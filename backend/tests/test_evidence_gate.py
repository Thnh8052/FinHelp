"""The evidence gate of the planned search (docs/Version_3/RAG_REDESIGN_SPEC.md section 5.8, setting "L15", approved 16/11): after the main search, code
looks once at the selected documents the plan did NOT search; a document whose best dense similarity to the question is close to (or above) the best of the
searched ones is opened, its candidates are scored in the SAME reranker call as the main search, and the best of them are appended after the main chunks.
No language-model call. Measured in experiments/scripts/mvp/gate_strong.py and gate_timing.py."""
import types

import pytest

from app.core.config import settings
from app.modules.query_router.planner import PlanItem
from app.modules.retrieval.hybrid_search import SEARCH_PARTS, HybridSearchService, gate_extra, gate_open, gate_pool
from app.modules.retrieval.term_cache import TERMS


# ---------------------------------------------------------------- the three pure steps
def test_gate_open_takes_the_documents_near_the_searched_ones_largest_gap_first():
    gaps = {"far": -0.40, "near": -0.08, "above": 0.05, "edge": -0.10}
    assert gate_open(gaps, -0.10) == ["above", "near", "edge"]  # -0.10 itself opens; "far" never does. No cap of its own: a notebook holds at most 5 documents
    assert gate_open({"far": -0.40}, -0.10) == []
    assert gate_open({}, -0.10) == []


def test_gate_pool_fuses_the_rankings_with_the_question_counted_twice():
    question, sub_a, sub_b = ["a", "b", "c", "d"], ["d", "c"], ["d"]
    # d: 2/63 + 1/60 + 1/60 ; a: 2/60 ; c: 2/62 + 1/61 ; b: 2/61
    assert gate_pool([question, sub_a, sub_b], 4) == ["d", "c", "a", "b"]
    assert gate_pool([question, sub_a, sub_b], 2) == ["d", "c"]
    assert gate_pool([question], 3) == ["a", "b", "c"]  # no plan query: the question's own order
    assert gate_pool([], 3) == []


def test_gate_extra_scores_by_question_and_best_plan_query_and_keeps_the_best(monkeypatch):
    monkeypatch.setattr(settings, "GATE_MIN_SCORE", 0.15)
    monkeypatch.setattr(settings, "GATE_MAX_CHUNKS", 3)
    monkeypatch.setattr(settings, "GATE_MAX_TOKENS", 1000)
    qwen = {("q", "x"): 0.2, ("s1", "x"): 0.9, ("s2", "x"): 0.1,  # 0.6 * 0.2 + 0.4 * 0.9 = 0.48
            ("q", "y"): 0.5, ("s1", "y"): 0.0, ("s2", "y"): 0.0,  # 0.30
            ("q", "low"): 0.1, ("s1", "low"): 0.1,  # 0.10: under the floor
            ("q", "held"): 0.9, ("s1", "held"): 0.9,  # already among the main chunks
            ("q", "z"): 0.4, ("s1", "z"): 0.4,  # 0.40
            ("s1", "unscored"): 0.9}  # no score for the question: not judged
    tokens = {"x": 100, "y": 100, "z": 100, "low": 100, "held": 100, "w": 100}
    pools = [["x", "low", "held", "unscored"], ["y", "z"]]
    assert gate_extra(pools, qwen, "q", ["s1", "s2"], {"held"}, tokens, 0) == ["x", "z", "y"]  # best score first, over every opened document
    monkeypatch.setattr(settings, "GATE_MAX_CHUNKS", 2)
    assert gate_extra(pools, qwen, "q", ["s1", "s2"], {"held"}, tokens, 0) == ["x", "z"]
    monkeypatch.setattr(settings, "GATE_MAX_CHUNKS", 3)
    assert gate_extra(pools, qwen, "q", ["s1", "s2"], {"held"}, {**tokens, "z": 950}, 0) == ["x", "y"]  # a chunk that does not fit is skipped, the next one may fit
    assert gate_extra(pools, qwen, "q", ["s1", "s2"], {"held"}, tokens, 850) == ["x"]  # the main chunks already take most of the context
    assert gate_extra(pools, qwen, "q", [], set(), tokens, 0) == ["held", "y", "z"]  # no plan query: the question's score alone (x 0.2 is fourth)
    assert gate_extra([], qwen, "q", ["s1"], set(), tokens, 0) == []


