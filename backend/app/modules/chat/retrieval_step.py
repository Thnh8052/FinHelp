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
from app.modules.query_router.planner import PlanItem, PlanUnavailable, plan_multi_doc, plan_with_then
from app.modules.chat.scope import catalog_card, catalog_entry, document_label, text_years
from app.modules.retrieval.hybrid_search import SEARCH_PARTS, HybridSearchService


T = TypeVar("T")
EMPTY_PLAN = "empty_plan"  # routing of a valid empty plan: nothing searched (step 3, tests/test_empty_plan.py)
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
    routing: str = "planner"  # [targets_]single | [targets_]planner | r5 | r4 (how the searched documents were chosen) | empty_plan (nothing searched) | targets_question (an empty plan code vetoed: the question in each targeted document)
    timings: Dict[str, float] = field(default_factory=dict)  # seconds: plan (planner / decomposer), search
    missing: List[str] = field(default_factory=list)  # targeted documents with no retrieved chunk
    hop: Dict[str, Any] = field(default_factory=dict)  # MULTIHOP_ENABLED: the dependent part and what the second step did (empty when there was none)
    degraded: List[str] = field(default_factory=list)  # "plan_deadline", "plan_unavailable", "rerank_skipped": a step dropped for time or failure (the answer shows "search more")


PLAN_FAILURES = ("plan_deadline", "plan_unavailable")


async def within_deadline(call: Awaitable[T], fallback: T, degraded: List[str]) -> T:
    """`call`, or `fallback` past PLAN_DEADLINE_SECONDS (the planner or the query split) or when the planner had no plan to give (PlanUnavailable: the
    model down, no valid plan twice); noted in `degraded` as "plan_deadline" or "plan_unavailable" (before 18/11 a failed planner was not noted at all)."""
    try:
        return await asyncio.wait_for(call, settings.PLAN_DEADLINE_SECONDS)
    except asyncio.TimeoutError:
        logger.warning(f"Planner past its {settings.PLAN_DEADLINE_SECONDS:.0f} s deadline: the question goes on without its plan")
        degraded.append("plan_deadline")
        return fallback
    except PlanUnavailable:
        degraded.append("plan_unavailable")
        return fallback


async def second_step(hybrid_search: HybridSearchService, query: str, then: str, retrieved: List[Dict[str, Any]], notebook_id: str, scope: List[DocumentRecord],
                      ids: List[str]) -> Dict[str, Any]:
    """A two-step question (settings MULTIHOP_ENABLED): when the dependent part names an item to look up, the intermediate call settles the first step from the
    first excerpts and plans the second search; its new excerpts are appended after the first ones (whose numbers the result cites) while the context stays
    within MULTIDOC_PLANNED_MAX_TOKENS (tokens counted as characters / 4). A bare comparison ("which was higher?") needs no second search."""
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
        if c.get("chunk_id") in held or used + size > settings.MULTIDOC_PLANNED_MAX_TOKENS:
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


