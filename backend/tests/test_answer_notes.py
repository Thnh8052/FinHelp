"""The notes code adds to the answer prompt (prompt review 19/11, problems 1-3, owner: "nghiên cứu và sửa lại").
1. They were not in the trace: nobody could tell afterwards what the model had been told.
2. An assumption shown above the answer (the "understood" line) was also asked of the answer: "State the assumption in one short sentence at the
   start", next to the input policy's "... and say so" for the same year, so answers opened by repeating the line above them (3 of 3 dev samples).
   A part of a message with several questions has no understood line: it still states its assumption.
3. The notes named a report by its machine label "Amazon.com, Inc. | 10-K | FY2019 (ended 2019-12-31)", and answers copied it word for word."""
from app.modules.query_router.input_policy import PRIOR_YEAR_NOTE
from app.modules.query_router.target_scope import decide_targets
from tests.test_input_policy import _doc, _orchestrator
from tests.test_targets import AMD25, NV25, doc

NIKE19 = [_doc("d1", "nike19.pdf", company_name="NIKE, Inc", fiscal_year=2019, report_type="10-K", period_end="2019-05-31", years_covered=[2019, 2018, 2017])]
NIKE_BOTH = NIKE19 + [_doc("d2", "nike23.pdf", company_name="NIKE, Inc", fiscal_year=2023, report_type="10-K", period_end="2023-05-31", years_covered=[2023, 2022, 2021])]


def _notes(seen, n=0):
    return seen["answers"][n][1]


# ------------------------------------------------------------------ 1. the notes are in the trace
async def test_the_notes_sent_with_the_answer_are_in_the_trace(monkeypatch):
    orch, seen = _orchestrator(NIKE_BOTH, monkeypatch)
    r = await orch.execute_query("What was Nike's revenue?", "nb", document_ids=["d1", "d2"])
    assert _notes(seen) and r["trace"]["notes"] == _notes(seen)


async def test_each_part_of_a_message_with_several_questions_keeps_its_notes(monkeypatch):
    orch, seen = _orchestrator(NIKE19, monkeypatch)
    r = await orch.execute_query("What was Nike's revenue in 2018? What was Nike's net income in FY2019?", "nb", document_ids=["d1"])
    parts = r["trace"]["parts"]
    assert len(parts) == 2 and [p["notes"] for p in parts] == [_notes(seen, 0), _notes(seen, 1)]


# ------------------------------------------------------------------ 2. what the understood line shows is not asked again
async def test_an_assumption_shown_above_the_answer_is_given_to_the_model_but_not_asked_again(monkeypatch):
    for question in ("What was Nike's revenue in 2018?", "Doanh thu của Nike năm 2018 là bao nhiêu?"):
        orch, seen = _orchestrator(NIKE19, monkeypatch)
        r = await orch.execute_query(question, "nb", document_ids=["d1"])
        notes = _notes(seen)
        assert "2018" in r["understood"]  # the line above the answer says where FY2018 comes from
        assert PRIOR_YEAR_NOTE not in notes and not any("State the assumption" in n for n in notes)
        said = [n for n in notes if "FY2018" in n and "do not repeat" in n]
        assert len(said) == 1  # the model still knows the assumption, once


async def test_a_part_without_an_understood_line_still_states_its_assumption(monkeypatch):
    orch, seen = _orchestrator(NIKE19, monkeypatch)
    r = await orch.execute_query("What was Nike's revenue in 2018? What was Nike's net income in FY2019?", "nb", document_ids=["d1"])
    assert "understood" not in r or not r["understood"]
    assert any("State the assumption" in n and "FY2018" in n for n in _notes(seen, 0))


def test_a_gap_of_the_tagged_files_shown_above_the_answer_is_not_said_again():
    question = "Compare AMD and NVIDIA revenue in 2025."
    shown = decide_targets(question, [AMD25, NV25], ["amd25"], vi=False)
    alone = decide_targets(question, [AMD25, NV25], ["amd25"], vi=False, shown=False)
    assert "NVIDIA" in shown.understood
    assert not any("say so in one sentence" in n for n in shown.notes) and any("do not repeat" in n for n in shown.notes)
    assert any("say so in one sentence" in n for n in alone.notes)


def test_the_fiscal_year_alignment_shown_above_the_answer_is_not_asked_again(monkeypatch):
    from app.modules.query_router import target_scope

    monkeypatch.setattr(target_scope, "alignment_note", lambda *a: "Comparing 2025: AMD uses FY2025; NVIDIA uses FY2026 (standing for calendar 2025).")
    shown = decide_targets("Compare AMD and NVIDIA revenue in 2025.", [AMD25, NV25], None, vi=False)
    alone = decide_targets("Compare AMD and NVIDIA revenue in 2025.", [AMD25, NV25], None, vi=False, shown=False)
    assert "standing for calendar 2025" in shown.understood
    assert not any(n.startswith("Say how the fiscal years were aligned") for n in shown.notes)
    assert any("standing for calendar 2025" in n and "do not repeat" in n for n in shown.notes)
    assert any(n.startswith("Say how the fiscal years were aligned") for n in alone.notes)


# ------------------------------------------------------------------ 3. reports named in words, not by the machine label
async def test_notes_and_the_understood_line_name_reports_without_the_machine_label(monkeypatch):
    for question in ("What was Nike's revenue?", "What was Nike's revenue in 2018?"):
        orch, seen = _orchestrator(NIKE_BOTH, monkeypatch)
        r = await orch.execute_query(question, "nb", document_ids=["d1", "d2"])
        text = " ".join(_notes(seen)) + " " + r["understood"]
        assert " | " not in text and "(ended" not in text
        assert "NIKE, Inc 10-K FY2019" in text or "NIKE, Inc 10-K FY2023" in text
