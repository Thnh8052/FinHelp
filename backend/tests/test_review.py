"""The review of a written answer (docs/Version_3/RAG_REDESIGN_SPEC.md section 4): every check returns Findings, one decision, at most one rewrite
with the notes of every check merged, then the answer is kept, blocked or annotated. No model: the answers are made up."""
import pytest

from app.core.config import settings
from app.modules.chat import orchestrator as orch_mod
from app.modules.generation.answer_check import policy, review
from app.modules.generation.answer_check.calculations import wrong_steps
from app.modules.query_router.input_policy import Decision
from tests.test_validation import AMD, CHUNKS, NV, _orchestrator, _scope

META = '\n<answer_meta>{"status": "answered", "short_answer": "x", "citations": [1]}</answer_meta>'
EXCERPT = [{"content": "Net sales 10,000 8,000 Gross profit 2,500 2,000 Revenue 71,890 Gross profit 50,205"}]


def kinds(findings):
    return sorted((f.check, f.severity) for f in findings)


# ---------------------------------------------------------------- the checks
def test_a_grounded_answer_has_no_finding():
    answer = "Net sales grew from 8,000 to 10,000 [1]: (10,000 − 8,000) ÷ 8,000 = 25.0%." + META
    assert review.run_checks(answer, EXCERPT, [], "en") == []


def test_a_written_step_with_a_wrong_result_is_one_arithmetic_finding_that_says_the_right_value():
    answer = "Growth: (10,000 − 8,000) ÷ 8,000 = 20.0% [1]." + META
    found = review.run_checks(answer, EXCERPT, [], "en")
    assert kinds(found) == [("arithmetic", review.REPAIRABLE)]  # the same 20.0% is not reported a second time as an unverified figure
    assert "25.0%" in found[0].note and "20.0%" in found[0].note


@pytest.mark.parametrize("line", [
    "$700 million × (1 − 0.90) = $70 million",                   # a unit word inside: only "(1 − 0.90) = $70" could be read
    "FY2017: |(155)| / 7,017 × 100 = 2.2089% [1]",              # absolute bars
    "DPO = 365 × [(2,746.2 + 2,854.1) ÷ 2] ÷ (11,108.4 − 82.9) = **92.70**",
    "FY2018: \\(131 ÷ 7{,}500 × 100 = 1.7\\%\\)",                  # LaTeX thousands mark
    "FY2018 COGS = 495,761 × (1 − 24.7%) = 373,308.0 million",  # a percent mixed with plain numbers
    "Total stores: 930 + 127 = 1.057; 907 + 128 = 1.035",       # thousands written with a point
])
def test_steps_read_only_in_part_are_never_reported_as_wrong(line):
    assert wrong_steps(line + META) == []


def test_a_wrong_step_in_a_bullet_after_a_colon_or_an_equals_sign_is_found():
    for line in ("- 1,672 ÷ 1,513 = 1.74", "Turnover = $16,830 ÷ $2,694 = **5.99x**", "Calculation: 1,672 ÷ 1,513 = 1.74"):
        assert len(wrong_steps(line)) == 1, line


def test_an_unverified_figure_is_repairable_and_its_note_names_the_answers_own_close_result():
    answer = "Gross margin was 70.9% in FY2016 [1].\n\n- FY2016: 50,205 ÷ 71,890 = 69.8%" + META
    found = review.run_checks(answer, EXCERPT, [], "en")
    assert [(f.check, f.text) for f in found] == [("figure", "70.9%")]
    assert "69.8%" in found[0].note  # a pointer for the rewrite: code never replaces the figure


def test_advice_is_hard_wrong_language_is_repairable_and_a_missing_source_is_only_a_note():
    assert ("safety", review.HARD) in kinds(review.run_checks("I recommend buying the stock [1]." + META, EXCERPT, [], "en"))
    english = "Net sales were 10,000 in the latest year and 8,000 in the year before [1]." + META
    assert ("language", review.REPAIRABLE) in kinds(review.run_checks(english, EXCERPT, [], "vi"))
    assert kinds(review.run_checks("Net sales were 10,000 in the latest year." + META, EXCERPT, [], "en")) == [("status", review.NOTE)]


def test_citations_to_no_excerpt_or_to_another_company_are_repairable():
    found = review.run_checks("AMD revenue was $60,922 million [2]. See also [7]." + META, CHUNKS, [AMD, NV], "en")
    assert [f.check for f in found] == ["citation", "citation"] and all(f.severity == review.REPAIRABLE for f in found)


def test_the_policy_checks_can_be_left_out():
    assert review.run_checks("I recommend buying the stock [1]." + META, EXCERPT, [], "en", policy_checks=False) == []


# ---------------------------------------------------------------- the decision
def test_only_hard_or_repairable_findings_ask_for_a_rewrite_and_the_note_merges_them():
    hard, fig, note = (review.Finding("safety", review.HARD, "", "no advice"), review.Finding("figure", review.REPAIRABLE, "9", "figure 9"),
                       review.Finding("status", review.NOTE, "", "cite"))
    assert not review.needs_rewrite([note]) and review.needs_rewrite([fig]) and review.needs_rewrite([hard])
    text = review.rewrite_note([hard, fig, note])
    assert "no advice" in text and "figure 9" in text and "cite" not in text


def test_the_rewrite_is_kept_only_when_it_has_no_hard_finding_and_strictly_fewer_findings():
    hard, fig = review.Finding("safety", review.HARD, "", ""), review.Finding("figure", review.REPAIRABLE, "1", "")
    assert review.keep_rewrite([fig, fig], [])
    assert not review.keep_rewrite([fig], [fig])  # not fewer: the first answer stays
    assert not review.keep_rewrite([fig], [hard])
    assert review.keep_rewrite([hard], [fig])


