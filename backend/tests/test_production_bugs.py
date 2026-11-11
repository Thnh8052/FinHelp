"""Bugs #15, #17, #18, #19, #21, #22, #23, #25 and #27 of docs/Version_3/production_bugs.md (no database, no network, no email: everything outside the code under test is faked).
The daily quota of #16 is tested with the other quota rules in test_mongo_v3.py and test_acl.py."""
import asyncio
from datetime import datetime, timedelta, timezone
import io
import time
import types

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from pymongo.errors import DuplicateKeyError
import pytest

from app import main
from app.api_router import api_v1_router
from app.core.config import settings
from app.core.security import create_access_token
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.storage.local_fs import StorageService
from app.modules.auth import auth as auth_api
from app.modules.auth.user import UserRecord
from app.modules.auth.user_repo import UserRepository
from app.modules.chat import chat as chat_api
from app.modules.chat.chat_models import CitationItem, MessageRecord
from app.modules.documents import documents as documents_api
from app.modules.documents.document import DocumentMetadata, DocumentRecord
from app.modules.ingestion.ingestion_job import IngestionJobRecord
from app.modules.notebooks import notebooks as notebooks_api
from app.shared import deps
from app.shared.deps import get_current_user_id, get_optional_user_id
from app.shared.rate_limit import spend_guest_allowance
from app.shared.unexpected_errors import UnexpectedErrors


def _on_the_event_loop() -> bool:
    """A blocking call made here would stop every other request of the server."""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


# ---------------------------------------------------------------- #15 what guests may spend
class Notebooks:
    saved = []

    def __init__(self, db):
        pass

    async def save_notebook(self, record):
        self.saved.append(record)


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(notebooks_api, "NotebookRepository", Notebooks)
    app = FastAPI()
    app.include_router(notebooks_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_current_user_id] = lambda: "alice"
    return TestClient(app, raise_server_exceptions=False)


def test_guest_notebooks_stop_at_the_daily_allowance(api, monkeypatch):
    monkeypatch.setattr(settings, "GUEST_DAILY_NOTEBOOKS", 2)
    Notebooks.saved.clear()
    assert [api.post("/notebooks/guest").status_code for _ in range(3)] == [200, 200, 429]
    assert len(Notebooks.saved) == 2  # the refused one created nothing


def _guest_at(address):
    return types.SimpleNamespace(client=types.SimpleNamespace(host=address))


def test_each_address_has_its_own_guest_allowance():
    spend_guest_allowance(_guest_at("10.0.0.1"), "question", 1)
    with pytest.raises(HTTPException) as refused:
        spend_guest_allowance(_guest_at("10.0.0.1"), "question", 1)
    assert refused.value.status_code == 429 and "đăng nhập" in refused.value.detail  # the interface offers the sign-in on this word
    spend_guest_allowance(_guest_at("10.0.0.2"), "question", 1)
    spend_guest_allowance(_guest_at("10.0.0.1"), "upload", 1)  # one allowance per kind of use


# ---------------------------------------------------------------- #17 registration input, #18 email
class Accounts:
    def __init__(self, db):
        pass

    async def get_by_email(self, email):
        return None

    async def get_by_username(self, username):
        return None

    async def save_user(self, user):
        return "id"


@pytest.fixture
def auth(monkeypatch):
    sent = []

    def send(*a, **k):
        sent.append(_on_the_event_loop())
        return True

    monkeypatch.setattr(auth_api, "UserRepository", Accounts)
    monkeypatch.setattr(auth_api.email_service, "send_account_confirmation", send)
    monkeypatch.setattr(auth_api.email_service, "send_password_reset_otp", send)
    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api/v1")
    app.dependency_overrides[get_database] = lambda: None
    client = TestClient(app, raise_server_exceptions=False)
    client.sent = sent
    return client


GOOD = {"email": "new@example.com", "username": "new_user.1", "password": "eight-chars"}


def _register(client, **changes):
    return client.post("/api/v1/auth/register", json={**GOOD, **changes})


def test_valid_registration_is_accepted(auth):
    response = _register(auth, full_name="  Nguyễn Văn A  ")
    assert response.status_code == 200 and response.json()["full_name"] == "Nguyễn Văn A"


@pytest.mark.parametrize("changes", [
    {"password": ""},
    {"password": "1"},
    {"password": "7-chars"},
    {"username": "     "},
    {"username": "ab"},
    {"username": "a" * 33},
    {"username": "a" * 20000},
    {"username": "has space"},
    {"username": "a@b.com"},  # sign-in looks an account up by email or username: a name must not look like an email
    {"full_name": "x" * 121},
])
def test_bad_registration_input_is_refused(auth, changes):
    assert _register(auth, **changes).status_code == 422
    assert auth.sent == []


