"""Sign-in cookie, sign-out that really ends a session, security headers, and bugs #20, #24, #26 (no database, no network: everything outside the code under test is faked)."""
import asyncio
from datetime import timedelta
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
import pytest

from app import main
from app.api_router import api_v1_router
from app.core.config import settings
from app.core.security import create_access_token
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.admin import admin as admin_api
from app.modules.auth import auth as auth_api
from app.modules.auth.user import UserRecord
from app.modules.auth.user_repo import UserRepository
from app.modules.retrieval import retrieval as retrieval_api
from app.services.email_service import EmailService
from app.shared import deps, health
from app.shared.deps import get_current_user


def _claims(token):
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


class Accounts:
    """The users collection, in memory: the same rules as UserRepository."""
    user = None
    taken_email = taken_username = False

    def __init__(self, db):
        pass

    async def get_by_id(self, user_id):
        return self.user if self.user and self.user.user_id == user_id else None

    async def get_by_email(self, email):
        return self.user if self.taken_email else None

    async def get_by_username(self, username):
        return self.user if self.taken_username else None

    async def get_by_email_or_username(self, identifier):
        return self.user

    async def save_user(self, user):
        return "id"

    async def update_last_login(self, user_id):
        return True

    async def revoke_token(self, user_id, token_id):
        self.user.revoked_token_ids.append(token_id)
        return True


@pytest.fixture
def client(monkeypatch):
    Accounts.user = UserRecord(user_id="alice", email="alice@example.com", username="alice", hashed_password="x")
    Accounts.taken_email = Accounts.taken_username = False
    monkeypatch.setattr(auth_api, "UserRepository", Accounts)
    monkeypatch.setattr(deps, "UserRepository", Accounts)
    monkeypatch.setattr(auth_api, "verify_password", lambda plain, hashed: plain == "the-right-password")
    monkeypatch.setattr(auth_api.email_service, "send_account_confirmation", lambda **k: True)
    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api/v1")
    app.dependency_overrides[get_database] = lambda: None
    return TestClient(app, raise_server_exceptions=False)


SIGN_IN = {"identifier": "alice", "password": "the-right-password"}
NEW_ACCOUNT = {"email": "new@example.com", "username": "new_user", "password": "a-good-password"}


def _cookie_of(response):
    return response.headers["set-cookie"]


# ---------------------------------------------------------------- the sign-in token lives where page scripts cannot read it
@pytest.mark.parametrize("path, body", [("/api/v1/auth/login-json", SIGN_IN), ("/api/v1/auth/register", NEW_ACCOUNT)])
def test_signing_in_sets_a_cookie_scripts_cannot_read(client, path, body):
    cookie = _cookie_of(client.post(path, json=body)).lower()
    assert cookie.startswith(f"{deps.SESSION_COOKIE}=") and "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    assert "secure" not in cookie  # plain http on this machine: a Secure cookie would not be stored by every browser


def test_the_cookie_is_secure_over_https(client):
    secure = TestClient(client.app, base_url="https://testserver")
    assert "secure" in _cookie_of(secure.post("/api/v1/auth/login-json", json=SIGN_IN)).lower()


def test_the_cookie_signs_the_browser_in(client):
    token = client.post("/api/v1/auth/login-json", json=SIGN_IN).json()["access_token"]
    client.cookies.clear()
    assert client.get("/api/v1/auth/me", headers={"Cookie": f"{deps.SESSION_COOKIE}={token}"}).status_code == 200


def test_a_refused_cookie_is_removed_so_the_browser_can_continue_as_a_guest(client):
    response = client.get("/api/v1/auth/me", headers={"Cookie": f"{deps.SESSION_COOKIE}=not-a-token"})
    assert response.status_code == 401 and "max-age=0" in _cookie_of(response).lower() and _cookie_of(response).startswith(f"{deps.SESSION_COOKIE}=")


def test_every_token_has_its_own_id():
    assert _claims(create_access_token("alice"))["jti"] != _claims(create_access_token("alice"))["jti"]


# ---------------------------------------------------------------- signing out ends that session on the server
def test_signing_out_ends_the_token_and_removes_the_cookie(client):
    token = client.post("/api/v1/auth/login-json", json=SIGN_IN).json()["access_token"]
    client.cookies.clear()
    header = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=header).status_code == 200

    response = client.post("/api/v1/auth/logout", headers=header)

    assert response.status_code == 200 and "max-age=0" in _cookie_of(response).lower()
    assert client.get("/api/v1/auth/me", headers=header).status_code == 401


