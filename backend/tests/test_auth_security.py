"""Auth hardening and the guest / user / admin rules (no database, no network: repositories are faked)."""
from datetime import datetime, timedelta, timezone
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.modules.auth import auth as auth_api
from app.shared import deps
from app.modules.documents import documents as documents_api
from app.shared.deps import get_optional_user_id
from app.api_router import api_v1_router
from app.core.config import Settings, settings
from app.core.security import get_password_hash, verify_password
from app.modules.admin import init_admin
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.documents.document import DocumentRecord
from app.modules.notebooks.notebook import NotebookRecord
from app.modules.auth.user import ADMIN_EMAIL, ADMIN_USER_ID, UserRecord

REAL_PASSWORD = "a-long-real-password"
ADMIN = UserRecord(user_id="usr_admin", email="admin@example.com", username="admin", hashed_password=get_password_hash(REAL_PASSWORD), role="admin")


class FakeUsers:
    def __init__(self, db):
        pass

    async def get_by_email_or_username(self, identifier):
        return ADMIN if identifier in ("admin", ADMIN.email) else None

    async def get_by_email(self, email):
        return ADMIN if email == ADMIN.email else None

    async def update_last_login(self, user_id):
        return True

    async def set_reset_token(self, email, token, expires_at):
        return True


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setattr(auth_api, "UserRepository", FakeUsers)
    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api/v1")
    app.dependency_overrides[get_database] = lambda: None
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------- admin account
def test_no_public_endpoint_resets_the_admin(app_client):
    paths = app_client.app.openapi()["paths"]
    assert "/api/v1/auth/login-json" in paths and not [p for p in paths if "setup-admin" in p]
    assert app_client.post("/api/v1/auth/setup-admin").status_code in (404, 405)


@pytest.mark.parametrize("path,body", [("/api/v1/auth/login-json", {"identifier": "admin", "password": None}),
                                       ("/api/v1/auth/login", None)])
def test_admin_has_no_password_shortcut(app_client, path, body):
    def attempt(password):
        if body is None:  # the OAuth2 form endpoint
            return app_client.post(path, data={"username": "admin", "password": password})
        return app_client.post(path, json={**body, "password": password})

    for shortcut in ("admin", "admin123", "Admin@123456"):
        assert attempt(shortcut).status_code == 401
    ok = attempt(REAL_PASSWORD)
    assert ok.status_code == 200 and ok.json()["role"] == "admin"


class ResetUsers:
    """In-memory users collection for the reset-code flow: the same rules as UserRepository (hash stored, tries counted)."""
    user = None

    def __init__(self, db):
        pass

    async def get_by_email_or_username(self, identifier):
        return self.user if identifier in (self.user.username, self.user.email) else None

    async def get_by_email(self, email):
        return self.user if email == self.user.email else None

    async def set_reset_token(self, email, token, expires_at):
        self.user.reset_token, self.user.reset_token_expires_at, self.user.reset_attempts = token, expires_at, 0
        return True

    async def use_reset_attempt(self, email, max_attempts):
        if email != self.user.email or not self.user.reset_token or self.user.reset_attempts >= max_attempts:
            return None
        self.user.reset_attempts += 1
        return self.user

    async def update_password(self, user_id, new_hash):
        self.user.hashed_password, self.user.reset_token = new_hash, None
        return True

    async def update_last_login(self, user_id):
        return True


@pytest.fixture
def reset_flow(monkeypatch):
    """(client, codes): the codes the server "emailed"; the API response is the only other thing the client sees."""
    ResetUsers.user = UserRecord(user_id="usr_a", email="a@example.com", username="alice", hashed_password=get_password_hash(REAL_PASSWORD))
    codes = []
    monkeypatch.setattr(auth_api, "UserRepository", ResetUsers)
    monkeypatch.setattr(auth_api.email_service, "send_password_reset_otp", lambda email, code, *a, **k: codes.append(code) or True)
    monkeypatch.setattr(auth_api.email_service, "send_password_changed_notification", lambda **kw: True)
    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api/v1")
    app.dependency_overrides[get_database] = lambda: None
    return TestClient(app, raise_server_exceptions=False), codes


def _forgot(client, email="a@example.com"):
    return client.post("/api/v1/auth/forgot-password", json={"email": email})


def _reset(client, code, password="brand-new-password"):
    return client.post("/api/v1/auth/reset-password", json={"email": "a@example.com", "otp_code": code, "new_password": password})


