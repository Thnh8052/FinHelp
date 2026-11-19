"""Two reports that print different figures for the same line item and year (owner 19/11): a later report restating an earlier year must be reported
to the user. The system prompt already asked for it; nothing made sure the model saw the difference. Code finds it in the excerpts before the answer is
written and adds the owner-approved note; it never changes a figure.

Measured before the change (experiments/scripts/system_test_18_11/figure_conflicts.py): on the FinanceBench annual reports, 93 conflicts in 4,262 cells
two reports print, about 18-19 of a sample of 20 real restatements or reclassifications; future payment schedules, 10-Q half-year columns, generic row
names and untitled tables were the false ones and are left out."""
from app.modules.chat import orchestrator as orch_mod
from app.modules.generation.conflicts import Report, conflict_notes
from app.modules.query_router.input_policy import Decision
from tests.test_input_policy import _doc, _orchestrator

CF = "CONSOLIDATED STATEMENTS OF CASH FLOWS"
A17 = {"chunk_id": "c17", "document_id": "a17", "page": 38, "table_title": CF, "content": "(in millions)\n\n| | 2016 | 2017 |\n|---|---|---|\n"
       "| Net cash provided by (used in) operating activities | 16,443 | 18,434 |\n| Other, net | 12 | 15 |"}
A19 = {"chunk_id": "c19", "document_id": "a19", "page": 36, "table_title": CF, "content": "(in millions)\n\n| | 2017 | 2018 | 2019 |\n|---|---|---|---|\n"
       "| Net cash provided by (used in) operating activities | 18,365 | 30,723 | 38,514 |\n| Other, net | 40 | 9 | 7 |"}
REPORTS = {"a17": Report("amazoncom", True, 2017, "Amazon | 10-K | FY2017"), "a19": Report("amazoncom", True, 2019, "Amazon | 10-K | FY2019")}
NOTE = ('Excerpts [1] and [2] print different figures for "Net cash provided by (used in) operating activities" in 2017: 18,434 in [1] (Amazon | 10-K | FY2017) '
        'and 18,365 in [2] (Amazon | 10-K | FY2019); the later report has probably restated it. If your answer uses this figure, tell the user both figures '
        "with their reports and say which one you used (the later report's).")


def test_a_figure_a_later_annual_report_restates_gets_the_approved_note():
    assert conflict_notes([A17, A19], REPORTS) == [NOTE]


def test_the_same_figure_in_both_reports_or_in_another_scale_is_no_conflict():
    same = dict(A19, content=A19["content"].replace("18,365", "18,434"))
    assert conflict_notes([A17, same], REPORTS) == []
    thousands = dict(A19, content=A19["content"].replace("(in millions)", "(in thousands)").replace("18,365", "18,434,000"))
    assert conflict_notes([A17, thousands], REPORTS) == []


def test_what_is_not_a_restated_year_is_left_out():
    # a schedule of future payments: 2018 is not closed in the FY2017 report
    plan = {"document_id": "a17", "page": 60, "table_title": "Contractual obligations", "content": "| | 2018 | 2019 |\n|---|---|---|\n| Long-term debt payments | 100 | 1,354 |"}
    later = {"document_id": "a19", "page": 70, "table_title": "Contractual obligations", "content": "| | 2018 | 2019 |\n|---|---|---|\n| Long-term debt payments | 160 | 1,300 |"}
    assert conflict_notes([plan, later], REPORTS) == []
    # a quarterly report: its 2017 column may be six months
    quarterly = {**REPORTS, "a19": Report("amazoncom", False, 2019, "Amazon | 10-Q | FY2019 Q2")}
    assert conflict_notes([A17, A19], quarterly) == []
    # another company, an untitled table, a generic row name ("Other, net" differs above and is not reported)
    other = {**REPORTS, "a19": Report("costcowholesale", True, 2019, "Costco | 10-K | FY2019")}
    assert conflict_notes([A17, A19], other) == []
    assert conflict_notes([A17, dict(A19, table_title="")], REPORTS) == []


async def test_the_note_reaches_the_answer_prompt_in_both_languages(monkeypatch):
    docs = [_doc("a17", "amzn17.pdf", company_name="Amazon.com, Inc.", fiscal_year=2017, report_type="10-K"),
            _doc("a19", "amzn19.pdf", company_name="Amazon.com, Inc.", fiscal_year=2019, report_type="10-K")]
    orch, _ = _orchestrator(docs, monkeypatch)
    seen = []

    async def retrieve(query, notebook_id, scope, forced=None):
        return orch_mod.RetrievalResult(scope, {"a17": "Amazon | 10-K | FY2017", "a19": "Amazon | 10-K | FY2019"}, [], [], [dict(A17), dict(A19)], "targets_planner")

    async def generate(question, chunks, notes=None, max_tokens=1200):
        seen.append(list(notes or []))
        return "Amazon's 2017 operating cash flow was 18,365 million [2]."

    monkeypatch.setattr(orch, "retrieve", retrieve)
    orch.__dict__.pop("_answer", None)
    monkeypatch.setattr(orch_mod, "generate_answer", generate)
    for question, lang in (("What was Amazon's operating cash flow in 2017?", "en"), ("Dòng tiền hoạt động của Amazon năm 2017 là bao nhiêu?", "vi")):
        await orch._answer_one(question, "nb", docs, Decision(lang=lang))
        assert any("print different figures" in n and "18,434" in n and "18,365" in n for n in seen[-1]), seen[-1]


def test_a_footnote_mark_does_not_make_a_generic_row_name_specific():
    """Measured on FinanceBench: "Other, net (b)" passed the generic-name filter because of its footnote mark."""
    a = dict(A17, content=A17["content"].replace("Other, net", "Other, net (b)"))
    b = dict(A19, content=A19["content"].replace("Other, net", "Other, net (b)").replace("18,365", "18,434"))
    assert conflict_notes([a, b], REPORTS) == []
