"""The retrieval half of a question: which selected documents are searched, with which queries, and the chunks that come back."""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, TypeVar

import httpx
from qdrant_client.http.exceptions import ResponseHandlingException

from app.core.config import settings
from app.core.error_codes import Code
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import logger
from app.modules.documents.document import DocumentRecord
from app.modules.query_router.catalog_route import question_years, r5
from app.modules.query_router.decomposer import decompose_query
from app.modules.query_router.bridge import continue_plan
from app.modules.query_router.input_policy import _split, detect_language, needs_lookup
from app.modules.query_router.planner import PlanItem, plan_multi_doc, plan_with_then
from app.modules.chat.scope import catalog_card, catalog_entry, document_label, text_years
from app.modules.retrieval.hybrid_search import SEARCH_PARTS, HybridSearchService


T = TypeVar("T")
# What a dropped or slow vector store looks like: a timeout, a refused or reset connection, an httpx transport error, the client's own wrapper of those.
# The remote GPU worker is not here: its client already resends once and reports ServiceUnavailableError, which passes through unchanged.
SEARCH_FAILURES = (asyncio.TimeoutError, ConnectionError, httpx.TransportError, ResponseHandlingException)


async def search_with_retry(call: Callable[[], Awaitable[T]]) -> T:
    """Run one search (a function returning the awaitable, so every try is a new one); a transient failure is tried again SEARCH_RETRIES times,
    then the user gets SEARCH_UNAVAILABLE. A search only reads, so sending it again changes nothing."""
    tries = settings.SEARCH_RETRIES + 1
    for attempt in range(1, tries + 1):
        try:
            return await call()
        except SEARCH_FAILURES as exc:
            logger.warning(f"Search failed (try {attempt} of {tries}): {type(exc).__name__}: {str(exc)[:120]}")
            if attempt == tries:
                raise ServiceUnavailableError(Code.SEARCH_UNAVAILABLE) from exc
            await asyncio.sleep(settings.SEARCH_RETRY_DELAY_SECONDS)
    raise AssertionError("unreachable")  # the loop returns or raises


@dataclass
class RetrievalResult:
    scope: List[DocumentRecord]
    labels: Dict[str, str]
    plan: List[PlanItem]
    sub_queries: List[str]
    retrieved: List[Dict[str, Any]]
    routing: str = "planner"  # [targets_]single | [targets_]planner | r5 | r4 (how the searched documents were chosen)
    timings: Dict[str, float] = field(default_factory=dict)  # seconds: plan (planner / decomposer), search
    missing: List[str] = field(default_factory=list)  # V1: targeted documents with no retrieved chunk even after the retry
    hop: Dict[str, Any] = field(default_factory=dict)  # MULTIHOP_ENABLED: the dependent part and what the second step did (empty when there was none)


async def second_step(hybrid_search: HybridSearchService, query: str, then: str, retrieved: List[Dict[str, Any]], notebook_id: str, scope: List[DocumentRecord],
                      ids: List[str]) -> Dict[str, Any]:
    """A two-step question (settings MULTIHOP_ENABLED): when the dependent part names an item to look up, the intermediate call settles the first step from the
    first excerpts and plans the second search; its new excerpts are appended after the first ones (whose numbers the result cites) while the context stays
    within GATE_MAX_TOKENS (tokens counted as characters / 4). A bare comparison ("which was higher?") needs no second search."""
    hop: Dict[str, Any] = {"then": then}
    if not needs_lookup(then):
        return {**hop, "skipped": "no item to look up"}
    labels = {d.document_id: document_label(d) for d in scope}
    for c in retrieved:  # the intermediate call reads each excerpt under its source's name, as the writer does
        if c["document_id"] in labels:
            c["document_label"] = labels[c["document_id"]]
    bridge = await continue_plan(query, then, retrieved, [catalog_entry(d) for d in scope])
    if bridge is None:
        return {**hop, "skipped": "first step not settled"}
    more = await search_with_retry(lambda: hybrid_search.retrieve_planned(bridge.question or query, bridge.plan, notebook_id, ids))
    held = {c.get("chunk_id") for c in retrieved}
    used = sum(len(c["content"]) for c in retrieved) // 4
    added = 0
    for c in more:
        size = len(c["content"]) // 4
        if c.get("chunk_id") in held or used + size > settings.GATE_MAX_TOKENS:
            continue
        retrieved.append(c)
        held.add(c.get("chunk_id"))
        used += size
        added += 1
    return {**hop, "found": bridge.found, "citations": bridge.citations, "question": bridge.question,
            "plan": [{"query": p.query, "documents": p.document_ids} for p in bridge.plan], "added": added}


async def route_by_code(hybrid_search: HybridSearchService, query: str, notebook_id: str, scope: List[DocumentRecord], ids: List[str]) -> Tuple[List[Dict[str, Any]], str]:
    """(chunks, routing) without a plan: R5 on the catalog, then R4 (15/11: R5 on the first pages' text removed, it never answered on 179 gold questions)."""
    routed = r5(query, ids, {d.document_id: catalog_card(d) for d in scope})
    if routed:
        return await search_with_retry(lambda: hybrid_search.retrieve_multi_doc([PlanItem(query, [d]) for d in routed], notebook_id, ids)), "r5"
    years = question_years(query)
    return await search_with_retry(lambda: hybrid_search.retrieve_by_content(query, notebook_id, ids, [d for d, y in text_years(scope).items() if y in years])), "r4"


