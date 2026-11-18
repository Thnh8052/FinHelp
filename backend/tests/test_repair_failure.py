"""L22: a second writing of the answer (the one repair of the checks) is an extra. When the model cannot be reached for it,
the answer already written stands. Before the fix, `_answer` turned the failure into the fixed apology text ("No answer could be generated right now...")
and the caller accepted that text over the real answer, because the apology has no more issues than the answer had (len(i2) <= len(issues)).

The real `_answer` runs here; only the model call is faked, and production's prompt setting is used."""
import pytest

from app.core.config import settings
from app.modules.chat import orchestrator as orch_mod
from app.modules.generation.llm_client import LLMUnavailableError
from app.modules.query_router.input_policy import Decision
from tests.test_validation import CHUNKS, _orchestrator, _scope

APOLOGY = "Sorry, no answer could be generated right now"


@pytest.fixture(autouse=True)
def _production_settings(monkeypatch):
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4")  # a reply without an answer_meta block counts as answered
    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", False)


def fake_model(orch, monkeypatch, *replies):
    """The real `_answer` runs; the model call gives the replies in turn (the last one repeats) and raises a reply that is an exception. Returns the list of calls."""
    calls = []

    async def generate(question, chunks, notes=None, max_tokens=1500):
        calls.append(len(chunks))
        reply = replies[min(len(calls), len(replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    orch.__dict__.pop("_answer", None)  # the helpers' fake _answer goes
    monkeypatch.setattr(orch_mod, "generate_answer", generate)
    return calls


async def test_a_repair_that_cannot_reach_the_model_leaves_the_answer_already_written(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = fake_model(orch, monkeypatch, "AMD revenue was $99,999 million [1].", LLMUnavailableError("llm_unavailable"))
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 2  # the repair was tried
    assert APOLOGY not in r["answer"] and "$99,999" in r["answer"]  # the real answer stands, not the apology
    assert "⚠️" in r["answer"]  # it was never repaired, so its figure is still flagged
    assert r["verification"]["repaired"] is False and not r["verification"]["passed"] and r["verification"]["first_issues"]


async def test_a_repair_that_works_still_replaces_the_answer(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = fake_model(orch, monkeypatch, "AMD revenue was $99,999 million [1].", "AMD revenue was $25,785 million [1].")
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 2 and "$25,785" in r["answer"] and r["verification"]["repaired"] and r["verification"]["passed"]


async def test_the_apology_for_an_outage_is_not_verified_or_repaired(monkeypatch):
    """The fixed apology shows the first excerpts and a page number ("Page 41"): the number check reads that number as an unverified figure of an answer, and the one repair then
    asks the model again, to rewrite an apology (found 14/11 while fixing the cut replies)."""
    orch, _ = _orchestrator([], monkeypatch)
    calls = fake_model(orch, monkeypatch, LLMUnavailableError("llm_unavailable"))
    chunks = [dict(c, page=41) for c in CHUNKS]  # a page number above 12 that the excerpts do not print

    async def retrieve(query, notebook_id, scope, forced=None):
        return orch_mod.RetrievalResult(scope, {"amd": "AMD", "nv": "NVIDIA"}, [], [], [dict(c) for c in chunks], "targets_planner")

    monkeypatch.setattr(orch, "retrieve", retrieve)
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert r["answer"].startswith("Sorry, no answer could be generated right now") and "⚠️" not in r["answer"]
    assert len(calls) == 1 and not r["verification"]["repaired"] and r["verification"]["passed"]


async def test_the_first_answer_still_falls_back_to_the_apology_and_a_second_writing_can_ask_for_the_error(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    fake_model(orch, monkeypatch, LLMUnavailableError("llm_unavailable"))
    chunks = [dict(c) for c in CHUNKS]
    assert (await orch._answer("What was AMD's revenue?", chunks)).startswith(APOLOGY)  # nothing is written yet: the apology with the excerpts is all there is
    with pytest.raises(LLMUnavailableError):
        await orch._answer("What was AMD's revenue?", chunks, fallback=False)