# ---------------------------------------------------------------- the planned search with the gate
class _Embedder:
    async def embed_queries(self, queries):
        return [[0.0] for _ in queries]


class _Retriever:
    def __init__(self, by_document):
        self.by_document, self.calls = by_document, []

    async def search_vectors(self, vectors, notebook_id, document_id=None, limit=5, per_vector_documents=None):
        self.calls.append({"documents": [list(d) for d in per_vector_documents], "limit": limit})
        assert len(vectors) == len(per_vector_documents)
        return [sorted(({"chunk_id": c, "score": s} for d in docs for c, s in self.by_document[d]), key=lambda h: -h["score"])[:limit] for docs in per_vector_documents]


class _Chunks:
    def __init__(self, text, by_document):
        self.text, self.by_document = text, by_document
        self.owner = {c: d for d, chunks in by_document.items() for c, _ in chunks}

    async def get_text_by_document(self, document_ids):
        return {d: {c: (self.text[c], 100) for c, _ in self.by_document[d]} for d in document_ids if d in self.by_document}

    async def get_chunks_by_ids(self, ids):
        return [types.SimpleNamespace(chunk_id=i, document_id=self.owner[i], page=1, section=None, chunk_type="text", content=self.text[i], concept_ids=[]) for i in ids]


class _Reranker:
    def __init__(self, score):
        self.calls, self.score = [], score

    async def score_pairs(self, pairs):
        self.calls.append(list(pairs))
        return [self.score(q, t) for q, t in pairs]


BY_DOCUMENT = {"d1": [("a1", 0.90), ("a2", 0.80)], "d2": [("b1", 0.90)], "d3": [("c1", 0.99), ("c2", 0.50)]}
TEXT = {"a1": "revenue a", "a2": "other", "b1": "revenue b", "c1": "revenue c", "c2": "nothing"}


def _score(q, t):
    if q == "revenue":
        return {"revenue a": 0.9, "revenue b": 0.9, "revenue c": 0.8}.get(t, 0.05)
    return {"revenue c": 0.3}.get(t, 0.1)  # the question


def _service(monkeypatch, by_document=None, text=None, score=_score):
    by_document, text = by_document or BY_DOCUMENT, text or TEXT
    monkeypatch.setattr(settings, "RERANK_ENABLED", True)
    monkeypatch.setattr(settings, "GATE_ENABLED", True)
    svc = HybridSearchService.__new__(HybridSearchService)
    svc.embedder, svc.retriever, svc.chunk_repo, svc.reranker = _Embedder(), _Retriever(by_document), _Chunks(text, by_document), _Reranker(score)
    TERMS.clear()
    return svc


PLAN = [PlanItem("revenue", ["d1", "d2"])]


async def test_a_skipped_document_close_to_the_searched_ones_is_opened_and_its_best_chunk_appended(monkeypatch):
    svc = _service(monkeypatch)  # d3 was not planned; its best dense score 0.99 is above the searched documents' 0.90
    parts = {}
    token = SEARCH_PARTS.set(parts)
    try:
        chunks = await svc.retrieve_planned("the question", PLAN, "nb", ["d1", "d2", "d3"])
    finally:
        SEARCH_PARTS.reset(token)
    assert [c["chunk_id"] for c in chunks] == ["a1", "b1", "a2", "c1"]  # the main chunks as before, then the gate's: c1 = 0.6 * 0.3 + 0.4 * 0.8 = 0.50; c2 = 0.08 is under the floor
    assert chunks[-1]["document_id"] == "d3"
    assert len(svc.reranker.calls) == 1  # ONE reranker call: the gate's pairs travel with the main search's
    assert {("the question", "revenue c"), ("revenue", "revenue c"), ("revenue", "revenue a")} <= set(svc.reranker.calls[0])
    assert parts["gate_open"] == 1 and parts["gate_added"] == 1 and parts["gate_gap"] == pytest.approx(0.09) and parts["gate_pairs"] == 4  # 2 candidates x (question + 1 plan query)


