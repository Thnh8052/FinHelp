"""The "search deeper" button (CODE_MODEL_DECISIONS 4.1, N2; owner 17/11: a click runs the standard pipeline, never a quick search). The click sends the
question again with retry_of and deeper=True; the server reads what the clicked answer sent (trace chunk_ids, else its citations), leaves those excerpts
out of the new search (planner, first stage, reranker, selection as usual, so new excerpts come up), and writes the new answer from the excerpts the first
answer cited followed by the new ones."""
import types

from app.core.config import settings
from app.modules.chat import chat as chat_api
from app.modules.chat.chat_models import MessageRecord
from app.modules.query_router.planner import PlanItem
from app.modules.retrieval.hybrid_search import HybridSearchService
from app.modules.retrieval.term_cache import TERMS
from tests.test_no_gate import BY_DOCUMENT, TEXT, _Chunks, _doc, _Embedder, _Retriever


class _Reranker:
    def __init__(self):
        self.calls = []

    async def score_pairs(self, pairs):
        self.calls.append(list(pairs))
        return [0.9 if "revenue" in t else 0.5 for _, t in pairs]

    async def score(self, query, passages):
        return [0.9 if "revenue" in t else 0.5 for t in passages]


def _service(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_ENABLED", True)
    svc = HybridSearchService.__new__(HybridSearchService)
    svc.embedder, svc.retriever, svc.chunk_repo, svc.reranker = _Embedder(), _Retriever(BY_DOCUMENT), _Chunks(TEXT, BY_DOCUMENT), _Reranker()
    svc._qwen = {}
    TERMS.clear()
    return svc


async def test_a_planned_search_leaves_out_the_excerpts_already_sent(monkeypatch):
    svc = _service(monkeypatch)
    first = await svc.retrieve_planned("the question", [PlanItem("revenue", ["d1", "d2"])], "nb", ["d1", "d2"])
    assert "a1" in {c["chunk_id"] for c in first}
    svc = _service(monkeypatch)
    again = await svc.retrieve_planned("the question", [PlanItem("revenue", ["d1", "d2"])], "nb", ["d1", "d2"], exclude={"a1", "b1"})
    assert {c["chunk_id"] for c in again}.isdisjoint({"a1", "b1"}) and "a2" in {c["chunk_id"] for c in again}
    assert not any(t in ("revenue a", "revenue b") for _, t in svc.reranker.calls[0])  # the excerpts already sent are not even scored again


async def test_a_single_document_search_leaves_them_out_too(monkeypatch):
    svc = _service(monkeypatch)

    async def search_vectors(vectors, notebook_id, document_id=None, limit=5, per_vector_documents=None):
        return [[{"chunk_id": "a1", "score": 0.9}, {"chunk_id": "a2", "score": 0.8}] for _ in vectors]

    svc.retriever.search_vectors = search_vectors
    chunks = await svc.retrieve_research("q", [], "nb", "d1", exclude={"a1"})
    assert [c["chunk_id"] for c in chunks] == ["a2"]


async def test_the_retrieval_step_passes_the_excluded_excerpts_to_the_search(monkeypatch):
    from app.modules.chat import retrieval_step

    seen = {}

    class Search:
        async def retrieve_planned(self, question, plan, notebook_id, scope_ids, **kwargs):
            seen["planned"] = kwargs
            return [{"chunk_id": "n", "document_id": scope_ids[0], "page": 1, "content": "x", "score": 0.5}]

        async def retrieve_research(self, question, sub_queries, notebook_id, document_id=None, **kwargs):
            seen["research"] = kwargs
            return [{"chunk_id": "n", "document_id": "d1", "page": 1, "content": "x", "score": 0.5}]

        async def prescore(self, *a):
            return None

    async def plan(query, catalog):
        return [PlanItem("revenue", [])]

    async def split(query):
        return query, []

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", plan)
    monkeypatch.setattr(retrieval_step, "decompose_query", split)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    await retrieval_step.retrieve_for_scope(Search(), "Compare revenue", "nb", [_doc("d1", "Alpha", 2023), _doc("d2", "Beta", 2023)], exclude={"old"})
    await retrieval_step.retrieve_for_scope(Search(), "What was revenue?", "nb", [_doc("d1", "Alpha", 2023)], exclude={"old"})
    assert seen == {"planned": {"exclude": {"old"}}, "research": {"exclude": {"old"}}}


def test_what_a_clicked_answer_sent_and_cited():
    traced = MessageRecord(message_id="m2", notebook_id="nb", role="assistant", content="...",
                           citations=[{"citation_id": "c1", "chunk_id": "a1", "document_id": "d1", "page": 1, "snippet": "x", "cited": True},
                                      {"citation_id": "c2", "chunk_id": "a2", "document_id": "d1", "page": 2, "snippet": "y", "cited": False}],
                           trace_info={"chunk_ids": ["a1", "a2", "a3"]})
    assert chat_api.deeper_of(traced) == {"exclude": ["a1", "a2", "a3"], "keep": ["a1"]}
    older = traced.model_copy(update={"trace_info": {}})  # an answer stored before the trace kept chunk ids: its citations list what was sent
    assert chat_api.deeper_of(older) == {"exclude": ["a1", "a2"], "keep": ["a1"]}


async def test_a_deeper_click_reaches_the_orchestrator():
    seen = {}

    class Orchestrator:
        async def execute_query(self, **kw):
            seen.update(kw)
            return {"answer": "x", "intent": "retrieval_rag", "citations": [], "trace": {}}

    clicked = MessageRecord(message_id="m2", notebook_id="nb", role="assistant", content="...", trace_info={"chunk_ids": ["a1"]})
    adm = chat_api._Admitted(types.SimpleNamespace(focus_state={}), ["d1"], [], Orchestrator(), [], None, retry_of=clicked)
    await chat_api._answered(adm, chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"], retry_of="m2", deeper=True), "u1")
    assert seen["retry"] is True and seen["deeper"] == {"exclude": ["a1"], "keep": []}
    seen.clear()
    await chat_api._answered(adm, chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"], retry_of="m2"), "u1")
    assert seen["retry"] is True and seen.get("deeper") is None  # a chooser click: a new search over the ticked documents, nothing left out


def test_the_kept_excerpts_come_first_and_the_new_ones_fit_the_budget():
    from app.modules.chat.orchestrator import kept_then_new

    kept = [{"chunk_id": "k", "content": "a " * 10, "token_count": 10}]
    new = [{"chunk_id": "k", "content": "dup", "token_count": 1}] + [{"chunk_id": f"n{i}", "content": "b " * 10, "token_count": 10} for i in range(5)]
    out = kept_then_new(kept, new, budget=30, count=lambda c: c["token_count"])
    assert [c["chunk_id"] for c in out] == ["k", "n0", "n1"]  # the duplicate is dropped, the budget stops the rest


# ------------------------------------------------------------------ the documents of a click (UI check 17/11: a click followed the sidebar, not the answer)
def test_an_answer_records_the_documents_it_was_asked_over():
    class Orchestrator:
        async def execute_query(self, **kw):
            return {"answer": "x", "intent": "retrieval_rag", "citations": [], "trace": {}}

    import asyncio

    adm = chat_api._Admitted(types.SimpleNamespace(focus_state={}), ["d1", "d2"], ["d2"], Orchestrator(), [], None)
    result = asyncio.run(chat_api._answered(adm, chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1", "d2"], mentions=["d2"]), "u1"))
    assert result["trace"]["asked"] == {"document_ids": ["d1", "d2"], "mentions": ["d2"]}


def test_a_deeper_click_searches_the_documents_of_the_clicked_answer_not_the_current_selection():
    clicked = MessageRecord(message_id="m2", notebook_id="nb", role="assistant", content="...",
                            trace_info={"asked": {"document_ids": ["d1", "d2"], "mentions": ["d1", "d2"]}})
    assert chat_api.same_documents(clicked, ["d1"], []) == (["d1", "d2"], ["d1", "d2"])
    older = clicked.model_copy(update={"trace_info": {}})  # stored before the trace kept them: the request's choice stands
    assert chat_api.same_documents(older, ["d1"], []) == (["d1"], [])


def test_a_try_again_click_asks_the_same_documents_and_leaves_nothing_out():
    import asyncio

    seen = {}

    class Orchestrator:
        async def execute_query(self, **kw):
            seen.update(kw)
            return {"answer": "x", "intent": "retrieval_rag", "citations": [], "trace": {}}

    clicked = MessageRecord(message_id="m2", notebook_id="nb", role="assistant", content="...", trace_info={"chunk_ids": ["a1"]})
    adm = chat_api._Admitted(types.SimpleNamespace(focus_state={}), ["d1"], [], Orchestrator(), [], None, retry_of=clicked)
    req = chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"], retry_of="m2", again=True)
    asyncio.run(chat_api._answered(adm, req, "u1"))
    assert seen["retry"] is True and seen.get("deeper") is None  # the same search, nothing left out
    assert chat_api.uses_answer_documents(req) and chat_api.uses_answer_documents(req.model_copy(update={"again": False, "deeper": True}))
    assert not chat_api.uses_answer_documents(req.model_copy(update={"again": False}))  # a chooser click asks the ticked documents
