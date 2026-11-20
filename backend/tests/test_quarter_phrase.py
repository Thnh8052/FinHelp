"""A quarter written in Vietnamese ("quý 2 năm 2023") is read as that quarter, like "Q2 2023".
Production check 20/11: it was read as a whole year, no annual report exists, and the line above the answer wrongly said the year came from a
comparative column of a later report."""
import pytest

from app.modules.query_router import catalog_route
from app.modules.query_router.target_resolver import Filing
from app.modules.query_router.target_scope import ScopeDoc, decide_targets


def release(i, company, ticker, fy, quarter, end):
    card = {"entity": company, "aliases": [], "ticker": ticker}
    return ScopeDoc(i, f"{company} | earnings release | FY{fy} Q{quarter}", card, Filing(i, company, "earnings release", fy, quarter, None, end), [fy, fy - 1])


MCD = release("mcd", "McDonald's Corporation", "MCD", 2023, 2, "2023-06-30")
INTC = release("intc", "Intel Corporation", "INTC", 2023, 1, "2023-04-01")
CRM = release("crm", "Salesforce, Inc.", "CRM", 2024, 2, "2023-07-31")
DOCS = [MCD, INTC, CRM]

SAME_QUARTER = [  # every way of writing "the second quarter of 2023" that a user types, in English and in Vietnamese
    "Q2 2023", "q2 fy2023", "second quarter of 2023", "the second quarter of fiscal year 2023",
    "quý 2 năm 2023", "Quý 2/2023", "quý 2-2023", "quý II năm 2023", "quý hai năm 2023", "quý 2 của năm 2023",
    "quý 2 năm tài chính 2023", "quý 2 FY2023", "Q2 năm 2023", "quy 2 nam 2023",
]


@pytest.mark.parametrize("phrase", SAME_QUARTER)
def test_every_way_of_writing_a_quarter_gives_the_same_pair(phrase):
    assert catalog_route.quarter_pairs(f"What was the revenue in {phrase}?") == [(2023, 2)]


def test_several_quarters_in_one_vietnamese_question_keep_their_own_years():
    assert catalog_route.quarter_pairs("so sánh quý 1 năm 2023 và quý 4 năm tài chính 2024") == [(2023, 1), (2024, 4)]


@pytest.mark.parametrize("text", ["doanh thu năm 2023", "quý 5 năm 2023", "quý này", "quý 2 năm ngoái", "quý 2 và năm 2023 là hai kỳ khác nhau"])
def test_no_quarter_is_invented(text):
    assert catalog_route.quarter_pairs(text) == []


@pytest.mark.parametrize("vi,question", [
    (True, "Doanh thu và thu nhập hoạt động của McDonald's quý 2 năm 2023 là bao nhiêu?"),
    (True, "Doanh thu McDonald's quý II/2023 là bao nhiêu?"),
    (False, "What were McDonald's revenue and operating income in Q2 2023?"),
])
def test_a_quarter_with_its_own_report_is_not_said_to_come_from_a_comparative_column(vi, question):
    t = decide_targets(question, DOCS, None, vi=vi)
    assert t.document_ids == ["mcd"] and t.rule == "resolved" and not t.from_later
    assert "cột so sánh" not in t.understood and "comparative" not in t.understood
    assert "Giả định" not in t.understood and "Assumed" not in t.understood


def test_two_companies_in_vietnamese_each_get_their_own_quarter_and_no_false_assumption():
    t = decide_targets("So sánh tổng doanh thu của Intel quý 1 năm 2023 và Salesforce quý 2 năm tài chính 2024.", DOCS, None, vi=True)
    assert sorted(t.document_ids) == ["crm", "intc"] and not t.from_later
    assert "cột so sánh" not in t.understood and "Giả định" not in t.understood


def test_a_vietnamese_quarter_no_report_covers_still_falls_back_to_the_year_rule():
    # the quarter is parsed (no longer a whole year), and McDonald's has no Q3 2023 report: no document is forced, nothing is said to be a comparative column
    t = decide_targets("Doanh thu McDonald's quý 3 năm 2023 là bao nhiêu?", DOCS, None, vi=True)
    assert "cột so sánh" not in t.understood