async def test_a_skipped_document_far_from_the_searched_ones_stays_closed(monkeypatch):
    far = {**BY_DOCUMENT, "d3": [("c1", 0.50), ("c2", 0.40)]}  # 0.50 - 0.90 = -0.40, under the -0.10 that opens the gate
    svc = _service(monkeypatch, far)
    parts = {}
    token = SEARCH_PARTS.set(parts)
    try:
        chunks = await svc.retrieve_planned("the question", PLAN, "nb", ["d1", "d2", "d3"])
    finally:
        SEARCH_PARTS.reset(token)
    assert [c["chunk_id"] for c in chunks] == ["a1", "b1", "a2"]
    assert not any(t in ("revenue c", "nothing") for _, t in svc.reranker.calls[0])  # no pair of d3 is scored
    assert svc.retriever.calls[1] == {"documents": [["d3"]], "limit": 1}  # the look costs one top-1 vector search per skipped document, nothing else
    assert len(svc.retriever.calls) == 2 and parts["gate_open"] == 0 and parts["gate_added"] == 0 and parts["gate_gap"] == pytest.approx(-0.40)


async def test_an_opened_document_adds_nothing_when_no_chunk_reaches_the_floor(monkeypatch):
    svc = _service(monkeypatch, score=lambda q, t: 0.9 if t in ("revenue a", "revenue b") else 0.05)
    chunks = await svc.retrieve_planned("the question", PLAN, "nb", ["d1", "d2", "d3"])
    assert "d3" not in {c["document_id"] for c in chunks}


async def test_every_document_searched_means_nothing_to_look_at(monkeypatch):
    svc = _service(monkeypatch)
    chunks = await svc.retrieve_planned("the question", [PlanItem("revenue", ["d1", "d2", "d3"])], "nb", ["d1", "d2", "d3"])
    assert len(svc.retriever.calls) == 1  # the main search only
    assert {c["document_id"] for c in chunks} == {"d1", "d2", "d3"}


async def test_gate_off_never_looks_outside_the_plan(monkeypatch):
    svc = _service(monkeypatch)
    monkeypatch.setattr(settings, "GATE_ENABLED", False)
    chunks = await svc.retrieve_planned("the question", PLAN, "nb", ["d1", "d2", "d3"])
    assert [c["chunk_id"] for c in chunks] == ["a1", "b1", "a2"] and len(svc.retriever.calls) == 1


async def test_gate_documents_may_be_wider_than_the_searched_scope_or_absent(monkeypatch):
    svc = _service(monkeypatch)  # code forced d1 and d2: the search's scope is those two, the user selected three
    chunks = await svc.retrieve_planned("the question", PLAN, "nb", ["d1", "d2"])
    assert [c["chunk_id"] for c in chunks] == ["a1", "b1", "a2"]  # nothing skipped inside the scope
    svc = _service(monkeypatch)
    chunks = await svc.retrieve_planned("the question", PLAN, "nb", ["d1", "d2"], gate_document_ids=["d1", "d2", "d3"])
    assert [c["chunk_id"] for c in chunks] == ["a1", "b1", "a2", "c1"]


async def test_a_planner_that_chose_one_of_five_documents_lets_the_gate_open_the_other_four(monkeypatch):
    # a notebook holds at most 5 documents (MAX_SELECTED_DOCS_USER): the gate opens every skipped document that is close to the question, never more than 4
    five = {"d1": [("a1", 0.90)], **{f"s{i}": [(f"x{i}", 0.95 - i / 100)] for i in range(3)}, "far": [("f1", 0.20)]}
    text = {"a1": "revenue a", "f1": "revenue far", **{f"x{i}": f"revenue x{i}" for i in range(3)}}
    svc = _service(monkeypatch, five, text, lambda q, t: 0.9)
    parts = {}
    token = SEARCH_PARTS.set(parts)
    try:
        chunks = await svc.retrieve_planned("the question", [PlanItem("revenue", ["d1"])], "nb", ["d1", "s0", "s1", "s2", "far"])
    finally:
        SEARCH_PARTS.reset(token)
    assert {c["chunk_id"] for c in chunks} == {"a1", "x0", "x1", "x2"}  # three skipped documents opened, the far one (0.20 against 0.90) stays closed
    assert parts["gate_open"] == 3
    assert settings.MAX_SELECTED_DOCS_USER == 5


