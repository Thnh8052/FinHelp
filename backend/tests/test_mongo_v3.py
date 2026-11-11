"""MongoDB schema V3 rules (no database, no network: collections and repositories are faked)."""
import asyncio
from datetime import datetime, timedelta, timezone
import types

import pytest
from fastapi import HTTPException

from app.modules.auth import user_repo as user_repo_module
from app.modules.auth.user import UserRecord, today_utc
from app.modules.auth.user_repo import UserRepository
from app.modules.chat import chat as chat_api
from app.modules.chat.chat_models import MessageRecord
from app.modules.chat.chat_repo import ChatRepository
from app.modules.documents.document import DocumentRecord
from app.modules.ingestion.pipeline import IngestionPipeline
from app.modules.notebooks import notebooks as notebooks_api
from app.modules.notebooks import purge


def _user(**kw) -> UserRecord:
    return UserRecord(user_id="u1", email="a@example.com", username="alice", hashed_password="x", **kw)


def _doc(doc_id: str, status: str) -> DocumentRecord:
    return DocumentRecord(document_id=doc_id, notebook_id="nb", file_name=f"{doc_id}.pdf", file_size_bytes=1, file_path="p", status=status)


# ---------------------------------------------------------------- users
def test_email_and_username_are_case_insensitive_by_construction():
    user = UserRecord(user_id="u", email="A.Person@Example.COM", username="  ALICE ", hashed_password="x")
    assert user.email == "a.person@example.com" and user.username == "alice"


async def test_lookups_lowercase_what_the_user_typed(monkeypatch):
    seen = []

    async def find_one(self, query):
        seen.append(query)

    monkeypatch.setattr(UserRepository, "find_one", find_one)
    repo = UserRepository({"users": None})
    await repo.get_by_email("A@X.com")
    await repo.get_by_email_or_username(" BOB ")
    assert seen == [{"email": "a@x.com"}, {"$or": [{"email": "bob"}, {"username": "bob"}]}]


def test_quota_view_comes_from_the_role_and_the_counters():
    quota = _user(role="admin", daily_messages_limit=10000, daily_messages_used=3, total_tokens_consumed=7).quota
    assert (quota.tier, quota.max_upload_documents, quota.max_file_size_mb) == ("admin", 50, 100)
    assert (quota.messages_used_today, quota.total_tokens_consumed) == (3, 7)
    assert "quota" not in _user().model_dump()  # never stored


def test_a_window_from_an_earlier_day_counts_as_nothing_used():
    yesterday = today_utc() - timedelta(days=1)
    assert _user(daily_messages_used=9, daily_window_start=yesterday).messages_used_today() == 0
    assert _user(daily_messages_used=9, daily_window_start=today_utc().replace(tzinfo=None)).messages_used_today() == 9  # MongoDB gives naive UTC


def _evaluate(expression, doc):
    """The few aggregation operators the quota updates use."""
    if isinstance(expression, str) and expression.startswith("$"):
        return doc.get(expression[1:])
    if isinstance(expression, dict):
        operator, arguments = next(iter(expression.items()))
        values = [_evaluate(a, doc) for a in arguments]
        return {"$cond": lambda: values[1] if values[0] else values[2], "$lt": lambda: values[0] < values[1], "$add": lambda: sum(values),
                "$max": lambda: max(values), "$ifNull": lambda: values[1] if values[0] is None else values[0]}[operator]()
    return expression


class Users:
    """One document; like MongoDB, each update checks its filter and writes without letting another request in between (no await inside)."""

    def __init__(self, doc):
        self.doc = doc

    async def update_one(self, query, pipeline):
        if "$expr" in query and not _evaluate(query["$expr"], self.doc):
            return types.SimpleNamespace(matched_count=0, modified_count=0)
        self.doc.update({k: _evaluate(v, self.doc) for k, v in pipeline[0]["$set"].items()})
        return types.SimpleNamespace(matched_count=1, modified_count=1)


