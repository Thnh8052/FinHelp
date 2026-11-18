"""When the model cannot be reached the answer is the fixed apology with the first excerpts, and that apology is never checked. (L22, a repair that
could not reach the model, went with the repair itself: T4, 19/11.)

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
    assert len(calls) == 1 and r["verification"]["passed"]


async def test_an_outage_falls_back_to_the_apology_with_the_excerpts(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    fake_model(orch, monkeypatch, LLMUnavailableError("llm_unavailable"))
    assert (await orch._answer("What was AMD's revenue?", [dict(c) for c in CHUNKS])).startswith(APOLOGY)
