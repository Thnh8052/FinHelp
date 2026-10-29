"""Auth hardening and the guest / user / admin rules (no database, no network: repositories are faked)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1 import auth as auth_api
from app.api.v1 import deps
from app.api.v1 import documents as documents_api
from app.api.v1.deps import get_optional_user_id
from app.api.v1.router import api_v1_router
from app.core.config import Settings, settings
from app.core.security import get_password_hash, verify_password
from app.db import init_admin
from app.db.mongodb import get_database
from app.db.qdrant import get_qdrant_client
from app.models.document import DocumentRecord
from app.models.notebook import NotebookRecord
from app.models.user import UserRecord

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


def test_reset_code_is_shown_only_while_developing(app_client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    dev = app_client.post("/api/v1/auth/forgot-password", json={"email": ADMIN.email}).json()
    assert len(dev["otp_debug"]) == 6 and dev["otp_debug"].isdigit()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert "otp_debug" not in app_client.post("/api/v1/auth/forgot-password", json={"email": ADMIN.email}).json()


def test_admin_routes_are_closed_to_users_and_guests(app_client):
    assert app_client.get("/api/v1/auth/admin/dashboard").status_code == 401  # a guest
    assert app_client.post("/api/v1/auth/admin/update-tier", json={"user_id": "u", "tier": "user"}).status_code == 401


class _Collection:
    async def delete_many(self, *args, **kwargs):
        return type("Result", (), {"deleted_count": 0})()

    async def update_one(self, *args, **kwargs):
        return None


class FakeRepo:
    saved: list = []

    def __init__(self, db):
        self.collection = _Collection()

    async def get_by_username(self, name):
        return None

    async def save_user(self, user):
        FakeRepo.saved.append(user)

    async def get_by_id(self, _id):
        return None

    async def get_session(self, _id):
        return None

    async def save_notebook(self, nb):
        return None

    async def save_session(self, s):
        return None


@pytest.fixture
def admin_init(monkeypatch):
    FakeRepo.saved = []
    for name in ("UserRepository", "NotebookRepository", "ChatRepository"):
        monkeypatch.setattr(init_admin, name, FakeRepo)
    monkeypatch.setattr(init_admin.MongoManager, "db", object())
    return FakeRepo


async def test_admin_account_needs_an_explicit_password(admin_init, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)
    result = await init_admin.setup_admin_and_clean_mocks()
    assert result["success"] is False and admin_init.saved == []
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", REAL_PASSWORD)
    result = await init_admin.setup_admin_and_clean_mocks()
    assert result["success"] is True and "password" not in str(result).lower().replace("admin_password", "")
    assert admin_init.saved[0].role == "admin" and verify_password(REAL_PASSWORD, admin_init.saved[0].hashed_password)


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


def _doc(n, status="completed"):
    return DocumentRecord(document_id=f"d{n}", notebook_id="nb", file_name=f"{n}.pdf", file_size_bytes=1, file_path="x", parsing_status=status)


@pytest.fixture
def upload(monkeypatch):
    state = {"user": None, "docs": [], "notebook": NotebookRecord(notebook_id=GUEST_NOTEBOOK, user_id="guest", title="g")}

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

    monkeypatch.setattr(deps, "NotebookRepository", Notebooks)
    monkeypatch.setattr(documents_api, "DocumentRepository", Documents)
    monkeypatch.setattr(documents_api, "StorageService", Storage)
    app = FastAPI()
    app.include_router(documents_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_qdrant_client] = lambda: None
    app.dependency_overrides[get_optional_user_id] = lambda: state["user"]
    client = TestClient(app, raise_server_exceptions=False)

    def post(notebook_id):
        return client.post(f"/documents/upload/{notebook_id}", files={"file": ("r.pdf", b"%PDF-1.4", "application/pdf")}).status_code

    return state, post


def test_guest_may_upload_one_document_only(upload):
    state, post = upload
    assert post(GUEST_NOTEBOOK) == 500  # Stop: an empty notebook passes the gate
    state["docs"] = [_doc(1)]
    assert post(GUEST_NOTEBOOK) == 403
    state["docs"] = [_doc(1, status="failed")]
    assert post(GUEST_NOTEBOOK) == 500  # a failed document does not count: the guest can retry


def test_signed_in_user_may_upload_five_documents(upload):
    state, post = upload
    state["user"], state["notebook"] = "alice", NotebookRecord(notebook_id="nb", user_id="alice", title="a")
    state["docs"] = [_doc(n) for n in range(4)]
    assert post("nb") == 500
    state["docs"] = [_doc(n) for n in range(5)]
    assert post("nb") == 403


def test_nobody_uploads_into_someone_elses_notebook(upload):
    state, post = upload
    state["user"], state["notebook"] = "bob", NotebookRecord(notebook_id="nb", user_id="alice", title="a")
    assert post("nb") == 403
