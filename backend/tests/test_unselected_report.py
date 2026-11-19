"""B2 / T5 (system test 18/11, owner: change the message only, no new button): the question asks for a period that the selected sources do not cover,
while a ready report of the same company in this chat does. The reply said "Add the report for that period"; the report was already there."""
from app.modules.query_router.input_policy import SourceInfo, decide
from tests.test_input_policy import _doc, _orchestrator

NIKE19 = SourceInfo("NIKE, Inc", "10-K", 2019, None, "NIKE | 10-K | FY2019", years_covered=[2019, 2018, 2017])
NIKE12 = SourceInfo("NIKE, Inc", "10-K", 2012, None, "NIKE | 10-K | FY2012", years_covered=[2012, 2011, 2010])
PEP12 = SourceInfo("PepsiCo, Inc", "10-K", 2012, None, "PepsiCo | 10-K | FY2012", years_covered=[2012, 2011, 2010])
EN = "The FY2012 report is in this chat but not selected: select it in the sources and ask again."
VI = "Báo cáo cho FY2012 có trong chat nhưng chưa được chọn: hãy chọn nó trong danh sách nguồn rồi hỏi lại."


def test_a_report_in_the_chat_that_covers_the_period_is_named_in_both_languages():
    en = decide("What was Nike's revenue in FY2012?", [NIKE19], 2, unselected=[NIKE12])
    vi = decide("Doanh thu của Nike năm 2012 là bao nhiêu?", [NIKE19], 2, unselected=[NIKE12])
    assert en.action == vi.action == "period_unavailable"
    assert en.message == EN and vi.message == VI


def test_without_such_a_report_the_message_is_the_old_one():
    for unselected in ([], [PEP12]):  # none, or only another company's report for that year
        en = decide("What was Nike's revenue in FY2012?", [NIKE19], 2, unselected=unselected)
        vi = decide("Doanh thu của Nike năm 2012 là bao nhiêu?", [NIKE19], 2, unselected=unselected)
        assert en.action == "period_unavailable" and "Add the report for that period" in en.message
        assert vi.action == "period_unavailable" and "Hãy chọn thêm tài liệu của kỳ đó" in vi.message


async def test_the_chat_passes_the_ready_reports_that_are_not_selected(monkeypatch):
    docs = [_doc("d1", "nike19.pdf", company_name="NIKE, Inc", fiscal_year=2019, report_type="10-K"),
            _doc("d2", "nike23.pdf", company_name="NIKE, Inc", fiscal_year=2023, report_type="10-K"),
            _doc("d3", "nike12.pdf", company_name="NIKE, Inc", fiscal_year=2012, report_type="10-K")]
    orch, _ = _orchestrator(docs, monkeypatch)
    r = await orch.execute_query("What was Nike's revenue in FY2012?", "nb", document_ids=["d1", "d2"])
    assert r["intent"] == "period_unavailable" and EN in r["answer"]
    r = await orch.execute_query("Doanh thu của Nike năm 2012 là bao nhiêu?", "nb", document_ids=["d1", "d2"])
    assert r["intent"] == "period_unavailable" and VI in r["answer"]


async def test_a_part_of_a_message_with_several_questions_names_the_unselected_report_too(monkeypatch):
    """The parts of a message that asks several questions are decided one by one (_split_parts): they got the old message before 19/11."""
    docs = [_doc("d1", "nike19.pdf", company_name="NIKE, Inc", fiscal_year=2019, report_type="10-K"),
            _doc("d2", "nike23.pdf", company_name="NIKE, Inc", fiscal_year=2023, report_type="10-K"),
            _doc("d3", "nike12.pdf", company_name="NIKE, Inc", fiscal_year=2012, report_type="10-K")]
    orch, _ = _orchestrator(docs, monkeypatch)
    r = await orch.execute_query("What was Nike's revenue in FY2019? What was Nike's revenue in FY2012?", "nb", document_ids=["d1", "d2"])
    assert EN in r["answer"]