def test_signing_out_leaves_the_other_devices_signed_in(client):
    laptop = {"Authorization": f"Bearer {create_access_token('alice')}"}
    phone = {"Authorization": f"Bearer {create_access_token('alice')}"}
    client.post("/api/v1/auth/logout", headers=phone)
    assert client.get("/api/v1/auth/me", headers=laptop).status_code == 200


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer not-a-token"}])
def test_signing_out_without_a_valid_token_still_answers(client, headers):
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200


async def test_the_list_of_ended_sessions_cannot_grow_without_limit():
    seen = {}

    class Collection:
        async def update_one(self, query, update):
            seen.update(update)
            return types.SimpleNamespace(modified_count=1)

    repo = UserRepository.__new__(UserRepository)
    repo.collection = Collection()
    assert await repo.revoke_token("alice", "token-1") is True
    assert seen["$push"]["revoked_token_ids"] == {"$each": ["token-1"], "$slice": -UserRepository.REVOKED_TOKENS_KEPT}


# ---------------------------------------------------------------- /register cannot be used to list the accounts
@pytest.mark.parametrize("taken", ["taken_email", "taken_username"])
def test_a_taken_email_and_a_taken_username_look_alike(client, monkeypatch, taken):
    monkeypatch.setattr(Accounts, taken, True)
    response = client.post("/api/v1/auth/register", json=NEW_ACCOUNT)
    assert response.status_code == 400 and response.json()["detail"] == auth_api.ACCOUNT_NOT_AVAILABLE


def test_probing_for_taken_accounts_is_limited(client, monkeypatch):
    monkeypatch.setattr(Accounts, "taken_email", True)
    codes = [client.post("/api/v1/auth/register", json=NEW_ACCOUNT).status_code for _ in range(auth_api.REGISTER_TAKEN_PER_IP + 1)]
    assert codes == [400] * auth_api.REGISTER_TAKEN_PER_IP + [429]


def test_successful_registrations_do_not_use_up_the_limit(client):
    assert {client.post("/api/v1/auth/register", json=NEW_ACCOUNT).status_code for _ in range(auth_api.REGISTER_TAKEN_PER_IP + 2)} == {200}


# ---------------------------------------------------------------- the emailed link
def test_the_reset_email_keeps_the_code_out_of_the_link(monkeypatch):
    service, sent = EmailService(), {}
    monkeypatch.setattr(service, "send_email", lambda to, subject, html, text=None: sent.update(html=html) or True)
    service.send_password_reset_otp("a@example.com", "483920")
    assert "483920" in sent["html"] and "otp=" not in sent["html"]


# ---------------------------------------------------------------- security headers
def test_every_api_answer_has_the_security_headers():
    response = TestClient(main.app, raise_server_exceptions=False).get("/api/v1/auth/tiers")
    assert response.headers["x-content-type-options"] == "nosniff" and response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer" and response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_the_api_documentation_page_can_still_load_its_scripts():
    assert "content-security-policy" not in TestClient(main.app, raise_server_exceptions=False).get("/docs").headers


def test_https_is_remembered_only_over_https():
    plain = TestClient(main.app, raise_server_exceptions=False).get("/api/v1/auth/tiers")
    secure = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False).get("/api/v1/auth/tiers")
    assert "strict-transport-security" not in plain.headers and "max-age" in secure.headers["strict-transport-security"]


# ---------------------------------------------------------------- #24 the health numbers are real
class Answers:
    def __init__(self, delay=0.0, broken=False):
        self.delay, self.broken = delay, broken

    async def _answer(self, *a, **k):
        await asyncio.sleep(self.delay)
        if self.broken:
            raise ConnectionError("down")
        return {}

    command = get_collections = _answer


def _services(monkeypatch, mongo, qdrant):
    monkeypatch.setattr(health.MongoManager, "db", mongo)
    monkeypatch.setattr(health.QdrantManager, "client", qdrant)


def _health():
    return TestClient(main.app, raise_server_exceptions=False).get("/health")


def test_health_is_green_only_when_both_services_answer(monkeypatch):
    _services(monkeypatch, Answers(), Answers())
    response = _health()
    assert response.status_code == 200 and response.json()["status"] == "healthy"