def test_a_blank_full_name_falls_back_to_the_username(auth):
    assert _register(auth, full_name="   ").json()["full_name"] == GOOD["username"]


def test_two_registrations_at_once_get_a_clear_refusal(auth, monkeypatch):
    async def raced(self, user):
        raise DuplicateKeyError("E11000")

    monkeypatch.setattr(Accounts, "save_user", raced)
    assert _register(auth).status_code == 400
    assert auth.sent == []  # no welcome email for an account that was not created


def test_the_password_rule_is_the_same_for_a_new_password():
    with pytest.raises(ValueError):
        auth_api.ResetPasswordRequest(email="a@example.com", otp_code="123456", new_password="7-chars")
    with pytest.raises(ValueError):
        auth_api.ChangePasswordRequest(old_password="whatever", new_password="7-chars")


def test_the_welcome_email_does_not_hold_the_event_loop(auth):
    assert _register(auth).status_code == 200
    assert auth.sent == [False]


def test_the_reset_code_email_does_not_hold_the_event_loop(auth, monkeypatch):
    async def known(self, email):
        return UserRecord(user_id="u", email=email, username="alice", hashed_password="x")

    async def stored(self, email, token, expires_at):
        return True

    monkeypatch.setattr(Accounts, "get_by_email", known)
    monkeypatch.setattr(Accounts, "set_reset_token", stored, raising=False)
    assert auth.post("/api/v1/auth/forgot-password", json={"email": "a@example.com"}).status_code == 200
    assert auth.sent == [False]


def _account():
    return UserRecord(user_id="u", email="a@example.com", username="alice", hashed_password="stored-hash")


@pytest.fixture
def password_work(auth, monkeypatch):
    """Which bcrypt calls ran on the event loop; the account of the routes that need one."""
    calls = []

    def verify(plain, hashed):
        calls.append(("verify", _on_the_event_loop()))
        return plain == "the-right-password"

    def digest(plain):
        calls.append(("hash", _on_the_event_loop()))
        return "new-hash"

    async def found(self, *_):
        return _account()

    async def done(self, *a, **k):
        return True

    monkeypatch.setattr(auth_api, "verify_password", verify)
    monkeypatch.setattr(auth_api, "get_password_hash", digest)
    monkeypatch.setattr(auth_api.email_service, "send_password_changed_notification", lambda **k: auth.sent.append(_on_the_event_loop()) or True)
    for name in ("get_by_email_or_username", "update_last_login", "update_password"):
        monkeypatch.setattr(Accounts, name, found if name.startswith("get") else done, raising=False)
    auth.app.dependency_overrides[auth_api.get_current_user] = _account
    return calls


def test_registration_hashes_off_the_event_loop(auth, password_work):
    assert _register(auth).status_code == 200
    assert password_work == [("hash", False)]


def test_sign_in_checks_the_password_off_the_event_loop(auth, password_work):
    response = auth.post("/api/v1/auth/login-json", json={"identifier": "alice", "password": "the-right-password"})
    assert response.status_code == 200 and password_work == [("verify", False)]


def test_changing_a_password_stays_off_the_event_loop(auth, password_work):
    body = {"old_password": "the-right-password", "new_password": "a-new-long-password"}
    assert auth.post("/api/v1/auth/change-password", json=body).status_code == 200
    assert password_work == [("verify", False), ("hash", False)]
    assert auth.sent == [False]  # the "your password changed" email


def test_resetting_a_password_stays_off_the_event_loop(auth, password_work, monkeypatch):
    code = "123456"
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    async def attempt(self, email, max_attempts):
        user = _account()
        user.reset_token, user.reset_token_expires_at = auth_api._otp_hash(email, code), expiry
        return user

    monkeypatch.setattr(Accounts, "use_reset_attempt", attempt, raising=False)
    body = {"email": "a@example.com", "otp_code": code, "new_password": "a-new-long-password"}
    assert auth.post("/api/v1/auth/reset-password", json=body).status_code == 200
    assert password_work == [("hash", False)] and auth.sent == [False]


class _SignIns:
    async def get_by_email_or_username(self, identifier):
        return _account()

    async def update_last_login(self, user_id):
        return True


