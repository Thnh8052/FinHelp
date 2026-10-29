"""target_resolver: company / year / quarter -> filing, with fiscal years named differently by companies."""
from app.services.query_router.target_resolver import Filing, Target, alignment_note, resolve

F = [
    Filing("ulta_2023_10k", "ULTA BEAUTY, INC", "10-K", 2022, None, 2022, "2023-01-28"),        # fiscal 2022 ends 2023-01-28
    Filing("bestbuy_2023_10k", "BEST BUY CO., INC", "10-K", 2023, None, 2022),     # fiscal 2023 ends 2023-01-28
    Filing("bestbuy_2019_10k", "BEST BUY CO., INC", "10-K", 2019, None, 2018),
    Filing("bestbuy_2024q2_10q", "BEST BUY CO., INC", "10-Q", 2024, 2, None),
    Filing("cocacola_2022_10k", "THE COCA-COLA COMPANY", "10-K", 2022, None, 2022, "2022-12-31"),
    Filing("cocacola_2021_10k", "THE COCA-COLA COMPANY", "10-K", 2021, None, 2021),
    Filing("walmart_2023_10k", "Walmart Inc.", "10-K", 2023, None, 2022, "2023-01-31"),
    Filing("walmart_2022_10k", "Walmart Inc.", "10-K", 2022, None, 2021, "2022-01-31"),
    Filing("nike_2023_10k", "NIKE, Inc", "10-K", 2023, None, 2022),              # ends 2023-05-31
    Filing("jpm_2022_10k", "JPMorgan Chase & Co", "10-K", 2022, None, 2022),
    Filing("jpm_2022q4_er", "JPMorgan Chase & Co", "earnings release", 2022, 4, None),
]


def ids(rs): return [r.document_ids for r in rs]


def test_fiscal_name_is_used_when_the_user_says_fy():
    rs = resolve([Target("Ulta Beauty", 2022, "fiscal"), Target("Best Buy", 2022, "fiscal")], F)
    assert ids(rs) == [["ulta_2023_10k"], []] and rs[1].problem == "period not in sources"


def test_plain_year_comparison_of_offset_and_calendar_companies_is_aligned_on_calendar_year():
    rs = resolve([Target("Ulta Beauty", 2022), Target("Best Buy", 2022)], F)
    assert ids(rs) == [["ulta_2023_10k"], ["bestbuy_2023_10k"]] and rs[1].rule.startswith("calendar")
    rs = resolve([Target("Nike", 2022), Target("Coca-Cola", 2022)], F)
    assert ids(rs) == [["nike_2023_10k"], ["cocacola_2022_10k"]]


def test_plain_year_for_one_company_keeps_its_own_name():
    assert ids(resolve([Target("Nike", 2023)], F)) == [["nike_2023_10k"]]
    assert ids(resolve([Target("Best Buy", 2023)], F)) == [["bestbuy_2023_10k"]]


def test_calendar_basis_and_quarter_and_latest():
    assert ids(resolve([Target("Best Buy", 2018, "calendar")], F)) == [["bestbuy_2019_10k"]]
    assert ids(resolve([Target("Best Buy", 2024, quarter=2)], F)) == [["bestbuy_2024q2_10q"]]
    assert ids(resolve([Target("Best Buy")], F)) == [["bestbuy_2023_10k"]]


def test_10k_preferred_over_earnings_release_and_unknown_company_flagged():
    assert ids(resolve([Target("JPMorgan Chase", 2022)], F)) == [["jpm_2022_10k"]]
    r = resolve([Target("Adidas", 2022)], F)[0]
    assert r.document_ids == [] and r.problem == "company not in sources"


def test_fiscal_name_the_company_never_used_falls_back_to_the_period_end_year():
    r = resolve([Target("Ulta Beauty", 2023, "fiscal")], F)[0]  # FinanceBench: "Ulta Beauty ... as of FY2023"
    assert r.document_ids == ["ulta_2023_10k"] and "FY2022" in r.rule


def test_aligned_comparison_comes_with_a_note_saying_which_fiscal_year_stands_for_the_year():
    rs = resolve([Target("Coca-Cola", 2022), Target("Walmart", 2022)], F)
    assert ids(rs) == [["cocacola_2022_10k"], ["walmart_2023_10k"]]
    assert alignment_note(rs, F) == ("So sánh năm 2022: Coca-Cola tính theo FY2022 (kết thúc 12/2022); "
                                     "Walmart tính theo FY2023 (kết thúc 01/2023, đại diện cho năm lịch 2022).")
    assert alignment_note(rs, F, vi=False).startswith("Comparing 2022: Coca-Cola uses FY2022 (ended 12/2022); Walmart uses FY2023")
    assert alignment_note(resolve([Target("Walmart", 2022, "fiscal"), Target("Coca-Cola", 2022, "fiscal")], F), F) == ""