async def retrieve_for_scope(hybrid_search: HybridSearchService, query: str, notebook_id: str, scope: List[DocumentRecord], forced: Optional[List[str]] = None,
                             exclude: Optional[set] = None) -> RetrievalResult:
    """Retrieval only. One selected document: the measured single-filing path. Several: the planner writes one query per
    (selected document, item), and the results and a search with the question take equal slots (retrieve_planned); the planner
    choosing among the selected documents only maps queries to them, it never widens the scope. Any planner failure falls back to the measured path over the selection.
    `forced` (G3: the documents the question targets, by @file or by code): the search runs over those documents only, so the
    planner only writes queries (one document: the single-filing path). Nothing outside them is searched, whoever chose them (the evidence gate L15 is gone,
    TRIED TK-55): a wrong choice shows in the "understood" line, whose buttons ask again with other documents.
    `exclude`: chunks a "search deeper" click leaves out (the planned and the single-document searches; the routes without a plan search as usual)."""
    left_out = {"exclude": exclude} if exclude else {}
    labels = {d.document_id: document_label(d) for d in scope}
    targeted = [d for d in scope if d.document_id in set(forced or [])]
    scope = targeted or scope
    ids = [d.document_id for d in scope]
    plan: List[PlanItem] = []
    routing = ("targets_" if targeted else "") + ("single" if len(scope) == 1 else "planner")
    multi = len(scope) >= 2 and settings.MULTIDOC_ENABLED  # a notebook holds at most MAX_SELECTED_DOCS_USER (5) documents: no count above which the planner is skipped
    t0 = time.perf_counter()
    parts: Dict[str, float] = {}  # seconds in each part of the search (hybrid_search.part_done), kept in the trace as search_<part>
    SEARCH_PARTS.set(parts)
    then = ""
    degraded: List[str] = []
    if multi and settings.MULTIHOP_ENABLED:
        plan, then = await within_deadline(plan_with_then(query, [catalog_entry(d) for d in scope]), ([], ""), degraded)
    elif multi:
        plan = await within_deadline(plan_multi_doc(query, [catalog_entry(d) for d in scope]), [], degraded)
    t_plan = time.perf_counter() - t0
    hop: Dict[str, Any] = {}
    if plan:
        # R5 repairs what the plan misses (planner_fallback/fallback_eval.py): an item without documents searches the documents
        # the question names, and each named document the plan does not search gets a search with the question (FB3, add only). So does each
        # targeted document (@file, a ticked chooser box): the user said the question is about it (tests/test_tagged_documents.py).
        named = r5(query, ids, {d.document_id: catalog_card(d) for d in scope}) or []
        plan = [PlanItem(p.query, p.document_ids or named) for p in plan]
        searched = {d for p in plan for d in (p.document_ids or ids)}
        plan += [PlanItem(query, [d]) for d in dict.fromkeys(named + (ids if targeted else [])) if d not in searched]
        sub_queries = [p.query for p in plan]
        retrieved = await search_with_retry(lambda: hybrid_search.retrieve_planned(query, plan, notebook_id, ids, **left_out))
        if then:
            hop = await second_step(hybrid_search, query, then, retrieved, notebook_id, scope, ids)
    elif multi and not targeted and not set(PLAN_FAILURES) & set(degraded):
        # a VALID empty plan: the planner read the catalog of every selected report and chose none (gold v2: 6 of 200, all unanswerable; 0 of 274
        # answerable, TRIED KH-13). Nothing is searched; the answer is a fixed reply with "search all sources" (step 3, tests/test_empty_plan.py).
        routing, sub_queries, retrieved = EMPTY_PLAN, [], []
    elif multi and targeted and not set(PLAN_FAILURES) & set(degraded):
        # code vetoes a valid empty plan when it chose the documents (a named company, @ tags, the chooser, "search all sources"; KH-21: wrong 0 of 13):
        # EACH of them is searched with the question on the planned path, as a tagged document the plan skips is. Not the route without a plan: its R5
        # keeps only the report of the year asked (live check 18/11: Costco FY2015 never searched after "search all sources")
        plan = [PlanItem(query, [d]) for d in ids]
        routing, sub_queries = "targets_question", [query]
        retrieved = await search_with_retry(lambda: hybrid_search.retrieve_planned(query, plan, notebook_id, ids, **left_out))
    elif multi:
        # no plan (model down, no valid JSON, past the deadline): the routing without a language model. With MULTIDOC_WHOLE_MESSAGE the message reached here uncut, so code cuts it
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
            (search_query, sub_queries), _ = await asyncio.gather(within_deadline(decompose_query(query), (query, []), degraded),
                                                                  hybrid_search.prescore(query, notebook_id, doc_filter))
        else:  # a Vietnamese question is searched in English: its pool is only known after the call
            search_query, sub_queries = await within_deadline(decompose_query(query), (query, []), degraded)  # English for a Vietnamese question; the answer keeps `query`
        t_plan = time.perf_counter() - t0
        retrieved = await search_with_retry(lambda: hybrid_search.retrieve_research(search_query, sub_queries, notebook_id, doc_filter, **left_out))
    # a targeted document with no chunk is named so the answer says so (V1's own search of it ran 0 times in 192 questions, TRIED KH-14: gone 17/11)
    missing = [d for d in ids if not any(c["document_id"] == d for c in retrieved)] if targeted and len(ids) > 1 else []
    for chunk in retrieved:
        if chunk["document_id"] in labels:
            chunk["document_label"] = labels[chunk["document_id"]]
    timings = {"plan": round(t_plan, 2), "search": round(time.perf_counter() - t0 - t_plan, 2)} | {f"search_{k}": v for k, v in parts.items()}
    degraded += ["rerank_skipped"] if parts.get("rerank_skipped") else []
    return RetrievalResult(scope, labels, plan, sub_queries, retrieved, routing, timings, missing, hop, degraded)