@pytest.mark.parametrize("environment", ["development", "production"])
def test_reset_code_is_never_in_the_response(reset_flow, monkeypatch, environment):
    client, codes = reset_flow
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    response = _forgot(client)
    assert response.status_code == 200 and codes and codes[0] not in response.text and "otp" not in response.text.lower()
    assert _forgot(client, "nobody@example.com").json().keys() == response.json().keys()  # unknown emails look the same


def test_forgot_password_gives_every_email_the_same_answer(reset_flow):
    client, _ = reset_flow
    assert _forgot(client).json() == _forgot(client, "nobody@example.com").json()


def test_a_refused_reset_does_not_tell_whether_the_account_exists(reset_flow):
    client, codes = reset_flow
    _forgot(client)
    wrong = "000000" if codes[0] != "000000" else "111111"
    known_wrong_code = _reset(client, wrong)
    unknown_email = client.post("/api/v1/auth/reset-password", json={"email": "nobody@example.com", "otp_code": wrong, "new_password": "brand-new-password"})
    ResetUsers.user.reset_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    expired = _reset(client, codes[0])
    assert {r.status_code for r in (known_wrong_code, unknown_email, expired)} == {400}
    assert known_wrong_code.json() == unknown_email.json() == expired.json()


def test_environment_defaults_to_production():
    assert Settings.model_fields["ENVIRONMENT"].default == "production"


def test_reset_code_is_stored_as_a_hash_and_resets_the_password(reset_flow):
    client, codes = reset_flow
    _forgot(client)
    assert ResetUsers.user.reset_token != codes[0] and codes[0] not in ResetUsers.user.reset_token
    assert _reset(client, codes[0]).status_code == 200
    assert verify_password("brand-new-password", ResetUsers.user.hashed_password)
    assert _reset(client, codes[0]).status_code == 400  # a code works once


def test_reset_code_dies_after_five_wrong_tries(reset_flow):
    client, codes = reset_flow
    _forgot(client)
    wrong = "000000" if codes[0] != "000000" else "111111"
    assert [_reset(client, wrong).status_code for _ in range(5)] == [400] * 5
    assert _reset(client, codes[0]).status_code == 400  # the right code is too late
    assert not verify_password("brand-new-password", ResetUsers.user.hashed_password)
    _forgot(client)  # a fresh code starts with fresh tries
    assert _reset(client, codes[-1]).status_code == 200


def test_reset_requests_are_limited_per_email_and_per_address(reset_flow):
    client, _ = reset_flow
    assert [_forgot(client).status_code for _ in range(4)] == [200, 200, 200, 429]
    assert _forgot(client, "other@example.com").status_code == 200  # another email is another count


def test_login_is_blocked_after_ten_wrong_passwords(reset_flow):
    client, _ = reset_flow

    def attempt(who, password):
        return client.post("/api/v1/auth/login-json", json={"identifier": who, "password": password}).status_code

    assert [attempt("alice", "wrong") for _ in range(10)] == [401] * 10
    assert attempt("alice", REAL_PASSWORD) == 429  # even the right password
    assert attempt("a@example.com", REAL_PASSWORD) == 429  # the email is the same account, not a fresh count


def test_right_password_clears_the_failed_count(reset_flow):
    client, _ = reset_flow
    body = {"identifier": "alice", "password": "wrong"}
    for _ in range(9):
        assert client.post("/api/v1/auth/login-json", json=body).status_code == 401
    assert client.post("/api/v1/auth/login-json", json={**body, "password": REAL_PASSWORD}).status_code == 200
    assert [client.post("/api/v1/auth/login-json", json=body).status_code for _ in range(9)] == [401] * 9


def test_admin_routes_are_closed_to_users_and_guests(app_client):
    assert app_client.get("/api/v1/auth/admin/dashboard").status_code == 401  # a guest
    assert app_client.post("/api/v1/auth/admin/update-tier", json={"user_id": "u", "tier": "user"}).status_code == 401


class _Collection:
    updates: list = []

    async def delete_many(self, *args, **kwargs):
        raise AssertionError("the startup must never delete accounts or notebooks")

    async def update_one(self, query, update):
        _Collection.updates.append((query, update))


class FakeRepo:
    saved: list = []

    def __init__(self, db):
        self.collection = _Collection()

    async def save_user(self, user):
        FakeRepo.saved.append(user)

    async def get_by_id(self, _id):
        return None

    async def save_notebook(self, nb):
        return None


