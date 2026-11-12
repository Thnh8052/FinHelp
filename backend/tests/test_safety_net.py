"""The safety net of 12/11/2026: it opens only when the question looks more like a skipped document than like the kept ones, ranks the skipped documents' chunks by
(1 - alpha) x the question's Qwen score + alpha x the best plan query's, and keeps the ones at or above the gate."""
import types

import pytest

from app.core.config import settings
from app.modules.retrieval import hybrid_search
from app.modules.retrieval.hybrid_search import HybridSearchService
from app.modules.retrieval.term_cache import TERMS


class Embedder:
    async def embed_queries(self, texts):
        return [[float(i)] for i, _ in enumerate(texts)]


class Retriever:
    """per_vector_documents (the gate): the best score of each document; a document of the first stage: its chunks, the same order for every query."""

    def __init__(self, best, chunks):
        self.best, self.chunks = best, chunks
        self.calls = []

    async def search_vectors(self, vectors, notebook_id, document_id=None, limit=5, per_vector_documents=None):
        self.calls.append((len(vectors), document_id, limit))
        if per_vector_documents:
            return [[{"chunk_id": f"{d}_top", "score": self.best[d[0]]}] for d in per_vector_documents]
        return [[{"chunk_id": c, "score": s} for c, s in self.chunks[document_id]] for _ in vectors]


class Chunks:
    def __init__(self, text):
        self.text = text

    async def get_text_by_document(self, document_ids):
        return {d: {c: (t, 100) for c, t in self.text.items() if c.startswith(d)} for d in document_ids}

    async def get_chunks_by_ids(self, ids):
        return [types.SimpleNamespace(chunk_id=i, document_id=i.split("_")[0], page=1, section=None, chunk_type="text", content=self.text[i], concept_ids=[]) for i in ids]

    async def get_sparse_weights(self, ids):
        return {i: ({}, 100) for i in ids}


class Reranker:
    def __init__(self, score):
        self.score, self.pairs = score, []

    async def score_pairs(self, pairs):
        self.pairs += pairs
        return [self.score(q, t) for q, t in pairs]


def net(monkeypatch, best, score, **settings_):
    monkeypatch.setattr(settings, "RERANK_ENABLED", True)
    for k, v in dict(NET_GATE=0.15, NET_POOL=20, NET_FIRST_STAGE=200, NET_FUSION_ALPHA=0.4, NET_FUSION_QUERIES=3, NET_OPEN_MIN_DENSE_GAP=-0.10).items():
        monkeypatch.setattr(settings, k, settings_.get(k, v))
    TERMS.clear()
    chunks = {"s1": [("s1_a", 0.9), ("s1_b", 0.8), ("s1_c", 0.7)]}
    text = {"s1_a": "cover page of the company", "s1_b": "income statement table", "s1_c": "risk factors"}
    svc = HybridSearchService.__new__(HybridSearchService)
    svc.embedder, svc.retriever, svc.chunk_repo, svc.reranker, svc._qwen = Embedder(), Retriever(best, chunks), Chunks(text), Reranker(score), {}
    return svc


async def test_the_net_stays_closed_when_the_question_looks_more_like_the_kept_documents(monkeypatch):
    svc = net(monkeypatch, {"s1": 0.40, "k1": 0.55}, lambda q, t: 0.9)  # dense_skip = 0.40 - 0.55 = -0.15 < -0.10
    parts = {}
    token = hybrid_search.SEARCH_PARTS.set(parts)
    try:
        assert await svc.safety_net("question", ["income statement"], "nb", ["s1"], [], ["k1"]) == []
    finally:
        hybrid_search.SEARCH_PARTS.reset(token)
    assert parts == {"net_gap": -0.15, "net_open": 0.0}
    assert svc.reranker.pairs == []  # no Qwen pair was scored


async def test_the_net_opens_on_a_close_gap_and_ranks_by_the_fused_score(monkeypatch):
    def score(query, text):  # the cover page matches the question (company name), the table matches the plan query
        return {"question": {"cover": 0.60, "income": 0.05, "risk": 0.02}, "income statement": {"cover": 0.05, "income": 0.90, "risk": 0.01}}[query][text.split()[0]] if text.split()[0] in ("cover", "income", "risk") else 0.0

    svc = net(monkeypatch, {"s1": 0.50, "k1": 0.55}, score)  # dense_skip = -0.05 >= -0.10: open
    parts = {}
    token = hybrid_search.SEARCH_PARTS.set(parts)
    try:
        out = await svc.safety_net("question", ["income statement"], "nb", ["s1"], [], ["k1"])
    finally:
        hybrid_search.SEARCH_PARTS.reset(token)
    assert parts["net_open"] == 1.0 and parts["net_gap"] == pytest.approx(-0.05)
    # fused: cover 0.6 x 0.60 + 0.4 x 0.05 = 0.38, income 0.6 x 0.05 + 0.4 x 0.90 = 0.39, risk 0.6 x 0.02 + 0.4 x 0.01 = 0.016 (under the gate)
    assert [c["chunk_id"] for c, _ in out] == ["s1_b", "s1_a"]
    assert out[0][0]["score"] == pytest.approx(0.39) and out[0][0]["via"] == "safety_net" and out[0][1] == 100
    assert len(svc.reranker.pairs) == 6  # 3 chunks x (the question + one plan query), in one call


async def test_without_kept_documents_the_net_always_opens_and_without_alpha_it_scores_by_the_question_only(monkeypatch):
    svc = net(monkeypatch, {"s1": -0.9}, lambda q, t: 0.5 if q == "question" else 0.0, NET_FUSION_ALPHA=0.0)
    out = await svc.safety_net("question", ["income statement"], "nb", ["s1"], [])  # the code route: no gate
    assert len(out) == 3 and all(c["score"] == 0.5 for c, _ in out)
    assert {q for q, _ in svc.reranker.pairs} == {"question"}  # the plan queries are not scored when alpha is 0


async def test_a_reranker_failure_returns_nothing(monkeypatch):
    svc = net(monkeypatch, {"s1": 0.5, "k1": 0.5}, lambda q, t: 0.9)

    async def boom(pairs):
        raise RuntimeError("CUDA out of memory")

    svc.reranker.score_pairs = boom
    assert await svc.safety_net("question", ["x"], "nb", ["s1"], [], ["k1"]) == []
