"""The admin review queue (owner 19/11): answers with a problem go to the admin on their own, not only when a user presses "Report wrong figures";
the dashboard can be narrowed to one user. One table defines every problem as a MongoDB condition: the queue's query and each answer's labels both
come from it, so they cannot disagree."""
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.admin import review as R

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)


def _answer(i, notebook="nb_u1", **fields):
    doc = {"message_id": f"m{i}", "notebook_id": notebook, "role": "assistant", "message_index": 2 * i + 1, "content": f"answer {i}",
           "created_at": NOW - timedelta(hours=i), "latency_ms": 9000, "trace_info": {"intent": "retrieval_rag", "review": {"outcome": "accepted"},
                                                                                      "answer_meta": {"status": "answered"}, "degraded": []}}
    for path, value in fields.items():
        node = doc
        *head, last = path.split("__")
        for key in head:
            node = node.setdefault(key, {})
        node[last] = value
    return doc


# ------------------------------------------------------------------ which answers have a problem, and which
@pytest.mark.parametrize("fields, label", [
    ({"user_rating": -1}, "user_report"),
    ({"trace_info__review__outcome": "annotated", "trace_info__verification__passed": True}, "warning"),
    # owner 19/11: untraced figures and mismatched citations are no longer shown to the user; the trace keeps them and the admin gets them here
    ({"trace_info__verification__passed": False}, "not_traced"),
    ({"trace_info__review__outcome": "blocked"}, "blocked"),
    ({"trace_info__answer_meta__status": "not_found"}, "not_found"),
    ({"trace_info__answer_meta__status": "partial"}, "partial"),
    ({"trace_info__degraded": ["rerank_deadline"]}, "degraded"),
    ({"trace_info__intent": "period_unavailable"}, "refused"),
    ({"trace_info__intent": "unsupported_language"}, "refused"),
    ({"trace_info__intent": "refuse_advice"}, "safety"),
    ({"latency_ms": 75000}, "slow"),
])
def test_each_problem_gets_its_label(fields, label):
    assert R.problem_labels(_answer(1, **fields)) == [label]


def test_a_clean_answer_has_no_label_and_problems_add_up():
    assert R.problem_labels(_answer(1)) == []
    labels = R.problem_labels(_answer(1, user_rating=-1, latency_ms=90000, trace_info__answer_meta__status="partial"))
    assert labels == ["user_report", "partial", "slow"]  # the table's order


def test_the_condition_of_a_label_matches_exactly_the_answers_it_labels():
    docs = [_answer(1), _answer(2, user_rating=-1), _answer(3, trace_info__intent="refuse_political"), _answer(4, trace_info__degraded=["plan_deadline"])]
    for label in R.LABELS:
        assert [d["message_id"] for d in docs if R.matches(R.PROBLEMS[label], d)] == [d["message_id"] for d in docs if label in R.problem_labels(d)]


# ------------------------------------------------------------------ the queue
class FakeCollection:
    """find / count_documents over a list, with the operators the review filters use (R.matches)."""

    def __init__(self, docs):
        self.docs = docs

    def find(self, query, projection=None):
        return FakeCursor([d for d in self.docs if R.matches(query, d)])

    async def count_documents(self, query):
        return sum(1 for d in self.docs if R.matches(query, d))

    async def update_one(self, query, update):
        hit = [d for d in self.docs if R.matches(query, d)]
        for d in hit[:1]:
            for k, v in update.get("$set", {}).items():
                d[k] = v
            for k in update.get("$unset", {}):
                d.pop(k, None)
        return type("Result", (), {"matched_count": len(hit[:1])})()


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction):
        self.docs = sorted(self.docs, key=lambda d: d.get(key) or NOW, reverse=direction < 0)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, n=None):
        return self.docs


class FakeDB(dict):
    def __getitem__(self, name):
        return self.setdefault(name, FakeCollection([]))


def _db(messages):
    db = FakeDB()
    db["messages"] = FakeCollection(messages + [{"notebook_id": m["notebook_id"], "role": "user", "message_index": m["message_index"] - 1,
                                                 "content": f"question of {m['message_id']}"} for m in messages])
    db["notebooks"] = FakeCollection([{"notebook_id": "nb_u1", "owner_type": "user", "owner_id": "u1", "title": "A"},
                                      {"notebook_id": "nb_u2", "owner_type": "user", "owner_id": "u2", "title": "B"},
                                      {"notebook_id": "nb_g", "owner_type": "guest", "owner_id": "g1", "title": "G"}])
    db["users"] = FakeCollection([{"user_id": "u1", "username": "lan"}, {"user_id": "u2", "username": "minh"}])
    return db


MESSAGES = [_answer(1), _answer(2, user_rating=-1), _answer(3, "nb_u2", trace_info__answer_meta__status="not_found"),
            _answer(4, "nb_g", trace_info__intent="period_unavailable"), _answer(5, "nb_u2", latency_ms=80000, trace_info__review__outcome="annotated",
                    trace_info__verification__passed=False),
            _answer(40 * 24, trace_info__answer_meta__status="partial")]  # 40 days old: outside a 14-day window


