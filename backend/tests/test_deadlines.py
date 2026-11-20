"""Step 2 of docs/VERSION_4/CODE_MODEL_DECISIONS_2026-11-17.md: a deadline for the planner (and the single-document query split) and for the reranker.
Past the planner's deadline the question goes the way it goes when the planner fails; past the reranker's, the first-stage order answers. Either way
the result says what was degraded, so the answer can show the "search more" button prominently (TRIED TK-57: without the reranker 89.3 -> 72.2 %)."""
import asyncio
import types

import pytest

from app.core.config import settings
from app.modules.query_router.planner import PlanItem
from app.modules.retrieval.hybrid_search import SEARCH_PARTS, HybridSearchService
from app.modules.retrieval.term_cache import TERMS
from tests.test_no_gate import BY_DOCUMENT, TEXT, _Chunks, _Embedder, _Retriever, _doc


def test_deadline_defaults():
    assert settings.PLAN_DEADLINE_SECONDS == 20.0  # the longest stored planner call took 17.0 s (gold v2, 200 calls)
    assert (settings.RERANK_DEADLINE_SECONDS, settings.RERANK_SECONDS_PER_PAIR) == (30.0, 0.15)  # longest measured 25.5 s; 0.15 s a pair is 3x the measured rate


class _SlowReranker:
    def __init__(self, seconds):
        self.seconds, self.calls = seconds, 0

    async def score_pairs(self, pairs):
        self.calls += 1
        await asyncio.sleep(self.seconds)
        return [0.9 for _ in pairs]

    async def score(self, query, passages):
        await asyncio.sleep(self.seconds)
        return [0.9 for _ in passages]


async def test_a_reranker_past_its_deadline_leaves_the_first_stage_order_and_says_so(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_ENABLED", True)
    monkeypatch.setattr(settings, "RERANK_DEADLINE_SECONDS", 0.05)
    monkeypatch.setattr(settings, "RERANK_SECONDS_PER_PAIR", 0.0)
    svc = HybridSearchService.__new__(HybridSearchService)
    svc.embedder, svc.retriever, svc.chunk_repo, svc.reranker = _Embedder(), _Retriever(BY_DOCUMENT), _Chunks(TEXT, BY_DOCUMENT), _SlowReranker(2.0)
    svc._qwen = {}
    TERMS.clear()
    parts = {}
    token = SEARCH_PARTS.set(parts)
    try:
        chunks = await asyncio.wait_for(svc.retrieve_planned("the question", [PlanItem("revenue", ["d1", "d2"])], "nb", ["d1", "d2"]), 1.0)
    finally:
        SEARCH_PARTS.reset(token)
    assert chunks and parts.get("rerank_skipped") == 1  # answered in the first-stage order, well before the slow reranker would have


async def test_the_single_document_search_has_the_same_deadline(monkeypatch):
    pytest.importorskip("torch")  # the single-document search reaches app.modules.retrieval.gpu, which imports torch
    monkeypatch.setattr(settings, "RERANK_ENABLED", True)
    monkeypatch.setattr(settings, "RERANK_DEADLINE_SECONDS", 0.05)
    monkeypatch.setattr(settings, "RERANK_SECONDS_PER_PAIR", 0.0)
    svc = HybridSearchService.__new__(HybridSearchService)
    svc.embedder, svc.retriever, svc.chunk_repo, svc.reranker = _Embedder(), _Retriever(BY_DOCUMENT), _Chunks(TEXT, BY_DOCUMENT), _SlowReranker(2.0)
    svc._qwen = {}

    async def search_vectors(vectors, notebook_id, document_id=None, limit=5, per_vector_documents=None):
        return [[{"chunk_id": "a1", "score": 0.9}, {"chunk_id": "a2", "score": 0.8}] for _ in vectors]

    svc.retriever.search_vectors = search_vectors
    parts = {}
    token = SEARCH_PARTS.set(parts)
    try:
        chunks = await asyncio.wait_for(svc.retrieve_research("q", [], "nb", "d1"), 1.0)
    finally:
        SEARCH_PARTS.reset(token)
    assert [c["chunk_id"] for c in chunks] == ["a1", "a2"] and parts.get("rerank_skipped") == 1


class _Search:
    def __init__(self):
        self.calls = []

    async def retrieve_planned(self, question, plan, notebook_id, scope_ids, **kwargs):
        self.calls.append(("planned", plan))
        return [{"chunk_id": "p", "document_id": scope_ids[0], "page": 1, "content": "x", "score": 0.5}]

    async def retrieve_multi_doc(self, plan, notebook_id, scope_ids, limit=None):
        self.calls.append(("code", [p.document_ids for p in plan]))
        return [{"chunk_id": "c", "document_id": plan[0].document_ids[0], "page": 1, "content": "x", "score": 0.5}]

    async def retrieve_by_content(self, query, notebook_id, ids, year_ids=None):
        self.calls.append(("content", ids))
        return [{"chunk_id": "r", "document_id": ids[0], "page": 1, "content": "x", "score": 0.5}]

    async def retrieve_research(self, question, sub_queries, notebook_id, document_id=None):
        self.calls.append(("research", question, list(sub_queries)))
        return [{"chunk_id": "s", "document_id": "d1", "page": 1, "content": "x", "score": 0.5}]

    async def prescore(self, *a):
        return None


async def test_a_planner_past_its_deadline_routes_without_a_plan_and_says_so(monkeypatch):
    from app.modules.chat import retrieval_step

    async def slow_plan(query, catalog):
        await asyncio.sleep(2.0)
        return [PlanItem("revenue", [])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", slow_plan)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    monkeypatch.setattr(settings, "PLAN_DEADLINE_SECONDS", 0.05)
    search = _Search()
    scope = [_doc("d1", "Alpha Corp", 2023), _doc("d2", "Beta Inc", 2023)]
    found = await asyncio.wait_for(retrieval_step.retrieve_for_scope(search, "Compare Alpha Corp and Beta Inc revenue", "nb", scope), 1.0)
    assert found.plan == [] and found.degraded == ["plan_deadline"]
    assert search.calls and search.calls[0][0] in ("code", "content")  # the route of a failed planner, not a planned search


async def test_a_query_split_past_its_deadline_searches_with_the_question_alone(monkeypatch):
    from app.modules.chat import retrieval_step

    async def slow_split(query):
        await asyncio.sleep(2.0)
        return query, ["a", "b"]

    monkeypatch.setattr(retrieval_step, "decompose_query", slow_split)
    monkeypatch.setattr(settings, "PLAN_DEADLINE_SECONDS", 0.05)
    search = _Search()
    found = await asyncio.wait_for(retrieval_step.retrieve_for_scope(search, "What was the revenue in 2023?", "nb", [_doc("d1", "Alpha Corp", 2023)]), 1.0)
    assert ("research", "What was the revenue in 2023?", []) in search.calls and found.degraded == ["plan_deadline"]


async def test_nothing_degraded_on_the_normal_path(monkeypatch):
    from app.modules.chat import retrieval_step

    async def plan(query, catalog):
        return [PlanItem("revenue", ["d1", "d2"])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", plan)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    found = await retrieval_step.retrieve_for_scope(_Search(), "Compare revenue", "nb", [_doc("d1", "Alpha Corp", 2023), _doc("d2", "Beta Inc", 2023)])
    assert found.degraded == []


def _unused():
    return types  # keep the import for the fakes' SimpleNamespace in test_no_gate