@pytest.fixture
def admin_init(monkeypatch):
    FakeRepo.saved, _Collection.updates = [], []
    for name in ("UserRepository", "NotebookRepository"):
        monkeypatch.setattr(init_admin, name, FakeRepo)
    monkeypatch.setattr(init_admin.MongoManager, "db", object())
    return FakeRepo


async def test_admin_account_needs_an_explicit_password(admin_init, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)
    result = await init_admin.ensure_admin()
    assert result["success"] is False and admin_init.saved == []
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", REAL_PASSWORD)
    result = await init_admin.ensure_admin()
    assert result["success"] is True and "password" not in str(result).lower().replace("admin_password", "")
    assert admin_init.saved[0].role == "admin" and verify_password(REAL_PASSWORD, admin_init.saved[0].hashed_password)
    assert admin_init.saved[0].user_id == ADMIN_USER_ID  # delete_many raises: nothing was deleted on the way


@pytest.mark.parametrize("password, moved", [(REAL_PASSWORD, 0), ("a-different-admin-password", 1)])
async def test_only_a_new_admin_password_ends_the_admins_sessions(admin_init, monkeypatch, password, moved):
    class Existing(FakeRepo):
        async def get_by_id(self, user_id):
            return ADMIN if user_id == ADMIN_USER_ID else None

    monkeypatch.setattr(init_admin, "UserRepository", Existing)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", password)
    await init_admin.ensure_admin()
    query, update = _Collection.updates[0]
    assert query == {"user_id": ADMIN_USER_ID} and update["$inc"] == {"token_version": moved}
    assert ("hashed_password" in update["$set"]) == bool(moved)  # the hash is rewritten only when the password changed


async def test_a_user_who_registered_as_admin_is_never_promoted(admin_init, monkeypatch):
    """The admin is looked up by its own id: a normal account holding the name 'admin' makes the creation fail, it is not taken over."""
    from pymongo.errors import DuplicateKeyError

    class NameTaken(FakeRepo):
        async def save_user(self, user):
            raise DuplicateKeyError("username")

    monkeypatch.setattr(init_admin, "UserRepository", NameTaken)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", REAL_PASSWORD)
    result = await init_admin.ensure_admin()
    assert result["success"] is False and _Collection.updates == []


@pytest.mark.parametrize("username, email", [("Admin", "new@example.com"), ("someone", ADMIN_EMAIL.upper())])
def test_nobody_can_register_the_admins_names(app_client, username, email):
    response = app_client.post("/api/v1/auth/register", json={"email": email, "username": username, "password": REAL_PASSWORD})
    assert response.status_code == 400 and response.json()["detail"]["code"] == auth_api.ACCOUNT_NOT_AVAILABLE


# ---------------------------------------------------------------- settings
def test_secret_key_has_no_default(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_placeholder_secret_is_refused_outside_development():
    placeholder = "change_this_to_a_very_secure_random_secret_key_in_production"
    Settings(_env_file=None, SECRET_KEY=placeholder, ENVIRONMENT="development")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=placeholder, ENVIRONMENT="production")


# ---------------------------------------------------------------- guest: 1 document, user: 5, per notebook
GUEST_NOTEBOOK = "nb_guest_" + "b" * 32


class Stop(Exception):
    """Raised by the faked storage: the upload got past the quota gate."""


def _doc(n, status="ready"):
    return DocumentRecord(document_id=f"d{n}", notebook_id="nb", file_name=f"{n}.pdf", file_size_bytes=1, file_path="x", status=status)


@pytest.fixture
def upload(monkeypatch):
    state = {"user": None, "docs": [], "notebook": NotebookRecord(notebook_id=GUEST_NOTEBOOK, owner_type="guest", owner_id="g", title="g")}

    class Notebooks:
        def __init__(self, db):
            pass

        async def get_by_id(self, _id):
            return state["notebook"]

    class Documents:
        def __init__(self, db):
            pass

        async def get_by_notebook(self, _id):
            return state["docs"]

    class Storage:
        async def save_pdf(self, *args):
            raise Stop()

    class Users:
        def __init__(self, db):
            pass

        async def get_by_id(self, _id):
            return types.SimpleNamespace(role=state.get("role", "user"))

    monkeypatch.setattr(deps, "NotebookRepository", Notebooks)
    monkeypatch.setattr(documents_api, "UserRepository", Users)
    monkeypatch.setattr(documents_api, "DocumentRepository", Documents)
    monkeypatch.setattr(documents_api, "StorageService", Storage)
    app = FastAPI()
    app.include_router(documents_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_qdrant_client] = lambda: None
    app.dependency_overrides[get_optional_user_id] = lambda: state["user"]
    client = TestClient(app, raise_server_exceptions=False)

    def post(notebook_id, content=b"%PDF-1.4"):
        return client.post(f"/documents/upload/{notebook_id}", files={"file": ("r.pdf", content, "application/pdf")}).status_code

    return state, post


