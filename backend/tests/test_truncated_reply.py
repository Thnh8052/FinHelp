"""A reply still cut by the token budget at the ceiling is not an answer. Before, chat_completion returned what it had (an empty text, or half of one):
generate_answer turned an empty text into the fixed refusal "the selected reports do not contain this information" with the status not_found, so a question the model could not finish
was told, after up to three long attempts, that its answer was not in the reports; a half text was shown as if complete. Now the call raises LLMTruncatedError (an
LLMUnavailableError, so every caller that already handles an unreachable model handles it), the answer shows a sorry for the system's limit with the first excerpts, and nothing else is
asked of the model for that answer. No model, no network: the model call is faked.
"""
import pytest

from app.core.config import settings
from app.modules.chat import orchestrator as orch_mod
from app.modules.generation import llm_client
from app.modules.generation.llm_client import LLMTruncatedError, LLMUnavailableError
from app.modules.query_router import input_policy, planner
from app.modules.query_router.input_policy import Decision
from tests.test_llm_client import patch, sized
from tests.test_multidoc import CATALOG
from tests.test_repair_failure import fake_model
from tests.test_validation import CHUNKS, _orchestrator, _scope

CUT = "llm_unavailable"


@pytest.fixture(autouse=True)
def _production_settings(monkeypatch):
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4")
    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", False)


# ---------------------------------------------------------------- the client
async def test_a_reply_cut_at_the_ceiling_is_an_error_not_an_empty_answer(monkeypatch):
    seen = sized(monkeypatch, needs=10 ** 9)
    with pytest.raises(LLMTruncatedError):
        await llm_client.chat_completion([{"role": "user", "content": "q"}])
    assert issubclass(LLMTruncatedError, LLMUnavailableError)  # every caller that handles an unreachable model handles this one
    assert len(seen) <= 2 and max(seen) <= settings.LLM_MAX_TOKENS_CEILING


async def test_half_a_text_cut_at_the_ceiling_is_not_returned_as_an_answer(monkeypatch):
    patch(monkeypatch, [("length", "Revenue was 10")] * 3)
    with pytest.raises(LLMTruncatedError):
        await llm_client.chat_completion([{"role": "user", "content": "q"}])


async def test_a_cut_reply_that_a_larger_budget_finishes_is_still_returned(monkeypatch):
    patch(monkeypatch, [("length", ""), ("stop", "Done.")])
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}]) == "Done."


# ---------------------------------------------------------------- the answer
async def test_the_first_answer_that_cannot_be_finished_says_sorry_for_the_limit_and_shows_the_excerpts(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    fake_model(orch, monkeypatch, LLMTruncatedError(CUT))
    chunks = [dict(c) for c in CHUNKS]
    en = await orch._answer("What was AMD's revenue?", chunks)
    assert en.startswith("Sorry, this question is beyond what the system can finish") and "splitting it" in en and "Net revenue 2024 25,785" in en
    assert "do not contain" not in en and "not found" not in en.lower()  # it never claims the reports lack the information
    vi = await orch._answer("Doanh thu của AMD là bao nhiêu?", chunks)
    assert vi.startswith("Xin lỗi, câu hỏi này vượt quá giới hạn xử lý của hệ thống") and "chia nhỏ" in vi and "Net revenue 2024 25,785" in vi
    fake_model(orch, monkeypatch, LLMUnavailableError(CUT))  # an outage keeps its own sentence
    assert (await orch._answer("What was AMD's revenue?", chunks)).startswith("No answer could be generated right now")


async def test_a_question_whose_answer_cannot_be_finished_costs_one_attempt_and_is_not_repaired(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = fake_model(orch, monkeypatch, LLMTruncatedError(CUT))
    chunks = [dict(c, page=41) for c in CHUNKS]  # a page number the excerpts do not print: it used to be read as an unverified figure of the apology

    async def retrieve(query, notebook_id, scope, forced=None, net_others=False):
        return orch_mod.RetrievalResult(scope, {"amd": "AMD", "nv": "NVIDIA"}, [], [], [dict(c) for c in chunks], "targets_planner")

    monkeypatch.setattr(orch, "retrieve", retrieve)
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 1  # one attempt, no repair of an apology
    assert r["answer"].startswith("Sorry, this question is beyond") and "⚠️" not in r["answer"]
    assert r["verification"]["passed"] and not r["verification"]["repaired"]


@pytest.mark.parametrize("failure", [LLMUnavailableError, LLMTruncatedError])
async def test_a_second_writing_that_fails_either_way_keeps_the_first_answer(monkeypatch, failure):
    orch, _ = _orchestrator([], monkeypatch)
    calls = fake_model(orch, monkeypatch, "AMD revenue was $99,999 million [1].", failure(CUT))
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 2 and "$99,999" in r["answer"] and "Sorry" not in r["answer"] and not r["verification"]["repaired"]


# ---------------------------------------------------------------- the other callers ask once, not again and again
async def test_the_planner_the_scope_check_and_the_follow_up_rewrite_do_not_ask_again_after_a_cut(monkeypatch):
    calls = []

    async def cut(messages, **kwargs):
        calls.append(1)
        raise LLMTruncatedError(CUT)

    planner._cache.clear()
    planner._guard_cache.clear()
    monkeypatch.setattr(planner, "chat_completion", cut)
    monkeypatch.setattr(input_policy, "chat_completion", cut)
    assert await planner.plan_multi_doc("a question about both", CATALOG) == [] and len(calls) == 1  # it used to be asked twice
    assert await planner.unlisted_companies("Apple revenue?", CATALOG) == [] and len(calls) == 2  # and three times
    assert await input_policy.rewrite_followup("and 2022?", [{"role": "user", "content": "AMD revenue 2023?"}, {"role": "assistant", "content": "x"}]) is None and len(calls) == 3