async def test_guesses_sent_together_cannot_pass_the_sign_in_limit(monkeypatch):
    checked = []

    def slow_wrong(plain, hashed):
        checked.append(plain)
        time.sleep(0.01)  # the requests overlap while each one waits for this
        return False

    monkeypatch.setattr(auth_api, "verify_password", slow_wrong)
    results = await asyncio.gather(*[auth_api._authenticate(_SignIns(), "alice", f"guess-{i}", "10.0.0.1") for i in range(40)], return_exceptions=True)

    assert len(checked) == auth_api.LOGIN_FAILS_PER_ACCOUNT
    assert sorted(r.status_code for r in results) == [401] * auth_api.LOGIN_FAILS_PER_ACCOUNT + [429] * (40 - auth_api.LOGIN_FAILS_PER_ACCOUNT)


async def test_correct_sign_ins_do_not_use_up_the_address_limit(monkeypatch):
    monkeypatch.setattr(auth_api, "verify_password", lambda plain, hashed: True)
    for _ in range(auth_api.LOGIN_FAILS_PER_IP + 1):
        assert (await auth_api._authenticate(_SignIns(), "alice", "right", "10.0.0.1")).user_id == "u"


# ---------------------------------------------------------------- #18 R2 calls
class R2:
    def __init__(self):
        self.calls = []

    def _note(self, name):
        self.calls.append((name, _on_the_event_loop()))

    def upload_file(self, **kw):
        self._note("upload")

    def download_file(self, Filename, **kw):
        self._note("download")

    def delete_object(self, **kw):
        self._note("delete")

    def get_paginator(self, _):
        return types.SimpleNamespace(paginate=lambda **kw: [])


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PDF_STORAGE_DIR", tmp_path / "pdfs")
    monkeypatch.setattr(settings, "ARTIFACTS_STORAGE_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", tmp_path)
    service = StorageService()
    service.backend, service._s3_client = "r2", R2()
    return service


async def test_saving_a_pdf_does_not_hold_the_event_loop(storage):
    path = await storage.save_pdf("nb", "doc", types.SimpleNamespace(filename="r.pdf", file=io.BytesIO(b"%PDF")))
    assert path.read_bytes() == b"%PDF" and storage.s3_client.calls == [("upload", False)]


async def test_deleting_files_does_not_hold_the_event_loop(storage):
    await storage.delete_document_files("nb", "doc", "pdfs/nb/doc_r.pdf")
    assert storage.s3_client.calls == [("delete", False)]


async def test_fetching_a_pdf_from_r2_does_not_hold_the_event_loop(monkeypatch, storage):
    async def document(*a, **k):
        return types.SimpleNamespace(notebook_id="nb", document_id="doc", file_name="r.pdf")

    monkeypatch.setattr(documents_api, "_document", document)
    monkeypatch.setattr(documents_api, "StorageService", lambda: storage)
    with pytest.raises(HTTPException) as missing:  # the fake R2 writes no file
        await documents_api.get_document_file("doc", None, "alice")
    assert missing.value.status_code == 404 and storage.s3_client.calls == [("download", False)]


# ---------------------------------------------------------------- #19 titles
def test_a_new_notebook_title_is_limited(api):
    assert api.post("/notebooks", json={"title": "x" * 121}).status_code == 422
    created = api.post("/notebooks", json={"title": "  " + "x" * 120 + "  "})
    assert created.status_code == 200 and created.json()["title"] == "x" * 120


def test_a_new_notebook_without_a_title_keeps_the_default(api):
    default = api.post("/notebooks", json={}).json()["title"]
    assert api.post("/notebooks", json={"title": "   "}).json()["title"] == default


# ---------------------------------------------------------------- #27 unforeseen errors and refused tokens
def test_an_unforeseen_error_is_json_with_an_id_and_cors_headers(monkeypatch):
    monkeypatch.setattr(main, "settings", None)  # /health reads an attribute of it: an error nobody planned for
    origin = settings.BACKEND_CORS_ORIGINS[0]

    response = TestClient(main.app, raise_server_exceptions=False).get("/health", headers={"Origin": origin})  # without `with`: no startup, no database

    body = response.json()
    assert response.status_code == 500 and body["request_id"] and "NoneType" not in str(body)
    assert response.headers["access-control-allow-origin"] == origin


async def _through_the_handler(app):
    sent = []

    async def send(message):
        sent.append(message)

    await UnexpectedErrors(app)({"type": "http", "method": "GET", "path": "/x", "headers": []}, None, send)
    return sent


async def test_an_error_after_the_answer_started_is_not_answered_twice():
    async def half_answered(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("broke while streaming")

    with pytest.raises(RuntimeError):
        await _through_the_handler(half_answered)


async def test_a_normal_answer_passes_untouched():
    async def fine(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})

    assert [m["status"] for m in await _through_the_handler(fine)] == [204]


