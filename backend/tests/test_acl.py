"""G0 request gate: notebook / session / source-selection access (no database, no network: repositories are faked)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import chat as chat_api
from app.api.v1 import deps
from app.api.v1.deps import can_access_notebook, can_chat, get_optional_user_id, is_guest_notebook, owns_session
from app.db.mongodb import get_database
from app.db.qdrant import get_qdrant_client
from app.models.chat import ChatSessionRecord, MessageRecord
from app.models.notebook import NotebookRecord

GUEST_ID = "nb_guest_" + "a" * 32
NOTEBOOKS = {
    "nb_alice": NotebookRecord(notebook_id="nb_alice", user_id="alice", title="A"),
    "nb_sec_demo": NotebookRecord(notebook_id="nb_sec_demo", user_id="admin", title="Mẫu"),
    GUEST_ID: NotebookRecord(notebook_id=GUEST_ID, user_id="guest", title="Khách"),
    "nb_guest_trial": NotebookRecord(notebook_id="nb_guest_trial", user_id="guest", title="Cũ, dùng chung"),
}
SESSIONS = {
    "ses_alice": ChatSessionRecord(session_id="ses_alice", notebook_id="nb_alice", user_id="alice"),
    "ses_guest": ChatSessionRecord(session_id="ses_guest", notebook_id=GUEST_ID, user_id="guest"),
}


# ---------------------------------------------------------------- the rules
def test_owner_reads_and_writes_others_do_not():
    nb = NOTEBOOKS["nb_alice"]
    assert can_access_notebook(nb, "alice", write=True)
    assert not can_access_notebook(nb, "bob") and not can_access_notebook(nb, None)


def test_sample_notebook_is_read_only_and_chat_needs_its_owner():
    nb = NOTEBOOKS["nb_sec_demo"]
    assert can_access_notebook(nb, None) and can_access_notebook(nb, "bob")
    assert not can_access_notebook(nb, "bob", write=True)
    assert not can_chat(nb, None) and not can_chat(nb, "bob") and can_chat(nb, "admin")


def test_guest_notebook_needs_an_unguessable_id():
    assert is_guest_notebook(NOTEBOOKS[GUEST_ID]) and can_chat(NOTEBOOKS[GUEST_ID], None)
    old = NOTEBOOKS["nb_guest_trial"]  # the shared trial notebook every guest used to see
    assert not is_guest_notebook(old) and not can_access_notebook(old, None) and not can_chat(old, None)


def test_session_belongs_to_one_caller():
    assert owns_session(SESSIONS["ses_alice"], "alice") and not owns_session(SESSIONS["ses_alice"], "bob")
    assert not owns_session(SESSIONS["ses_alice"], None) and owns_session(SESSIONS["ses_guest"], None)
    assert not owns_session(SESSIONS["ses_guest"], "alice")


def test_qdrant_filter_refuses_a_search_without_notebook():
    from app.services.retrieval.qdrant_retriever import QdrantRetriever

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

    def __init__(self, db):
        pass

    async def get_session(self, session_id):
        return SESSIONS.get(session_id)

    async def get_sessions_by_notebook(self, notebook_id):
        return [s for s in SESSIONS.values() if s.notebook_id == notebook_id]

    async def get_messages(self, session_id, limit=50):
        return []

    async def save_session(self, session):
        self.saved.append(session)

    async def append_message(self, message):
        pass


class Stop(Exception):
    """Raised by the faked orchestrator: the request got past every gate."""


@pytest.fixture
def client(monkeypatch):
    caller = {"id": None}
    monkeypatch.setattr(deps, "NotebookRepository", FakeNotebooks)
    monkeypatch.setattr(chat_api, "ChatRepository", FakeChats)

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
    assert ask(client, None, notebook_id="nb_guest_trial", document_ids=["d1"]).status_code == 403
    assert ask(client, "bob", notebook_id="nb_missing", document_ids=["d1"]).status_code == 404


def test_guest_cannot_chat_in_the_shared_sample(client):
    assert ask(client, None, notebook_id="nb_sec_demo", document_ids=["d1"]).status_code == 403


def test_a_source_must_be_selected_within_the_limit(client):
    assert ask(client, "alice", notebook_id="nb_alice").status_code == 422
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=[f"d{i}" for i in range(6)]).status_code == 422
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1", "d2"]).status_code == 422


def test_someone_elses_session_is_refused(client):
    assert ask(client, "bob", notebook_id="nb_alice", document_ids=["d1"], session_id="ses_alice").status_code == 403
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"], session_id="ses_guest").status_code == 403  # other notebook
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"], session_id="ses_ghost").status_code == 403


def test_allowed_questions_reach_the_orchestrator(client):
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"], session_id="ses_alice").status_code == 500  # Stop
    FakeChats.saved.clear()
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1"]).status_code == 500
    assert FakeChats.saved[-1].user_id == "guest" and len(FakeChats.saved[-1].session_id) == len("ses_") + 32


def test_messages_and_session_lists_are_the_callers_own(client):
    client.caller["id"] = "bob"
    assert client.get("/chat/sessions/ses_alice/messages").status_code == 403
    assert client.get("/chat/sessions/notebook/nb_alice").status_code == 403
    client.caller["id"] = "alice"
    assert client.get("/chat/sessions/ses_alice/messages").status_code == 200
    assert [s["session_id"] for s in client.get("/chat/sessions/notebook/nb_alice").json()] == ["ses_alice"]


def test_document_list_and_upload_check_the_notebook(monkeypatch):
    from app.api.v1 import documents as doc_api

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
    assert c.post("/documents/upload/nb_sec_demo", files=pdf).status_code == 403  # samples are read-only


def test_mentions_must_be_selected_sources(client):
    r = ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"], mentions=["d9"])
    assert r.status_code == 422


def test_guest_questions_are_not_capped(client, monkeypatch):
    async def five_questions_so_far(self, session_id, limit=50):
        return [MessageRecord(message_id=f"m{i}", session_id=session_id, role="user", content="q") for i in range(5)]

    monkeypatch.setattr(FakeChats, "get_messages", five_questions_so_far)
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1"], session_id="ses_guest").status_code == 500  # Stop: past every gate