def test_the_note_under_the_answer_lists_what_stays_wrong_in_the_answers_language():
    found = [review.Finding("figure", review.REPAIRABLE, "$99,999", ""), review.Finding("arithmetic", review.REPAIRABLE, "1 + 1 = 3", ""),
             review.Finding("citation", review.REPAIRABLE, "[7]", ""), review.Finding("language", review.REPAIRABLE, "", "")]
    vi = review.annotate("Câu trả lời." + META, found, "vi")
    assert "⚠️ Lưu ý: số chưa kiểm chứng được trong đoạn trích: $99,999" in vi and "phép tính viết ra cho kết quả khác" in vi
    assert "trích dẫn không khớp nguồn" in vi and vi.index("⚠️") < vi.index("<answer_meta>")
    en = review.annotate("An answer.", found[:1], "en")
    assert en.endswith("⚠️ Note: figures not verified in the excerpts: $99,999.")
    assert review.annotate("An answer.", [review.Finding("language", review.REPAIRABLE, "", "")], "en") == "An answer."


# ---------------------------------------------------------------- the orchestrator: one writing, at most one rewrite
def _model(orch, monkeypatch, *replies):
    """The real _answer runs; the model gives the replies in turn (the last one repeats). Returns the notes of each call."""
    calls = []

    async def generate(question, chunks, notes=None, max_tokens=1500):
        calls.append(list(notes or []))
        return replies[min(len(calls), len(replies)) - 1]

    orch.__dict__.pop("_answer", None)
    monkeypatch.setattr(orch_mod, "generate_answer", generate)
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4")
    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", True)
    monkeypatch.setattr(settings, "ANSWER_REPAIR_ENABLED", True)
    return calls


async def test_writing_an_answer_no_longer_checks_it(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = _model(orch, monkeypatch, "You should buy AMD stock [1].")
    assert await orch._answer("Should I buy AMD?", [dict(c) for c in CHUNKS]) == "You should buy AMD stock [1]." and len(calls) == 1


async def test_an_answer_with_problems_of_two_kinds_is_rewritten_once_with_both_notes(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = _model(orch, monkeypatch, "AMD revenue was $99,999 million [1]; you should buy the stock.")
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 2  # today's code wrote up to four versions: policy rewrite, repair, policy rewrite of the repair
    assert "investment recommendation" in calls[1][-1] and "$99,999" in calls[1][-1]
    assert r["answer"].startswith(policy.BLOCKED["en"]) and r["trace"]["review"]["outcome"] == "blocked"


async def test_a_wrong_written_result_is_rewritten_with_the_right_value_and_kept_when_fixed(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = _model(orch, monkeypatch, "AMD revenue grew from 22,680 to 25,785 [1]: (25,785 − 22,680) ÷ 22,680 = 20.0%.",
                   "AMD revenue grew from 22,680 to 25,785 [1]: (25,785 − 22,680) ÷ 22,680 = 13.7%.")
    r = await orch._answer_one("How much did AMD revenue grow in 2024?", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 2 and "13.7%" in calls[1][-1]
    assert "13.7%" in r["answer"] and "⚠️" not in r["answer"] and r["verification"]["repaired"] and r["verification"]["passed"]
    assert r["trace"]["review"]["first"][0]["check"] == "arithmetic" and r["trace"]["review"]["outcome"] == "rewritten"


async def test_a_clean_answer_is_written_once_and_the_trace_says_so(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = _model(orch, monkeypatch, "AMD revenue was $25,785 million in 2024 [1]; NVIDIA $60,922 million [2].")
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 1 and r["trace"]["review"] == {"first": [], "after_rewrite": None, "outcome": "accepted"}
    assert r["verification"] == {"passed": True, "repaired": False, "unverified_figures": [], "first_issues": []}


async def test_a_soft_problem_the_rewrite_does_not_fix_keeps_the_first_answer_with_its_note(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = _model(orch, monkeypatch, "AMD revenue was $99,999 million [1].", "AMD revenue was $99,998 million [1].")
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 2 and "$99,999" in r["answer"] and "⚠️ Note: figures not verified in the excerpts: $99,999" in r["answer"]
    assert r["trace"]["review"]["outcome"] == "kept" and not r["verification"]["repaired"] and not r["verification"]["passed"]


async def test_without_repairs_a_hard_problem_is_still_rewritten_once_and_a_soft_one_is_only_noted(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = _model(orch, monkeypatch, "AMD revenue was $99,999 million [1].")
    monkeypatch.setattr(settings, "ANSWER_REPAIR_ENABLED", False)
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 1 and "⚠️" in r["answer"]
    calls = _model(orch, monkeypatch, "You should buy AMD stock [1].", "AMD revenue was $25,785 million in 2024 [1].")
    monkeypatch.setattr(settings, "ANSWER_REPAIR_ENABLED", False)
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 2 and "$25,785" in r["answer"]


async def test_an_overview_is_checked_for_safety_but_not_for_figures(monkeypatch):
    orch, _ = _orchestrator([], monkeypatch)
    calls = _model(orch, monkeypatch, "AMD: revenue about $99,999 million [1].")
    chunks = [dict(c, document_label="AMD") for c in CHUNKS]
    answer, info = await orch._write_checked("Summarize the files", chunks, [], [], "en", figures=False)
    assert answer.startswith("AMD: revenue about $99,999") and "⚠️" not in answer and len(calls) == 1 and info["outcome"] == "accepted"
    calls = _model(orch, monkeypatch, "AMD looks like a good buy [1].", "AMD looks like a good buy [1].")
    answer, info = await orch._write_checked("Summarize the files", chunks, [], [], "en", figures=False)
    assert answer.startswith(policy.BLOCKED["en"]) and len(calls) == 2