class Sessions:
    """The account behind a token, as UserRepository returns it."""
    user = None

    def __init__(self, db):
        pass

    async def get_by_id(self, user_id):
        return self.user if self.user and self.user.user_id == user_id else None


@pytest.fixture
def session(monkeypatch):
    Sessions.user = UserRecord(user_id="alice", email="alice@example.com", username="alice", hashed_password="x")
    monkeypatch.setattr(deps, "UserRepository", Sessions)
    return Sessions


async def test_no_token_is_a_guest():
    assert await deps.get_optional_user_id(None, None) is None


async def test_a_valid_token_names_its_account(session):
    assert await deps.get_optional_user_id(create_access_token("alice"), None) == "alice"


async def _status_of_a_token(token):
    """What both ways of reading a token answer; each must refuse the same tokens."""
    codes = set()
    for dependency in (deps.get_optional_user_id, deps.get_current_user):
        with pytest.raises(HTTPException) as refused:
            await dependency(token, None)
        codes.add(refused.value.status_code)
    return codes


@pytest.mark.parametrize("token", [create_access_token("alice", timedelta(minutes=-1)), "not-a-token"])
async def test_a_sent_token_that_is_expired_or_forged_is_refused(session, token):
    assert await _status_of_a_token(token) == {401}


# ---------------------------------------------------------------- #22 sessions end when they should
async def test_a_password_change_ends_the_earlier_sessions(session):
    token = create_access_token("alice")
    assert await deps.get_optional_user_id(token, None) == "alice"
    session.user.token_version = 1
    assert await _status_of_a_token(token) == {401}


async def test_a_token_of_the_current_version_still_works(session):
    session.user.token_version = 4
    assert (await deps.get_current_user(create_access_token("alice", version=4), None)).user_id == "alice"


async def test_a_locked_account_cannot_use_its_token(session):
    session.user.is_active = False
    assert await _status_of_a_token(create_access_token("alice")) == {403}


async def test_a_deleted_account_cannot_use_its_token(session):
    session.user = None
    assert await _status_of_a_token(create_access_token("alice")) == {401}