@pytest.mark.parametrize("mongo, qdrant, field", [(Answers(broken=True), Answers(), "database"), (Answers(), Answers(broken=True), "vector_search"), (None, Answers(), "database")])
def test_health_reports_a_service_that_does_not_answer(monkeypatch, mongo, qdrant, field):
    _services(monkeypatch, mongo, qdrant)
    response = _health()
    assert response.status_code == 503 and response.json()["status"] == "unhealthy" and response.json()[field] == "disconnected"


def test_a_service_that_hangs_counts_as_down(monkeypatch):
    monkeypatch.setattr(health, "PING_TIMEOUT_SECONDS", 0.01)
    _services(monkeypatch, Answers(delay=1.0), Answers())
    assert _health().status_code == 503


class Stats:
    def __init__(self, db):
        pass

    async def get_admin_dashboard_stats(self):
        return {}


async def test_the_dashboard_shows_a_measured_latency(monkeypatch):
    monkeypatch.setattr(admin_api, "UserRepository", Stats)
    _services(monkeypatch, Answers(delay=0.03), Answers())
    performance = (await admin_api.get_admin_dashboard(None, None))["system_performance"]
    assert performance["status"] == "healthy" and performance["latency_ms"] >= 25 and performance["database"] == "MongoDB Connected"


async def test_the_dashboard_shows_a_database_that_is_down(monkeypatch):
    monkeypatch.setattr(admin_api, "UserRepository", Stats)
    _services(monkeypatch, Answers(broken=True), Answers())
    performance = (await admin_api.get_admin_dashboard(None, None))["system_performance"]
    assert performance["status"] == "unhealthy" and performance["latency_ms"] is None and performance["database"] == "MongoDB Unreachable"


# ---------------------------------------------------------------- #26 only plans that exist
@pytest.fixture
def admin_client(monkeypatch):
    class Users:
        def __init__(self, db):
            pass

        async def update_user_tier(self, user_id, tier):
            return True

    monkeypatch.setattr(admin_api, "UserRepository", Users)
    app = FastAPI()
    app.include_router(admin_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[admin_api.require_admin] = lambda: None
    return TestClient(app)


@pytest.mark.parametrize("tier, status", [("banana", 422), ("", 422), ("guest", 200), ("user", 200), ("admin", 200)])
def test_only_existing_plans_can_be_assigned(admin_client, tier, status):
    assert admin_client.post("/auth/admin/update-tier", json={"user_id": "u", "tier": tier}).status_code == status


# ---------------------------------------------------------------- #20 the inspection routes are for administrators
@pytest.fixture
def inspection(monkeypatch):
    caller = {"user": UserRecord(user_id="u", email="u@example.com", username="user", hashed_password="x")}

    async def allowed(*a, **k):
        return None

    class Search:
        def __init__(self, db, qdrant):
            pass

        async def retrieve_hydrated_chunks(self, **kw):
            return []

    monkeypatch.setattr(retrieval_api, "require_notebook", allowed)
    monkeypatch.setattr(retrieval_api, "HybridSearchService", Search)
    app = FastAPI()
    app.include_router(retrieval_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_qdrant_client] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: caller["user"]
    client = TestClient(app)
    client.caller = caller
    return client


@pytest.mark.parametrize("path, body", [("/retrieval/search", {"notebook_id": "n", "query": "q"}), ("/retrieval/research", {"notebook_id": "n", "query": "q"})])
def test_ordinary_accounts_cannot_use_the_inspection_routes(inspection, path, body):
    assert inspection.post(path, json=body).status_code == 403


def _as_admin(inspection):
    inspection.caller["user"] = UserRecord(user_id="a", email="a@example.com", username="admin", hashed_password="x", role="admin")


def test_an_administrator_can_search(inspection):
    _as_admin(inspection)
    assert inspection.post("/retrieval/search", json={"notebook_id": "n", "query": "q"}).status_code == 200


@pytest.mark.parametrize("top_k, status", [(0, 422), (51, 422), (1, 200), (50, 200)])
def test_the_number_of_results_is_bounded(inspection, top_k, status):
    _as_admin(inspection)
    assert inspection.post("/retrieval/search", json={"notebook_id": "n", "query": "q", "top_k": top_k}).status_code == status