def test_guest_may_upload_one_document_only(upload):
    state, post = upload
    assert post(GUEST_NOTEBOOK) == 500  # Stop: an empty notebook passes the gate
    state["docs"] = [_doc(1)]
    assert post(GUEST_NOTEBOOK) == 403
    state["docs"] = [_doc(1, status="failed")]
    assert post(GUEST_NOTEBOOK) == 500  # a failed document does not count: the guest can retry


def test_guest_uploads_stop_at_the_daily_allowance(upload, monkeypatch):
    monkeypatch.setattr(settings, "GUEST_DAILY_UPLOADS", 2)
    _, post = upload
    assert post(GUEST_NOTEBOOK, b"this is only named .pdf") == 400  # a refused file does not use the allowance
    assert [post(GUEST_NOTEBOOK) for _ in range(3)] == [500, 500, 429]  # 500: Stop, the file reached the storage


@pytest.mark.parametrize("role", ["user", "admin"])
def test_every_signed_in_account_may_upload_five_documents(upload, role):
    state, post = upload
    state["user"], state["role"], state["notebook"] = "alice", role, NotebookRecord(notebook_id="nb", owner_id="alice", title="a")
    state["docs"] = [_doc(n) for n in range(4)]
    assert post("nb") == 500
    state["docs"] = [_doc(n) for n in range(5)]
    assert post("nb") == 403


def test_the_document_limit_shown_is_the_one_enforced():
    from app.modules.auth.user import TIER_SPECS

    assert TIER_SPECS["guest"]["max_upload_documents"] == settings.MAX_SELECTED_DOCS_GUEST
    assert TIER_SPECS["user"]["max_upload_documents"] == TIER_SPECS["admin"]["max_upload_documents"] == settings.MAX_SELECTED_DOCS_USER


MB = 1024 * 1024


def _pdf_of(megabytes):
    return b"%PDF-1.4" + b"0" * (megabytes * MB)


@pytest.mark.parametrize("role, limit", [("user", 20), ("admin", 100)])
def test_each_role_has_its_own_file_size_limit(upload, role, limit):
    state, post = upload
    state["user"], state["role"], state["notebook"] = "alice", role, NotebookRecord(notebook_id="nb", owner_id="alice", title="a")
    assert post("nb", _pdf_of(limit - 1)) == 500  # Stop: reached the storage
    assert post("nb", _pdf_of(limit + 1)) == 413


def test_a_guest_file_is_limited_to_five_megabytes(upload):
    _, post = upload
    assert post(GUEST_NOTEBOOK, _pdf_of(4)) == 500
    assert post(GUEST_NOTEBOOK, _pdf_of(6)) == 413


@pytest.mark.parametrize("content", [b"", b"this is only named .pdf", b"<html>%PDF</html>"])
def test_a_file_that_is_not_a_pdf_is_refused_before_storage(upload, content):
    _, post = upload
    assert post(GUEST_NOTEBOOK, content) == 400


async def _through_the_limit(path, headers, method="POST"):
    from app.shared.upload_limit import UploadSizeLimit

    reached, sent = [], []

    async def app(scope, receive, send):
        reached.append(scope["path"])

    async def send(message):
        sent.append(message)

    await UploadSizeLimit(app)({"type": "http", "method": method, "path": path, "headers": headers}, None, send)
    return bool(reached), sent[0]["status"] if sent else None


async def test_an_oversized_upload_is_refused_before_its_body_is_read():
    from app.shared.upload_limit import MAX_UPLOAD_BODY

    path = "/api/v1/documents/upload/nb"
    assert await _through_the_limit(path, [(b"content-length", str(MAX_UPLOAD_BODY + 1).encode())]) == (False, 413)
    assert await _through_the_limit(path, []) == (False, 411)
    assert await _through_the_limit(path, [(b"content-length", b"1000")]) == (True, None)
    assert await _through_the_limit("/api/v1/chat/query", []) == (True, None)  # other routes are untouched


def test_nobody_uploads_into_someone_elses_notebook(upload):
    state, post = upload
    state["user"], state["notebook"] = "bob", NotebookRecord(notebook_id="nb", owner_id="alice", title="a")
    assert post("nb") == 403
