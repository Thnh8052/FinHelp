"""Step 5 of docs/VERSION_4/GUARDRAILS_REDESIGN_2026-11-19.md: one ceiling on the tokens every chat question of the day may spend, all accounts and
guests together (red-team 19/11, LLM10 unbounded consumption: per-account limits alone let many accounts spend without end)."""
from app.core.config import settings
from app.core.error_codes import Code
from app.modules.chat import chat as chat_api
from tests.test_acl import GUEST_ID, FakeUsage, FakeUsers, ask, client  # noqa: F401  (client is a fixture)


def test_past_the_days_budget_no_question_starts(client, monkeypatch):
    monkeypatch.setattr(settings, "DAILY_TOKEN_BUDGET", 1000)
    FakeUsage.spent = 1000
    FakeUsers.reserved.clear()
    for user, notebook in (("alice", "nb_alice"), (None, GUEST_ID)):
        response = ask(client, user, notebook_id=notebook, document_ids=["d1"])
        assert response.status_code == 429 and response.json()["detail"]["code"] == Code.DAILY_BUDGET_USED  # a quota, like question_quota_used: the interface shows its sentence (a 5xx shows "busy")
        assert 0 < int(response.headers["retry-after"]) <= 24 * 60 * 60  # until the next UTC day
    assert FakeUsers.reserved == []  # refused before any quota is reserved and before any model is called


def test_under_the_budget_questions_go_on(client, monkeypatch):
    monkeypatch.setattr(settings, "DAILY_TOKEN_BUDGET", 1000)
    FakeUsage.spent = 999
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"]).status_code == 500  # Stop: it reached the faked orchestrator


def test_a_budget_of_zero_is_no_ceiling(client, monkeypatch):
    monkeypatch.setattr(settings, "DAILY_TOKEN_BUDGET", 0)
    FakeUsage.spent = 10 ** 12
    assert ask(client, "alice", notebook_id="nb_alice", document_ids=["d1"]).status_code == 500


def test_every_answer_adds_its_tokens_to_the_day(client, monkeypatch):
    async def answered(self, **kw):
        return {"answer": "ok", "intent": "qa", "citations": [], "charged": True,
                "trace": {"llm": {"calls": 3, "prompt_tokens": 16873, "completion_tokens": 1519}}}

    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", answered)
    FakeUsage.spent, FakeUsage.added = 0, []
    assert ask(client, None, notebook_id=GUEST_ID, document_ids=["d1"]).status_code == 200  # a guest's tokens count too
    assert FakeUsage.added == [18392]


def test_the_default_budget_is_on():
    assert type(settings).model_fields["DAILY_TOKEN_BUDGET"].default > 0