async def retrieve_for_scope(hybrid_search: HybridSearchService, query: str, notebook_id: str, scope: List[DocumentRecord], forced: Optional[List[str]] = None, *,
                             tagged: bool = False) -> RetrievalResult:
    """Retrieval only. One selected document: the measured single-filing path. Several: the planner writes one query per
    (selected document, item), and the results and a search with the question take equal slots (retrieve_planned); the planner
    choosing among the selected documents only maps queries to them, it never widens the scope. Any planner failure falls back to the measured path over the selection.
    `forced` (G3: the documents the question targets, by @file or by code): the search runs over those documents only, so the
    planner only writes queries (one document: the single-filing path).
    `tagged`: the forced documents are the user's own @file tags. When code chose them instead (a company named in the question), the evidence gate of the planned
    search may still look at the rest of the selection (hybrid_search.retrieve_planned, settings GATE_*); the user's tags are never widened."""
    selected = [d.document_id for d in scope]
    labels = {d.document_id: document_label(d) for d in scope}  # of the whole selection: a chunk the gate adds carries its source's name too
    targeted = [d for d in scope if d.document_id in set(forced or [])]
    scope = targeted or scope
    ids = [d.document_id for d in scope]
    wider = {"gate_document_ids": selected} if targeted and not tagged and len(selected) > len(ids) else {}
    plan: List[PlanItem] = []
    routing = ("targets_" if targeted else "") + ("single" if len(scope) == 1 else "planner")
    multi = len(scope) >= 2 and settings.MULTIDOC_ENABLED  # a notebook holds at most MAX_SELECTED_DOCS_USER (5) documents: no count above which the planner is skipped
    t0 = time.perf_counter()
    parts: Dict[str, float] = {}  # seconds in each part of the search (hybrid_search.part_done), kept in the trace as search_<part>
    SEARCH_PARTS.set(parts)
    then = ""
    if multi and settings.MULTIHOP_ENABLED:
        plan, then = await plan_with_then(query, [catalog_entry(d) for d in scope])
    elif multi:
        plan = await plan_multi_doc(query, [catalog_entry(d) for d in scope])
    t_plan = time.perf_counter() - t0
    hop: Dict[str, Any] = {}
    if plan:
        # R5 repairs what the plan misses (planner_fallback/fallback_eval.py): an item without documents searches the documents
        # the question names, and each named document the plan does not search gets a search with the question (FB3, add only).
        named = r5(query, ids, {d.document_id: catalog_card(d) for d in scope}) or []
        plan = [PlanItem(p.query, p.document_ids or named) for p in plan]
        searched = {d for p in plan for d in (p.document_ids or ids)}
        plan += [PlanItem(query, [d]) for d in named if d not in searched]
        sub_queries = [p.query for p in plan]
        retrieved = await search_with_retry(lambda: hybrid_search.retrieve_planned(query, plan, notebook_id, ids, **wider))
        if then:
            hop = await second_step(hybrid_search, query, then, retrieved, notebook_id, scope, ids)
    elif multi:
        # no plan (model down or no valid JSON): the routing without a language model. With MULTIDOC_WHOLE_MESSAGE the message reached here uncut, so code cuts it
        # (input_policy._split) and routes each part; the chunks are pooled in order (measured as the net: 12 of 24 messages, see config)
        pieces = (_split(query) or [query]) if settings.MULTIDOC_WHOLE_MESSAGE else [query]
        retrieved, routes = [], []
        for part in pieces:
            chunks, route = await route_by_code(hybrid_search, part, notebook_id, scope, ids)
            seen = {c.get("chunk_id") for c in retrieved}
            retrieved += [c for c in chunks if c.get("chunk_id") not in seen]
            routes.append(route)
        routing, sub_queries = ("r5" if "r5" in routes else "r4"), pieces
    else:
        doc_filter = ids[0] if len(ids) == 1 else (ids or None)
        if len(ids) == 1 and detect_language(query) == "en":  # Qwen scores the question's pool while the LLM writes the sub-queries
            (search_query, sub_queries), _ = await asyncio.gather(decompose_query(query),
                                                                  hybrid_search.prescore(query, notebook_id, doc_filter))
        else:  # a Vietnamese question is searched in English: its pool is only known after the call
            search_query, sub_queries = await decompose_query(query)  # English for a Vietnamese question; the answer keeps `query`
        t_plan = time.perf_counter() - t0
        retrieved = await search_with_retry(lambda: hybrid_search.retrieve_research(search_query, sub_queries, notebook_id, doc_filter))
    missing: List[str] = []
    if targeted and len(ids) > 1:  # V1: every targeted document must show up; one more search of its own, then say what is missing
        for doc_id in [d for d in ids if not any(c["document_id"] == d for c in retrieved)]:
            more = await search_with_retry(lambda: hybrid_search.retrieve_multi_doc([PlanItem(q, [doc_id]) for q in dict.fromkeys(sub_queries or [query])],
                                                                                    notebook_id, [doc_id], limit=settings.V1_RETRY_CHUNKS))
            retrieved += more
            if not more:
                missing.append(doc_id)
    for chunk in retrieved:
        if chunk["document_id"] in labels:
            chunk["document_label"] = labels[chunk["document_id"]]
    timings = {"plan": round(t_plan, 2), "search": round(time.perf_counter() - t0 - t_plan, 2)} | {f"search_{k}": v for k, v in parts.items()}
    return RetrievalResult(scope, labels, plan, sub_queries, retrieved, routing, timings, missing, hop)
