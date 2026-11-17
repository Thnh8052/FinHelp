"""The evidence gate (L15) is gone (owner 17/11/2026, docs/VERSION_4/TRIED.md TK-55): on TK-49 it saved 1 of 187 questions when the planner was right
(a question naming no company, which the "understood" line and its document chooser now cover) and 1.2 / 4.9 / 4.3 points when the planner was wrong,
for 35 more reranker pairs a question. A planned search now looks only at the documents its plan searches; a document the planner left out is repaired by
R5 (a named company) or by the user (the buttons). Fakes as the gate's old tests (experiments/archive/removed_gate_2026-11-17)."""
import inspect
import types

from app.core.config import settings
from app.modules.query_router.planner import PlanItem
from app.modules.retrieval.hybrid_search import HybridSearchService
from app.modules.retrieval.term_cache import TERMS


class _Embedder:
    async def embed_queries(self, queries):
        return [[0.0] for _ in queries]


class _Retriever:
    def __init__(self, by_document):
        self.by_document, self.calls = by_document, []

    async def search_vectors(self, vectors, notebook_id, document_id=None, limit=5, per_vector_documents=None):
        self.calls.append([list(d) for d in per_vector_documents])
        return [sorted(({"chunk_id": c, "score": s} for d in docs for c, s in self.by_document[d]), key=lambda h: -h["score"])[:limit] for docs in per_vector_documents]


class _Chunks:
    def __init__(self, text, by_document):
        self.text, self.by_document = text, by_document
        self.owner = {c: d for d, chunks in by_document.items() for c, _ in chunks}

    async def get_text_by_document(self, document_ids):
        return {d: {c: (self.text[c], 100) for c, _ in self.by_document[d]} for d in document_ids if d in self.by_document}

    async def get_chunks_by_ids(self, ids):
        return [types.SimpleNamespace(chunk_id=i, document_id=self.owner[i], page=1, section=None, chunk_type="text", token_count=100, content=self.text[i],
                                      concept_ids=[]) for i in ids]


class _Reranker:
    def __init__(self):
        self.calls = []

    async def score_pairs(self, pairs):
        self.calls.append(list(pairs))
        return [0.9 if "revenue" in t else 0.1 for _, t in pairs]


BY_DOCUMENT = {"d1": [("a1", 0.90), ("a2", 0.80)], "d2": [("b1", 0.90)], "d3": [("c1", 0.99), ("c2", 0.50)]}
TEXT = {"a1": "revenue a", "a2": "other", "b1": "revenue b", "c1": "revenue c", "c2": "nothing"}


async def test_a_planned_search_never_looks_at_a_document_its_plan_does_not_search(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_ENABLED", True)
    svc = HybridSearchService.__new__(HybridSearchService)
    svc.embedder, svc.retriever, svc.chunk_repo, svc.reranker = _Embedder(), _Retriever(BY_DOCUMENT), _Chunks(TEXT, BY_DOCUMENT), _Reranker()
    TERMS.clear()
    # d3 is selected and its best chunk (0.99) is above the searched documents' 0.90: the old gate opened it
    chunks = await svc.retrieve_planned("the question", [PlanItem("revenue", ["d1", "d2"])], "nb", ["d1", "d2", "d3"])
    assert "d3" not in {c["document_id"] for c in chunks}
    assert len(svc.retriever.calls) == 1 and not any("d3" in docs for docs in svc.retriever.calls[0])  # one vector search, inside d1 and d2 only
    assert len(svc.reranker.calls) == 1 and not any(t in ("revenue c", "nothing") for _, t in svc.reranker.calls[0])


def test_no_gate_setting_or_argument_is_left():
    assert not [k for k in type(settings).model_fields if k.startswith("GATE_")]
    assert "gate_document_ids" not in inspect.signature(HybridSearchService.retrieve_planned).parameters
    import app.modules.retrieval.hybrid_search as hs
    assert not any(hasattr(hs, name) for name in ("gate_open", "gate_pool", "gate_extra"))


def _doc(doc_id, company, year):
    from app.modules.documents.document import DocumentMetadata, DocumentRecord

    return DocumentRecord(document_id=doc_id, notebook_id="nb", file_name=f"{doc_id}.pdf", file_size_bytes=1, file_path="p", status="ready",
                          metadata=DocumentMetadata(company_name=company, report_type="10-K", fiscal_year=year))


async def test_documents_forced_by_code_are_searched_alone(monkeypatch):
    from app.modules.chat import retrieval_step

    seen = {}

    class Search:
        async def retrieve_planned(self, question, plan, notebook_id, scope_ids, **kwargs):
            seen.update(scope=list(scope_ids), kwargs=kwargs)
            return [{"chunk_id": d, "document_id": d, "page": 1, "content": "x", "score": 0.5} for d in scope_ids]

    async def fake_plan(query, catalog):
        return [PlanItem("revenue", [])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", fake_plan)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    scope = [_doc("d1", "Alpha Corp", 2023), _doc("d2", "Beta Inc", 2023), _doc("d3", "Gamma Ltd", 2023)]
    await retrieval_step.retrieve_for_scope(Search(), "Compare the revenue of the two companies", "nb", scope, ["d1", "d2"])
    assert seen == {"scope": ["d1", "d2"], "kwargs": {}}  # no wider look at d3


def test_windows_only_for_text_chunks_of_600_tokens_or_more():
    assert settings.RERANK_WINDOW_MIN_TOKENS == 600  # TK-56: 167 -> 160 pairs a question, +1/-0 on gold v2, no loss when the planner is wrong
