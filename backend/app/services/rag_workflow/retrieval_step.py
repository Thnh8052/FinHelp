"""The retrieval half of a question: which selected documents are searched, with which queries, and the chunks that come back."""
import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.document import DocumentRecord
from app.services.query_router.catalog_route import joined, question_years, r5, r5_text
from app.services.query_router.decomposer import decompose_query
from app.services.query_router.input_policy import detect_language
from app.services.query_router.planner import PlanItem, plan_multi_doc
from app.services.rag_workflow.scope import catalog_card, catalog_entry, document_label, text_years
from app.services.retrieval.hybrid_search import HybridSearchService


@dataclass
class RetrievalResult:
    scope: List[DocumentRecord]
    labels: Dict[str, str]
    plan: List[PlanItem]
    sub_queries: List[str]
    retrieved: List[Dict[str, Any]]
    routing: str = "planner"  # [targets_]single | [targets_]planner | planner+net | r5 | r5_text | r4 (how the searched documents were chosen)
    timings: Dict[str, float] = field(default_factory=dict)  # seconds: plan (planner / decomposer), search
    missing: List[str] = field(default_factory=list)  # V1: targeted documents with no retrieved chunk even after the retry


async def retrieve_for_scope(hybrid_search: HybridSearchService, query: str, notebook_id: str, scope: List[DocumentRecord], forced: Optional[List[str]] = None, net_others: bool = False) -> RetrievalResult:
    """Retrieval only. One selected document: the measured single-filing path. Several: the planner writes one query per
    (selected document, item) and the results take equal slots; the planner choosing among the selected documents only
    maps queries to them, it never widens the scope. Any planner failure falls back to the measured path over the selection.
    `forced` (G3: the documents the question targets, by @file or by code): the search runs over those documents only, so the
    planner only writes queries (one document: the single-filing path). `net_others`: the question also writes a name no
    catalog carries, so the selected documents outside `forced` get the safety net."""
    targeted = [d for d in scope if d.document_id in set(forced or [])]
    targets_scope = scope
    others = [d.document_id for d in scope if targeted and d not in targeted and net_others]
    scope = targeted or scope
    ids = [d.document_id for d in scope]
    labels = {d.document_id: document_label(d) for d in scope}
    plan: List[PlanItem] = []
    routing = ("targets_" if targeted else "") + ("single" if len(scope) == 1 else "planner")
    multi = 2 <= len(scope) <= settings.MULTIDOC_CATALOG_LIMIT and settings.MULTIDOC_ENABLED
    t0 = time.perf_counter()
    if multi:
        plan = await plan_multi_doc(query, [catalog_entry(d) for d in scope])
    t_plan = time.perf_counter() - t0
    if plan:
        # R5 repairs what the plan misses (planner_fallback/fallback_eval.py): an item without documents searches the documents
        # the question names. When the planner chose the documents (no G3 target) the safety net covers every document it skipped;
        # without the net, each named document the plan does not search gets a search with the question (FB3, add only).
        named = r5(query, ids, {d.document_id: catalog_card(d) for d in scope}) or []
        plan = [PlanItem(p.query, p.document_ids or named) for p in plan]
        searched = {d for p in plan for d in (p.document_ids or ids)}
        net_on = settings.NET_ENABLED and not targeted
        if not net_on:
            plan += [PlanItem(query, [d]) for d in named if d not in searched]
        sub_queries = [p.query for p in plan]
        retrieved = await hybrid_search.retrieve_multi_doc(plan, notebook_id, ids)
        skipped = [d for d in ids if d not in searched]
        if net_on and skipped:
            retrieved += extra_slots(retrieved, await hybrid_search.safety_net(
                query, [p.query for p in plan], notebook_id, skipped, [c["chunk_id"] for c in retrieved]))
            routing = "planner+net"
    elif multi:
        # no plan (model down or no valid JSON): the routing without a language model, R5 on the catalog, then R5 on the text, then R4
        routed, routing = r5(query, ids, {d.document_id: catalog_card(d) for d in scope}), "r5"
        if not routed:
            routed, routing = r5_text(query, ids, await first_words(hybrid_search, scope), text_years(scope)), "r5_text"
        sub_queries = [query]
        if routed:
            retrieved = await hybrid_search.retrieve_multi_doc([PlanItem(query, [d]) for d in routed], notebook_id, ids)
        else:
            routing = "r4"
            years = question_years(query)
            retrieved = await hybrid_search.retrieve_by_content(query, notebook_id, ids, [d for d, y in text_years(scope).items() if y in years])
    else:
        doc_filter = ids[0] if len(ids) == 1 else (ids or None)
        if len(ids) == 1 and detect_language(query) == "en":  # Qwen scores the question's pool while the LLM writes the sub-queries
            (search_query, sub_queries), _ = await asyncio.gather(decompose_query(query),
                                                                  hybrid_search.prescore(query, notebook_id, doc_filter))
        else:  # a Vietnamese question is searched in English: its pool is only known after the call
            search_query, sub_queries = await decompose_query(query)  # English for a Vietnamese question; the answer keeps `query`
        t_plan = time.perf_counter() - t0
        retrieved = await hybrid_search.retrieve_research(search_query, sub_queries, notebook_id, doc_filter)
    if others and settings.NET_ENABLED:
        retrieved += extra_slots(retrieved, await hybrid_search.safety_net(
            query, sub_queries or [query], notebook_id, others, [c["chunk_id"] for c in retrieved]))
        routing += "+net"
        labels.update({d.document_id: document_label(d) for d in targets_scope if d.document_id in others})
    missing: List[str] = []
    if targeted and len(ids) > 1:  # V1: every targeted document must show up; one more search of its own, then say what is missing
        for doc_id in [d for d in ids if not any(c["document_id"] == d for c in retrieved)]:
            more = await hybrid_search.retrieve_multi_doc([PlanItem(q, [doc_id]) for q in dict.fromkeys(sub_queries or [query])],
                                                               notebook_id, [doc_id], limit=settings.V1_RETRY_CHUNKS)
            retrieved += more
            if not more:
                missing.append(doc_id)
    for chunk in retrieved:
        if chunk["document_id"] in labels:
            chunk["document_label"] = labels[chunk["document_id"]]
    timings = {"plan": round(t_plan, 2), "search": round(time.perf_counter() - t0 - t_plan, 2)}
    return RetrievalResult(scope, labels, plan, sub_queries, retrieved, routing, timings, missing)


def extra_slots(retrieved: List[Dict[str, Any]], net: List[Any]) -> List[Dict[str, Any]]:
    """Safety-net chunks into at most NET_EXTRA_SLOTS extra slots, the token cap raised by 1,024 a slot."""
    cap = settings.MULTIDOC_MAX_TOKENS + 1024 * settings.NET_EXTRA_SLOTS
    used = sum(len(c["content"]) // 4 for c in retrieved)  # stream 1 is already capped at 8,192 tokens; chars / 4 is enough here
    out = []
    for chunk, tokens in net[: settings.NET_EXTRA_SLOTS]:
        if used + tokens > cap:
            continue
        out.append(chunk)
        used += tokens
    return out


async def first_words(hybrid_search: HybridSearchService, scope: List[DocumentRecord]) -> Dict[str, set]:
    """Words of each document's first two pages (R5 on the text, when the catalog names nothing)."""
    out = {}
    for d in scope:
        chunks = await hybrid_search.chunk_repo.get_chunks_by_document(d.document_id)
        first = sorted({c.page for c in chunks})[:2]
        out[d.document_id] = joined(re.findall(r"[a-z0-9&]+", " ".join(c.content for c in chunks if c.page in first).lower()))
    return out