async def test_sessions_from_before_this_change_keep_working(session):
    older = jwt.encode({"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert await deps.get_optional_user_id(older, None) == "alice"


async def test_storing_a_new_password_moves_the_token_version():
    seen = {}

    class Collection:
        async def update_one(self, query, update):
            seen.update(query=query, update=update)
            return types.SimpleNamespace(modified_count=1)

    repo = UserRepository.__new__(UserRepository)
    repo.collection = Collection()
    assert await repo.update_password("alice", "new-hash") is True
    assert seen["update"]["$inc"] == {"token_version": 1} and seen["update"]["$set"]["hashed_password"] == "new-hash"


def test_a_sign_in_token_carries_the_accounts_version():
    user = UserRecord(user_id="u", email="a@example.com", username="alice", hashed_password="x", token_version=3)
    claims = jwt.decode(auth_api._token_response(user).access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["ver"] == 3


def test_changing_the_password_keeps_this_device_signed_in(auth, password_work):
    body = {"old_password": "the-right-password", "new_password": "a-new-long-password"}
    token = auth.post("/api/v1/auth/change-password", json=body).json()["access_token"]
    assert jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["ver"] == 1


# ---------------------------------------------------------------- #23 an answer must not tell which accounts exist
async def test_signing_in_to_an_unknown_account_costs_a_password_check(monkeypatch):
    checked = []
    monkeypatch.setattr(auth_api, "verify_password", lambda plain, hashed: checked.append(plain) or True)

    class Nobody(_SignIns):
        async def get_by_email_or_username(self, identifier):
            return None

    with pytest.raises(HTTPException) as refused:
        await auth_api._authenticate(Nobody(), "nobody", "a-guess", "10.0.0.1")
    assert refused.value.status_code == 401 and checked == ["a-guess"]  # same work as a real account; a match still does not sign anyone in


# ---------------------------------------------------------------- #25 the browser receives only what the interface shows
@pytest.fixture
def read_api(monkeypatch):
    async def allowed(*a, **k):
        return None

    for module in (chat_api, documents_api):
        monkeypatch.setattr(module, "require_notebook", allowed)
    app = FastAPI()
    app.include_router(chat_api.router)
    app.include_router(documents_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_optional_user_id] = lambda: "alice"
    return TestClient(app)


def _stored(cls, records):
    class Repository:
        def __init__(self, db):
            pass

    for name, value in records.items():
        async def answer(self, *a, _value=value, **k):
            return _value

        setattr(Repository, name, answer)
    return Repository


def test_messages_carry_no_internal_details(read_api, monkeypatch):
    message = MessageRecord(
        message_id="m", notebook_id="nb", role="assistant", content="ok",
        citations=[CitationItem(citation_id="c", chunk_id="internal-chunk", document_id="d", page=2, snippet="s", score=0.91, cited=True)],
        trace_info={"understood": "AMD 2023", "alternatives": [{"document_id": "d2", "label": "Intel"}], "plan": "internal-plan", "prompt_version": "v2"},
        token_usage={"total_tokens": 5}, latency_ms=9, model_used="internal-model",
    )
    monkeypatch.setattr(chat_api, "ChatRepository", _stored("ChatRepository", {"get_messages": [message]}))

    response = read_api.get("/chat/messages/nb")

    body = response.json()[0]
    assert set(body) == {"message_id", "notebook_id", "role", "content", "citations", "understood", "alternatives", "created_at"}
    assert set(body["citations"][0]) == {"citation_id", "document_id", "page", "snippet", "cited"}
    assert body["understood"] == "AMD 2023" and body["alternatives"] == [{"document_id": "d2", "label": "Intel"}]
    assert not any(word in response.text for word in ("internal-chunk", "internal-plan", "internal-model", "prompt_version"))


def test_documents_carry_no_internal_details(read_api, monkeypatch):
    document = DocumentRecord(
        document_id="d", notebook_id="nb", file_name="r.pdf", file_size_bytes=1, file_path="pdfs/nb/internal-path.pdf", file_hash="internal-hash", status="ready",
        parsing_engine="pymupdf_fallback", catalog_confirmed_by="internal-user",
        metadata=DocumentMetadata(company_name="AMD", catalog_source="internal-source", catalog_history=[{"by": "internal-user"}]),
    )
    monkeypatch.setattr(documents_api, "DocumentRepository", _stored("DocumentRepository", {"get_by_notebook": [document]}))

    response = read_api.get("/documents/notebook/nb")

    body = response.json()[0]
    assert set(body) == {"document_id", "notebook_id", "file_name", "file_size_bytes", "page_count", "status", "metadata", "error_message", "tables_may_be_inaccurate", "created_at"}
    assert set(body["metadata"]) == {"company_name", "ticker", "report_type", "fiscal_year", "fiscal_quarter", "catalog_unverified", "catalog_confirmed", "user_override_unverified"}
    assert body["tables_may_be_inaccurate"] is True and not any(word in response.text for word in ("internal-", "pymupdf"))


def test_a_clean_document_is_not_flagged(read_api, monkeypatch):
    document = DocumentRecord(document_id="d", notebook_id="nb", file_name="r.pdf", file_size_bytes=1, file_path="p", parsing_engine="docling")
    monkeypatch.setattr(documents_api, "DocumentRepository", _stored("DocumentRepository", {"get_by_notebook": [document]}))
    assert read_api.get("/documents/notebook/nb").json()[0]["tables_may_be_inaccurate"] is False


def test_a_job_carries_no_internal_details(read_api, monkeypatch):
    job = IngestionJobRecord(job_id="j", document_id="d", notebook_id="nb", worker_id="internal-host", stage="docling", error_log="internal-trace", timings={"parse": 1.0})
    monkeypatch.setattr(documents_api, "IngestionJobRepository", _stored("IngestionJobRepository", {"get_by_id": job}))

    response = read_api.get("/documents/jobs/j")

    assert set(response.json()) == {"job_id", "document_id", "notebook_id", "status", "progress_percent"} and "internal-" not in response.text


def test_a_notebook_carries_no_internal_details(api):
    body = api.post("/notebooks/guest").json()
    assert set(body) == {"notebook_id", "title", "message_count", "created_at", "updated_at"}


# ---------------------------------------------------------------- #21 no sign-in token in an address
def test_no_route_takes_a_token_in_its_address():
    addresses = [route.path for route in documents_api.router.routes]
    assert "/documents/{document_id}/file" in addresses and not [a for a in addresses if "token" in a]


def test_a_pdf_address_with_a_token_signs_nobody_in(monkeypatch):
    seen = []

    async def document(db, document_id, user_id, write=False):
        seen.append(user_id)
        raise HTTPException(status_code=403)

    monkeypatch.setattr(documents_api, "_document", document)
    app = FastAPI()
    app.include_router(documents_api.router)
    app.dependency_overrides[get_database] = lambda: None
    token = create_access_token("alice")

    assert TestClient(app).get(f"/documents/d/file?token={token}").status_code == 403
    assert seen == [None]  # the token in the address was ignored