async def test_reranker_failure_keeps_the_main_search_and_adds_nothing(monkeypatch):
    svc = _service(monkeypatch)

    async def boom(pairs):
        raise RuntimeError("CUDA out of memory")

    svc.reranker.score_pairs = boom
    chunks = await svc.retrieve_planned("the question", PLAN, "nb", ["d1", "d2", "d3"])
    assert "d3" not in {c["document_id"] for c in chunks} and chunks  # the first-stage order still answers; an unscored candidate is never added


def test_gate_settings_are_the_measured_ones():
    assert (settings.GATE_ENABLED, settings.GATE_OPEN_GAP, settings.GATE_POOL, settings.GATE_PLAN_QUERIES) == (True, -0.10, 15, 3)
    assert (settings.GATE_QUESTION_WEIGHT, settings.GATE_MIN_SCORE, settings.GATE_MAX_CHUNKS, settings.GATE_MAX_TOKENS) == (0.6, 0.15, 14, 20480)
    assert not hasattr(settings, "GATE_MAX_DOCUMENTS")  # the 5-document limit of a notebook is the bound


# ---------------------------------------------------------------- which documents the gate may open (retrieval step)
def _doc(doc_id, company, year):
    from app.modules.documents.document import DocumentMetadata, DocumentRecord

    return DocumentRecord(document_id=doc_id, notebook_id="nb", file_name=f"{doc_id}.pdf", file_size_bytes=1, file_path="p", status="ready",
                          metadata=DocumentMetadata(company_name=company, report_type="10-K", fiscal_year=year))


class _Search:
    def __init__(self):
        self.gate = "not called"

    async def retrieve_planned(self, question, plan, notebook_id, scope_ids, **kwargs):
        self.scope, self.gate = list(scope_ids), kwargs.get("gate_document_ids")
        return [{"chunk_id": "c", "document_id": "d3", "page": 1, "content": "x", "score": 0.5}] + [{"chunk_id": d, "document_id": d, "page": 1, "content": "x", "score": 0.5} for d in scope_ids]

    async def retrieve_multi_doc(self, plan, notebook_id, scope_ids, limit=None):
        return []


async def _retrieve(monkeypatch, forced, **kwargs):
    from app.modules.chat import retrieval_step

    async def fake_plan(query, catalog):
        return [PlanItem("revenue", [])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", fake_plan)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    search = _Search()
    scope = [_doc("d1", "Alpha Corp", 2023), _doc("d2", "Beta Inc", 2023), _doc("d3", "Gamma Ltd", 2023)]
    found = await retrieval_step.retrieve_for_scope(search, "Compare the revenue of the two companies", "nb", scope, forced, **kwargs)
    return search, found


async def test_documents_forced_by_code_let_the_gate_see_the_rest_of_the_selection(monkeypatch):
    search, found = await _retrieve(monkeypatch, ["d1", "d2"])
    assert search.scope == ["d1", "d2"] and search.gate == ["d1", "d2", "d3"]
    assert next(c for c in found.retrieved if c["document_id"] == "d3")["document_label"].startswith("Gamma")  # a chunk the gate added carries its source's name


async def test_documents_tagged_by_the_user_keep_the_gate_inside_them(monkeypatch):
    search, _ = await _retrieve(monkeypatch, ["d1", "d2"], tagged=True)
    assert search.scope == ["d1", "d2"] and search.gate is None


async def test_the_planner_path_has_no_document_count_limit_of_its_own(monkeypatch):
    # a notebook holds at most 5 documents (MAX_SELECTED_DOCS_USER): the old "more than 80 documents: skip the planner" branch could not run and is gone
    from app.modules.chat import retrieval_step

    assert not hasattr(settings, "MULTIDOC_CATALOG_LIMIT")
    planned = []

    async def fake_plan(query, catalog):
        planned.append(len(catalog))
        return [PlanItem("revenue", [])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", fake_plan)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    search = _Search()
    scope = [_doc(f"d{i}", f"Company {i}", 2023) for i in range(1, 8)]  # more than a notebook can hold: still the planner path, no hidden ceiling
    await retrieval_step.retrieve_for_scope(search, "Compare the revenue of the companies", "nb", scope)
    assert planned == [7] and search.scope == [f"d{i}" for i in range(1, 8)]


async def test_no_forced_document_needs_no_wider_gate(monkeypatch):
    search, _ = await _retrieve(monkeypatch, None)
    assert search.scope == ["d1", "d2", "d3"] and search.gate is None  # the scope already is the whole selection