async def _consume(window_start, messages=1, tokens=100):
    doc = {"daily_messages_used": 5, "daily_window_start": window_start, "total_tokens_consumed": 1000}
    repo = UserRepository.__new__(UserRepository)
    repo.collection = Users(doc)
    await repo.consume_quota("u1", messages=messages, tokens=tokens)
    return doc


async def test_consume_quota_adds_within_the_same_day():
    doc = await _consume(today_utc())
    assert (doc["daily_messages_used"], doc["total_tokens_consumed"]) == (6, 1100)


async def test_consume_quota_restarts_the_count_on_a_new_day():
    doc = await _consume(today_utc() - timedelta(days=2))
    assert (doc["daily_messages_used"], doc["daily_window_start"], doc["total_tokens_consumed"]) == (1, today_utc(), 1100)


async def test_an_uncharged_request_still_records_its_tokens():
    doc = await _consume(today_utc(), messages=0, tokens=40)
    assert (doc["daily_messages_used"], doc["total_tokens_consumed"]) == (5, 1040)


def _quota_repo(used, limit=100, window_start=None):
    doc = {"daily_messages_used": used, "daily_messages_limit": limit, "daily_window_start": window_start or today_utc(), "total_tokens_consumed": 0}
    repo = UserRepository.__new__(UserRepository)
    repo.collection = Users(doc)
    return repo, doc


async def test_a_question_is_reserved_only_within_the_limit():
    repo, doc = _quota_repo(used=1, limit=2)
    assert await repo.reserve_quota("u1") is True and doc["daily_messages_used"] == 2
    assert await repo.reserve_quota("u1") is False and doc["daily_messages_used"] == 2


async def test_the_first_reservation_of_a_new_day_restarts_the_count():
    repo, doc = _quota_repo(used=2, limit=2, window_start=today_utc() - timedelta(days=1))
    assert await repo.reserve_quota("u1") is True
    assert (doc["daily_messages_used"], doc["daily_window_start"]) == (1, today_utc())


async def test_an_account_stored_without_a_limit_gets_the_default_one():
    repo, doc = _quota_repo(used=3)
    del doc["daily_messages_limit"]
    assert await repo.reserve_quota("u1") is True


@pytest.mark.parametrize("window_start, expected", [(today_utc(), 4), (today_utc() - timedelta(days=1), 0)])
async def test_giving_a_question_back_never_goes_below_zero(window_start, expected):
    repo, doc = _quota_repo(used=5, window_start=window_start)
    await repo.consume_quota("u1", messages=-1)
    assert doc["daily_messages_used"] == expected


async def _ask_together(monkeypatch, repo, requests, execute):
    class Chats:
        def __init__(self, db):
            pass

        async def get_messages(self, *a, **k):
            return []

        async def append_message(self, message):
            pass

    async def none(*a, **k):
        return None

    async def notebook(*a, **k):
        return types.SimpleNamespace(title="T", focus_state=None)

    monkeypatch.setattr(chat_api, "UserRepository", lambda db: repo)
    monkeypatch.setattr(chat_api, "ChatRepository", Chats)
    monkeypatch.setattr(chat_api, "require_notebook", notebook)
    monkeypatch.setattr(chat_api, "can_chat", lambda *a: True)
    monkeypatch.setattr(chat_api, "ensure_documents_ready", none)
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "__init__", lambda self, db, qdrant: None)
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "resolve_scope", none)
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", execute)
    question = chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"])
    return await asyncio.gather(*[chat_api.handle_user_query(None, question, "u1", None, None) for _ in range(requests)], return_exceptions=True)


async def test_questions_sent_together_cannot_pass_the_daily_limit(monkeypatch):
    repo, doc = _quota_repo(used=99, limit=100)
    started = []

    async def execute(self, **kw):
        started.append(1)
        await asyncio.sleep(0)  # the other requests run while this one is in the pipeline
        return {"answer": "ok", "intent": "qa", "citations": [], "trace": {}}

    results = await _ask_together(monkeypatch, repo, 5, execute)

    assert len(started) == 1  # one pipeline run for the one question left
    assert sorted(getattr(r, "status_code", 200) for r in results) == [200, 429, 429, 429, 429]
    assert doc["daily_messages_used"] == 100


