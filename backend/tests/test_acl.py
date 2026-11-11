"""G0 request gate: notebook / session / source-selection access (no database, no network: repositories are faked)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.modules.chat import chat as chat_api
from app.shared import deps
from app.shared.deps import can_access_notebook, can_chat, get_optional_user_id
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.chat.chat_models import MessageRecord
from app.modules.notebooks.notebook import NotebookRecord

GUEST_ID = "nb_guest_" + "a" * 32
NOTEBOOKS = {
    "nb_alice": NotebookRecord(notebook_id="nb_alice", owner_id="alice", title="A", message_count=2),
    "nb_new": NotebookRecord(notebook_id="nb_new", owner_id="alice"),
    "nb_sample": NotebookRecord(notebook_id="nb_sample", owner_type="system", owner_id="system", title="Mẫu"),
    GUEST_ID: NotebookRecord(notebook_id=GUEST_ID, owner_type="guest", owner_id="a" * 32, title="Khách"),
}


# ---------------------------------------------------------------- the rules
def test_owner_reads_and_writes_others_do_not():
    nb = NOTEBOOKS["nb_alice"]
    assert can_access_notebook(nb, "alice", write=True)
    assert not can_access_notebook(nb, "bob") and not can_access_notebook(nb, None)


def test_sample_notebook_is_read_only_and_nobody_can_chat_in_it():
    nb = NOTEBOOKS["nb_sample"]
    assert can_access_notebook(nb, None) and can_access_notebook(nb, "bob")
    assert not can_access_notebook(nb, "bob", write=True)
    assert not can_chat(nb, None) and not can_chat(nb, "bob") and not can_chat(nb, "system")


def test_the_id_of_a_guest_notebook_is_the_guests_key():
    assert can_access_notebook(NOTEBOOKS[GUEST_ID], None, write=True) and can_chat(NOTEBOOKS[GUEST_ID], None)


def test_qdrant_filter_refuses_a_search_without_notebook():
    from app.modules.retrieval.qdrant_retriever import QdrantRetriever

    retriever = QdrantRetriever.__new__(QdrantRetriever)
    with pytest.raises(ValueError):
        retriever.build_payload_filter("")
    assert retriever.build_payload_filter("nb_alice", ["d1", "d2"]).must[0].key == "notebook_id"


# ---------------------------------------------------------------- the routes
class FakeNotebooks:
    def __init__(self, db):
        pass

    async def get_by_id(self, notebook_id):
        return NOTEBOOKS.get(notebook_id)


class FakeChats:
    saved = []
    titles = []

    def __init__(self, db):
        pass

    async def get_messages(self, notebook_id, limit=500):
        return []

    async def set_title(self, notebook_id, title):
        self.titles.append((notebook_id, title))

    async def append_message(self, message):
        self.saved.append(message)


class FakeUsers:
    def __init__(self, db):
        pass

    allowed = True
    reserved = []
    consumed = []

    async def reserve_quota(self, user_id):
        self.reserved.append(user_id)
        return self.allowed

    async def consume_quota(self, user_id, messages=1, tokens=0):
        self.consumed.append((user_id, messages, tokens))


class Stop(Exception):
    """Raised by the faked orchestrator: the request got past every gate."""


@pytest.fixture
def client(monkeypatch):
    caller = {"id": None}
    monkeypatch.setattr(deps, "NotebookRepository", FakeNotebooks)
    monkeypatch.setattr(chat_api, "ChatRepository", FakeChats)
    monkeypatch.setattr(chat_api, "UserRepository", FakeUsers)

    async def ready(db, notebook_id, ids):
        return None

    async def scope(self, notebook_id, ids, document_id=None):
        return []

    async def execute(self, **kw):
        raise Stop()

    monkeypatch.setattr(chat_api, "ensure_documents_ready", ready)
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "__init__", lambda self, db, qdrant: None)
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "resolve_scope", scope)
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", execute)
    app = FastAPI()
    app.include_router(chat_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_qdrant_client] = lambda: None
    app.dependency_overrides[get_optional_user_id] = lambda: caller["id"]
    c = TestClient(app, raise_server_exceptions=False)
    c.caller = caller
    return c


def ask(client, user, **body):
    client.caller["id"] = user
    return client.post("/chat/query", json={"query": "What was revenue in FY2023?", **body})


def test_other_users_notebook_is_refused(client):
    assert ask(client, "bob", notebook_id="nb_alice", document_ids=["d1"]).status_code == 403
    assert ask(client, None, notebook_id="nb_alice", document_ids=["d1"]).status_code == 403
    assert ask(client, "bob", notebook_id="nb_missing", document_ids=["d1"]).status_code == 404


def test_nobody_can_chat_in_a_sample_notebook(client):
    assert ask(client, None, notebook_id="nb_sample", document_ids=["d1"]).status_code == 403
    assert ask(client, "bob", notebook_id="nb_sample", document_ids=["d1"]).status_code == 403


def test_a_source_must_be_selected_within_the_limit(client):
    assert ask(client, "alice", notebook_id="nb_alice").status_code == 422
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=[f"d{i}" for i in range(6)]).status_code == 422
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1", "d2"]).status_code == 422


def test_allowed_questions_reach_the_orchestrator(client):
    FakeChats.saved.clear()
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"]).status_code == 500  # Stop
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1"]).status_code == 500
    assert FakeChats.saved == []  # a question that got no answer does not stay in the history


async def _answered(self, **kw):
    return {"answer": "ok", "intent": "qa", "citations": [], "charged": False,
            "trace": {"llm": {"calls": 2, "prompt_tokens": 90, "completion_tokens": 10}, "timings": {"total": 1.5}}}


def test_the_first_searched_question_names_the_chat(client, monkeypatch):
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", _answered)  # a reply that searched nothing (a greeting, a refusal)
    FakeChats.titles.clear()
    ask(client, "alice", notebook_id="nb_new", document_ids=["d1"])
    assert FakeChats.titles == []

    async def searched(self, **kw):
        return {**await _answered(self), "charged": True}

    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", searched)
    ask(client, "alice", notebook_id="nb_new", document_ids=["d1"])
    ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"])  # already has a title
    assert FakeChats.titles == [("nb_new", "What was revenue in FY2023?")]


def test_a_user_over_the_daily_limit_is_refused(client, monkeypatch):
    monkeypatch.setattr(FakeUsers, "allowed", False)
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"]).status_code == 429
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1"]).status_code == 500  # guests are counted per address, not on an account: Stop


def test_a_question_without_a_usable_source_reserves_nothing(client, monkeypatch):
    async def refuse(self, notebook_id, ids, document_id=None):
        raise chat_api.SourceSelectionError("no_source_selected")

    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "resolve_scope", refuse)
    FakeUsers.reserved.clear()
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"]).status_code == 422
    assert FakeUsers.reserved == []


def test_a_failed_question_gives_its_reservation_back(client):
    FakeUsers.consumed.clear()
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"]).status_code == 500  # Stop
    assert FakeUsers.consumed == [("alice", -1, 0)]


def test_a_searched_question_keeps_its_reservation(client, monkeypatch):
    async def searched(self, **kw):
        return {**await _answered(self), "charged": True}

    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", searched)
    FakeUsers.consumed.clear()
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"]).status_code == 200
    assert FakeUsers.consumed == [("alice", 0, 100)]


def test_guests_are_stopped_at_their_daily_questions(client, monkeypatch):
    monkeypatch.setattr(settings, "GUEST_DAILY_QUESTIONS", 2)
    guest = dict(notebook_id=GUEST_ID, document_ids=["d1"])
    assert [ask(client, None, **guest).status_code for _ in range(3)] == [500, 500, 429]  # 500: Stop, past every gate
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"]).status_code == 500  # an account has its own limit


def test_a_refused_guest_question_does_not_use_the_allowance(client, monkeypatch):
    monkeypatch.setattr(settings, "GUEST_DAILY_QUESTIONS", 1)
    assert ask(client, None, notebook_id=GUEST_ID).status_code == 422  # no source selected
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1"]).status_code == 500


def test_an_answer_is_stored_with_its_cost_and_counted(client, monkeypatch):
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", _answered)
    FakeChats.saved.clear()
    FakeUsers.consumed.clear()

    response = ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"])

    assert response.status_code == 200 and response.json()["title"] == "A"
    assert FakeUsers.consumed == [("alice", -1, 100)]  # not charged as a question: the reservation goes back, its tokens still count
    assert [m.role for m in FakeChats.saved] == ["user", "assistant"]
    stored = FakeChats.saved[-1]
    assert stored.role == "assistant" and stored.token_usage == {"prompt_tokens": 90, "completion_tokens": 10, "total_tokens": 100}
    assert stored.latency_ms == 1500 and stored.model_used


def test_an_answer_carries_no_internal_details(client, monkeypatch):
    async def answered(self, **kw):
        citation = {"citation_id": "c", "chunk_id": "internal-chunk", "document_id": "d", "page": 1, "snippet": "s", "score": 0.9, "cited": True}
        return {"answer": "ok", "intent": "internal-route", "citations": [citation], "verification": {"unverified_figures": ["internal-figure"]}, "trace": {}}

    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", answered)
    response = ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"])
    assert set(response.json()) == {"title", "query", "answer", "citations", "understood", "alternatives"}
    assert set(response.json()["citations"][0]) == {"citation_id", "document_id", "page", "snippet", "cited"} and "internal-" not in response.text


def test_the_stored_trace_keeps_both_kinds_of_verdict(client, monkeypatch):
    async def answered(self, **kw):
        return {"answer": "ok", "intent": "retrieval_rag", "citations": [], "trace": {"intent": {"label": "report_question"}}}

    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", answered)
    FakeChats.saved.clear()
    ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"])
    stored = FakeChats.saved[-1].trace_info
    assert stored["intent"] == "retrieval_rag" and stored["router"] == {"label": "report_question"}


def test_messages_are_the_notebook_owners(client):
    client.caller["id"] = "bob"
    assert client.get("/chat/messages/nb_alice").status_code == 403
    client.caller["id"] = "alice"
    assert client.get("/chat/messages/nb_alice").status_code == 200


def test_document_list_and_upload_check_the_notebook(monkeypatch):
    from app.modules.documents import documents as doc_api

    monkeypatch.setattr(deps, "NotebookRepository", FakeNotebooks)
    caller = {"id": "bob"}
    app = FastAPI()
    app.include_router(doc_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_qdrant_client] = lambda: None
    app.dependency_overrides[get_optional_user_id] = lambda: caller["id"]
    c = TestClient(app, raise_server_exceptions=False)
    assert c.get("/documents/notebook/nb_alice").status_code == 403
    pdf = {"file": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    assert c.post("/documents/upload/nb_alice", files=pdf).status_code == 403
    assert c.post("/documents/upload/nb_sample", files=pdf).status_code == 403  # samples are read-only


def test_mentions_must_be_selected_sources(client):
    r = ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"], mentions=["d9"])
    assert r.status_code == 422


def test_earlier_guest_messages_do_not_use_up_the_allowance(client, monkeypatch):
    async def five_questions_so_far(self, notebook_id, limit=500):
        return [MessageRecord(message_id=f"m{i}", notebook_id=notebook_id, role="user", content="q") for i in range(5)]

    monkeypatch.setattr(FakeChats, "get_messages", five_questions_so_far)
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1"]).status_code == 500  # Stop: past every gate