async def test_the_queue_lists_open_problem_answers_of_the_window_newest_first_with_their_labels_and_question():
    out = await R.review_queue(_db([dict(m) for m in MESSAGES]), days=14, now=NOW)
    assert [i["message_id"] for i in out["items"]] == ["m2", "m3", "m4", "m5"]
    assert out["items"][0]["labels"] == ["user_report"] and out["items"][0]["question"] == "question of m2"
    assert out["items"][2]["owner_type"] == "guest" and out["items"][3]["labels"] == ["warning", "not_traced", "slow"]
    assert out["counts"] == {"user_report": 1, "warning": 1, "not_traced": 1, "blocked": 0, "not_found": 1, "partial": 0, "degraded": 0, "refused": 1, "safety": 0, "slow": 1}
    assert out["open_total"] == 4


async def test_the_queue_narrows_to_a_label_a_user_or_the_guests():
    db = _db([dict(m) for m in MESSAGES])
    assert [i["message_id"] for i in (await R.review_queue(db, days=14, label="not_found", now=NOW))["items"]] == ["m3"]
    assert [i["message_id"] for i in (await R.review_queue(db, days=14, user="u2", now=NOW))["items"]] == ["m3", "m5"]
    assert [i["message_id"] for i in (await R.review_queue(db, days=14, user="guests", now=NOW))["items"]] == ["m4"]


async def test_a_reviewed_answer_leaves_the_open_queue_and_can_be_reopened():
    db = _db([dict(m) for m in MESSAGES])
    assert await R.set_review(db, "m3", "ok", "figures checked, page 37", reviewer="admin", now=NOW)
    open_ids = [i["message_id"] for i in (await R.review_queue(db, days=14, now=NOW))["items"]]
    done = (await R.review_queue(db, days=14, status="reviewed", now=NOW))["items"]
    assert "m3" not in open_ids and [i["message_id"] for i in done] == ["m3"]
    assert done[0]["review"] == {"status": "ok", "note": "figures checked, page 37", "by": "admin", "at": NOW}
    assert await R.set_review(db, "m3", "open", "", reviewer="admin", now=NOW)
    assert "m3" in [i["message_id"] for i in (await R.review_queue(db, days=14, now=NOW))["items"]]
    assert not await R.set_review(db, "nope", "ok", "", reviewer="admin", now=NOW)


async def test_the_user_scope_of_the_dashboard():
    db = _db([])
    assert await R.user_scope(db, None) == {}
    assert await R.user_scope(db, "u1") == {"notebook_id": {"$in": ["nb_u1"]}}
    assert await R.user_scope(db, "guests") == {"notebook_id": {"$in": ["nb_g"]}}


# ------------------------------------------------------------------ the API
from types import SimpleNamespace  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.infrastructure.database.mongodb import get_database  # noqa: E402
from app.modules.admin import admin as admin_api  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    calls = []

    async def queue(db, **kw):
        calls.append(("queue", kw))
        return {"items": [], "counts": {}, "open_total": 0, "window_days": kw["days"]}

    async def mark(db, message_id, status, note, reviewer):
        calls.append(("mark", message_id, status, note, reviewer))
        return message_id != "missing"

    async def build(db, days, user=None):
        calls.append(("overview", days, user))
        return {"window_days": days}

    async def services():
        return {}

    monkeypatch.setattr(admin_api, "review_queue", queue)
    monkeypatch.setattr(admin_api, "set_review", mark)
    monkeypatch.setattr(admin_api, "build_overview", build)
    async def waiting(db, days, user=None):
        return 3

    monkeypatch.setattr(admin_api, "check_services", services)
    monkeypatch.setattr(admin_api, "open_count", waiting)
    app = FastAPI()
    app.include_router(admin_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[admin_api.require_admin] = lambda: SimpleNamespace(username="admin")
    c = TestClient(app)
    c.calls = calls
    return c


def test_the_queue_route_passes_its_filters_and_refuses_unknown_ones(client):
    assert client.get("/auth/admin/review?label=not_found&user=u2&status=reviewed&days=30").status_code == 200
    assert client.calls[-1] == ("queue", {"days": 30, "label": "not_found", "user": "u2", "status": "reviewed"})
    assert client.get("/auth/admin/review").status_code == 200
    assert client.calls[-1] == ("queue", {"days": 14, "label": None, "user": None, "status": "open"})
    assert [client.get(f"/auth/admin/review?{q}").status_code for q in ("label=banana", "status=closed", "days=91")] == [422, 422, 422]


def test_the_review_route_records_who_reviewed(client):
    assert client.post("/auth/admin/review/m3", json={"status": "needs_fix", "note": "wrong year"}).json() == {"success": True}
    assert client.calls[-1] == ("mark", "m3", "needs_fix", "wrong year", "admin")
    assert client.post("/auth/admin/review/missing", json={"status": "ok"}).status_code == 404
    assert client.post("/auth/admin/review/m3", json={"status": "great"}).status_code == 422


def test_the_overview_can_be_narrowed_to_one_user_and_counts_the_waiting_answers(client):
    assert client.get("/auth/admin/overview?user=u1").json()["review_open"] == 3
    assert client.calls[-1] == ("overview", 14, "u1")


async def test_the_waiting_count_is_the_open_queue():
    db = _db([dict(m) for m in MESSAGES])
    assert await R.open_count(db, 14, now=NOW) == 4 and await R.open_count(db, 14, "u2", now=NOW) == 2