async def test_several_failures_give_every_reserved_question_back(monkeypatch):
    repo, doc = _quota_repo(used=10)

    async def execute(self, **kw):
        await asyncio.sleep(0)
        raise RuntimeError("the pipeline broke")

    results = await _ask_together(monkeypatch, repo, 3, execute)

    assert all(isinstance(r, RuntimeError) for r in results) and doc["daily_messages_used"] == 10


# ---------------------------------------------------------------- strict chat gating
def _gate(monkeypatch, docs):
    class Documents:
        def __init__(self, db):
            pass

        async def get_by_notebook(self, _):
            return docs

    monkeypatch.setattr(chat_api, "DocumentRepository", Documents)
    return chat_api.ensure_documents_ready(None, "nb", ["ok"])


@pytest.mark.parametrize("status", ["pending", "processing"])
async def test_chat_is_locked_while_any_document_of_the_notebook_is_processing(monkeypatch, status):
    with pytest.raises(HTTPException) as exc:
        await _gate(monkeypatch, [_doc("ok", "ready"), _doc("other", status)])  # "other" is not even selected
    assert exc.value.status_code == 409


async def test_a_failed_document_does_not_block_the_chat(monkeypatch):
    await _gate(monkeypatch, [_doc("ok", "ready"), _doc("bad", "failed")])


async def test_a_selected_failed_document_is_refused(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        await _gate(monkeypatch, [_doc("ok", "failed")])
    assert exc.value.status_code == 422


# ---------------------------------------------------------------- messages
class Notebooks:
    def __init__(self):
        self.count = 0

    async def find_one_and_update(self, _query, update, **_):
        self.count += update["$inc"]["message_count"]
        assert "updated_at" in update["$set"]  # orders the chat list and postpones a guest notebook's expiry
        return {"message_count": self.count}


def _chat_repo():
    repo = ChatRepository.__new__(ChatRepository)
    repo.notebooks = Notebooks()
    repo.saved = []

    async def insert_one(data):
        repo.saved.append(data)
        return "id"

    repo.insert_one = insert_one
    return repo


async def test_messages_are_numbered_in_order():
    repo = _chat_repo()
    for i in range(3):
        await repo.append_message(MessageRecord(message_id=f"m{i}", notebook_id="nb", role="user", content="q"))
    assert [m["message_index"] for m in repo.saved] == [0, 1, 2]


async def test_history_keeps_the_newest_messages_in_conversation_order():
    repo = _chat_repo()
    calls = {}

    async def find_many(query, sort_by, limit):
        calls.update(query=query, sort_by=sort_by, limit=limit)
        return [{"message_id": f"m{i}", "notebook_id": "nb", "message_index": i, "role": "user", "content": "q"} for i in (59, 58, 57)]

    repo.find_many = find_many
    messages = await repo.get_messages("nb", limit=3)
    assert calls["sort_by"] == [("message_index", -1)] and [m.message_index for m in messages] == [57, 58, 59]


# ---------------------------------------------------------------- deletion and expiry
class Cursor:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self.it = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self.it)
        except StopIteration:
            raise StopAsyncIteration


class Messages:
    def __init__(self, log):
        self.log = log

    async def delete_many(self, query):
        self.log.append(("messages", query["notebook_id"]))


