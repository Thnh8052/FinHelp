"""How the question was understood is said once, where it belongs (system test 18/11, D5). A rewritten follow-up was shown twice, as the
"understood" line above the answer ("I understood the question as about: <files>") and again at the start of the answer ("I understood the question
as: “…”"); and every assumption ended the answer with "if this is not what you meant, tag the right file", even when no other file could be tagged
(a year read from the comparative column of the only report of that company)."""
from app.modules.query_router.target_scope import decide_targets, merge_understood
from tests.test_input_policy import HIST, NIKE_DOCS, _orchestrator
from tests.test_targets import AMD25, NV25, doc

LABELS_VI = "Tôi hiểu câu hỏi về: Costco | 10-K | FY2020."
LABELS_EN = "I understood the question as about: Costco | 10-K | FY2020. Assumed: FY2018 from the comparative column of Costco | 10-K | FY2020."


# ------------------------------------------------------------------ one line: the question as understood, then the files
def test_the_rewritten_question_and_the_files_make_one_line():
    assert merge_understood("Doanh thu của Costco năm 2018 là bao nhiêu?", LABELS_VI, vi=True) == \
        "Tôi hiểu câu hỏi là: “Doanh thu của Costco năm 2018 là bao nhiêu?”, về: Costco | 10-K | FY2020."
    assert merge_understood("What was Costco's revenue in 2018?", LABELS_EN, vi=False) == \
        "I understood the question as: “What was Costco's revenue in 2018?”, about: Costco | 10-K | FY2020. Assumed: FY2018 from the comparative column of Costco | 10-K | FY2020."


def test_without_files_the_line_is_the_question_alone_and_without_a_rewrite_nothing_changes():
    assert merge_understood("What was Costco's revenue in 2018?", "", vi=False) == "I understood the question as: “What was Costco's revenue in 2018?”."
    assert merge_understood("", LABELS_VI, vi=True) == LABELS_VI


# ------------------------------------------------------------------ the closing hint only when another file can be chosen
def test_a_year_from_the_comparative_column_states_the_assumption_without_the_tag_hint():
    t = decide_targets("What was AMD's revenue in 2024?", [AMD25, NV25], None, vi=False)
    assert t.document_ids == ["amd25"] and not t.alternatives
    assert any("comparative column" in n for n in t.notes)  # the assumption is still stated
    assert not any("tag the right file" in n for n in t.notes)  # no other AMD file exists to tag


def test_the_hint_stays_when_another_file_matches():
    amd24 = doc("amd24", "Advanced Micro Devices, Inc.", 2024, "AMD")
    t = decide_targets("What was AMD's gross margin?", [amd24, AMD25, NV25], None, vi=False)
    assert t.alternatives and any("tag the right file" in n for n in t.notes)


# ------------------------------------------------------------------ the answer itself does not repeat the line
async def test_a_rewritten_follow_up_is_shown_in_the_understood_line_not_in_the_answer(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod

    orch, seen = _orchestrator(NIKE_DOCS[1:], monkeypatch)

    async def rewrite(q, history):
        return "What was Nike's net income in FY2023?"

    monkeypatch.setattr(orch_mod, "rewrite_followup", rewrite)
    r = await orch.execute_query("And the net income?", "nb", document_ids=["d2"], history=HIST)
    assert r["understood"].startswith("I understood the question as: “What was Nike's net income in FY2023?”")
    assert "I understood the question as" not in r["answer"]
    assert r["trace"]["followup"]["resolved"] == "What was Nike's net income in FY2023?"


async def test_a_fixed_reply_after_a_rewrite_still_says_how_the_question_was_understood(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod

    orch, seen = _orchestrator(NIKE_DOCS[1:], monkeypatch)

    async def rewrite(q, history):
        return "What was Nike's net income in FY2010?"  # no selected report covers 2010: a fixed reply, which has no understood line

    monkeypatch.setattr(orch_mod, "rewrite_followup", rewrite)
    r = await orch.execute_query("And the net income?", "nb", document_ids=["d2"], history=HIST)
    assert r["answer"].startswith("I understood the question as: “What was Nike's net income in FY2010?”")


async def test_a_click_shows_the_question_it_asks_again(monkeypatch):
    orch, seen = _orchestrator(NIKE_DOCS[1:], monkeypatch)
    r = await orch.execute_query("What was Nike's net income in FY2023?", "nb", document_ids=["d2"], asked_as="What was Nike's net income in FY2023?")
    assert r["understood"].startswith("I understood the question as: “What was Nike's net income in FY2023?”")
    assert "I understood the question as" not in r["answer"]
