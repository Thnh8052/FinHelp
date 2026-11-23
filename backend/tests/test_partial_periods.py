"""B8 (19/11, owner: fix it, with the short note): a question about several years was refused WHOLE when one year was in no selected report, and
years of a maturity schedule counted as periods asked. "What was Amazon's total long-term debt in 2019, and what portion of its notes matures between
2020 and 2022?" over Amazon's FY2017 and FY2019 10-Ks got "The selected sources do not cover FY2020, FY2022"; Note 6 of the FY2019 10-K prints that
schedule. Two of the 166 answerable gold v2 questions were refused this way (fb_expert_004, fb_expert_008).
Now: an amount dated after the latest report (maturing, due, scheduled, expected...) belongs to that report (prompt v5 says so to the model); a year
no report shows, next to years that are shown, gets a note and an answer for the rest; a question whose every year is missing is still refused."""
from app.modules.query_router.input_policy import PARTIAL_PERIOD_NOTE, SourceInfo, decide

A17 = SourceInfo("Amazon.com, Inc.", "10-K", 2017, None, "Amazon.com, Inc. 10-K FY2017", years_covered=[2017, 2016, 2015])
A19 = SourceInfo("Amazon.com, Inc.", "10-K", 2019, None, "Amazon.com, Inc. 10-K FY2019", years_covered=[2019, 2018, 2017])
DEBT_EN = ("What was Amazon's total Long-Term Debt in 2019, and what portion of its Senior Unsecured Notes is scheduled to mature between 2020 and 2022 "
           "according to Note 6 (Debt)?")
DEBT_VI = "Tổng nợ dài hạn của Amazon năm 2019 là bao nhiêu và bao nhiêu trái phiếu đáo hạn trong giai đoạn 2020-2022?"


def test_years_of_a_maturity_schedule_are_not_periods_asked():
    for q in (DEBT_EN, DEBT_VI, "How much of Amazon's debt matures in 2021?", "Amazon dự kiến chi bao nhiêu cho thuê văn phòng năm 2021?"):
        d = decide(q, [A17, A19], 2)
        assert d.action != "period_unavailable", q
        assert "period_missing" not in d.flags, q  # nothing is missing: the FY2019 report prints the schedule


def test_a_missing_year_next_to_shown_years_is_answered_with_a_note():
    for q in ("What was Amazon's revenue in 2019 and 2022?", "Doanh thu của Amazon năm 2019 và 2022 là bao nhiêu?"):
        d = decide(q, [A19], 1)
        assert d.action != "period_unavailable", q
        assert PARTIAL_PERIOD_NOTE.format(wanted="FY2022") in d.notes and "period_missing" in d.flags


def test_a_question_whose_every_year_is_missing_is_still_refused():
    for q in ("What was Amazon's revenue in 2022?", "Doanh thu của Amazon năm 2022 là bao nhiêu?", "What was Amazon's revenue in 2010 and 2011?"):
        assert decide(q, [A19], 1).action == "period_unavailable", q


BANK25 = SourceInfo("Royal Bank of Canada", "annual report", 2025, None, "RBC annual report FY2025", years_covered=[2025, 2024])


def test_a_schedule_word_after_the_year_also_dates_the_amount():
    """24/11 (owner: make the rule looser): Vietnamese puts "dự kiến" after the year ("năm 2026 dự kiến"), English often too ("Q4 2026 expected"); the cue
    was looked for only before the year, so a forecast the report prints got "The selected reports do not show FY2026" (TRIED NP-28)."""
    for q, sources in (
        ("Theo thuyết minh 5, GDP quý 4 năm 2026 dự kiến cao hơn mức quý 4 năm 2025 bao nhiêu phần trăm?", [BANK25]),
        ("By how much is GDP in calendar Q4 2026 expected to exceed Q4 2025 in Note 5?", [BANK25]),
        ("Chi phí thuê văn phòng của Amazon năm 2021 dự kiến là bao nhiêu?", [A19]),
        ("How much of Amazon's notes in 2021 are scheduled to mature?", [A19]),
    ):
        d = decide(q, sources, len(sources))
        assert d.action != "period_unavailable", q
        assert "period_missing" not in d.flags, q


def test_a_result_of_a_later_year_is_not_a_schedule():
    """Only amounts dated after the report: "revenue in 2022" has no cue, "net sales expected" without a later year is an ordinary period."""
    assert decide("What revenue did Amazon report for 2022?", [A19], 1).action == "period_unavailable"
    assert decide("What net sales did Amazon expect for 2019?", [A19], 1).action != "period_unavailable"