def _purge_setup(monkeypatch, docs_by_notebook, log):
    class Documents:
        def __init__(self, db):
            pass

        async def get_by_notebook(self, notebook_id):
            return docs_by_notebook.get(notebook_id, [])

        async def delete_document(self, document_id):
            log.append(("document", document_id))

    class Repo:
        kind = ""

        def __init__(self, db):
            pass

        async def delete_by_document(self, document_id):
            log.append((self.kind, document_id))

    class Chunks(Repo):
        kind = "chunks"

    class Jobs(Repo):
        kind = "job"

    class Notebook:
        def __init__(self, db):
            pass

        async def delete_notebook(self, notebook_id):
            log.append(("notebook", notebook_id))

    class Storage:
        async def delete_document_files(self, notebook_id, document_id, file_path):
            log.append(("file", document_id))

        def delete_notebook_folder(self, notebook_id):
            log.append(("folder", notebook_id))

    monkeypatch.setattr(purge, "DocumentRepository", Documents)
    monkeypatch.setattr(purge, "ChunkRepository", Chunks)
    monkeypatch.setattr(purge, "IngestionJobRepository", Jobs)
    monkeypatch.setattr(purge, "NotebookRepository", Notebook)
    monkeypatch.setattr(purge, "StorageService", Storage)


class Qdrant:
    def __init__(self, log):
        self.log = log

    async def collection_exists(self, _):
        return True

    async def delete(self, **kw):
        self.log.append(("vectors", kw["points_selector"].filter.must[0].match.value))


async def test_deleting_a_notebook_removes_everything_it_owns_and_itself_last(monkeypatch):
    log = []
    _purge_setup(monkeypatch, {"nb": [_doc("d1", "ready"), _doc("d2", "failed")]}, log)

    await purge.purge_notebook({"messages": Messages(log)}, Qdrant(log), "nb")

    for document in ("d1", "d2"):
        assert {("vectors", document), ("file", document), ("chunks", document), ("job", document), ("document", document)} <= set(log)
    assert ("messages", "nb") in log and ("folder", "nb") in log and log[-1] == ("notebook", "nb")


async def test_only_expired_idle_guest_notebooks_are_purged(monkeypatch):
    log = []
    _purge_setup(monkeypatch, {"busy": [_doc("d1", "processing")], "idle": [_doc("d2", "ready")]}, log)
    seen = {}

    class Expired:
        def find(self, query, _projection):
            seen.update(query)
            return Cursor([{"notebook_id": "busy"}, {"notebook_id": "idle"}])

    assert await purge.purge_expired_guests({"notebooks": Expired(), "messages": Messages(log)}, Qdrant(log)) == 1
    assert seen["owner_type"] == "guest" and ("notebook", "idle") in log and ("notebook", "busy") not in log


async def test_a_notebook_with_a_document_in_processing_cannot_be_deleted(monkeypatch):
    log = []
    _purge_setup(monkeypatch, {"nb": [_doc("d1", "processing")]}, log)

    async def own(db, notebook_id, user_id):
        return None

    monkeypatch.setattr(notebooks_api, "_own_notebook", own)
    with pytest.raises(HTTPException) as exc:
        await notebooks_api.delete_notebook("nb", user_id="alice", db=None, qdrant=Qdrant(log))
    assert exc.value.status_code == 409 and log == []


# ---------------------------------------------------------------- stalled ingestion
class Jobs:
    def __init__(self, stuck):
        self.stuck, self.update = stuck, None

    def find(self, query, _projection):
        self.query = query
        return Cursor([{"document_id": d} for d in self.stuck])

    async def update_many(self, query, update):
        self.update = update["$set"]


class Documents:
    def __init__(self):
        self.update = None

    async def update_many(self, query, update):
        self.query, self.update = query, update["$set"]


async def test_a_job_that_stopped_moving_fails_and_frees_its_file():
    jobs, documents = Jobs(["d1"]), Documents()

    assert await IngestionPipeline.fail_stalled({"ingestion_jobs": jobs, "documents": documents}) == 1

    assert jobs.query["updated_at"]["$lt"] < datetime.now(timezone.utc) and jobs.update["status"] == "failed"
    assert documents.query == {"document_id": {"$in": ["d1"]}}
    assert documents.update["status"] == "failed" and documents.update["file_hash"] is None and documents.update["error_message"]


def test_the_quota_module_is_the_single_place_that_counts():
    assert hasattr(user_repo_module.UserRepository, "reserve_quota") and hasattr(user_repo_module.UserRepository, "consume_quota")
    assert not hasattr(user_repo_module.UserRepository, "increment_quota_usage")
