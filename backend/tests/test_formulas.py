"""TC-4, slice 1: a growth rate must be divided by the earlier period's value. The arithmetic check only re-computes what the answer writes, so
"(10,000 − 8,000) ÷ 10,000 = 20.0%" passed: the division is right, the formula is not (P0 case E03w). Checked only when the code is sure: the step is
a change between two figures, the sentence talks about growth or change, and the period of both figures is known (from the excerpt's table column,
a year written next to the figure in the excerpt, or the answer's own cited claim). Anything unsure is left alone. No model."""
from app.core.config import settings
from app.modules.generation.answer_check.formulas import check_formulas
from app.modules.generation.verification import flag_unverified, verify

TEXT = [{"content": "Revenues: FY2015 10,000; FY2014 8,000."}]  # the P0 fixture of E03w
TABLE = [{"content": "| Item | 2015 | 2014 |\n| --- | --- | --- |\n| Revenues | 10,000 | 8,000 |\n| Cost of sales | 6,000 | 5,000 |\n"}]


def problems(answer, chunks=TEXT):
    return [f["problem"] for f in check_formulas(answer, chunks)]


def test_a_growth_rate_divided_by_the_later_value_is_caught():
    found = check_formulas("Growth = (10,000 − 8,000) ÷ 10,000 = 20.0%.", TEXT)
    assert len(found) == 1 and found[0]["kind"] == "growth_base"
    assert "8,000" in found[0]["problem"] and "earlier" in found[0]["problem"]


def test_the_right_growth_rate_passes():
    assert problems("Growth = (10,000 − 8,000) ÷ 8,000 = 25.0%.") == []
    assert problems("Revenue grew 10,000 ÷ 8,000 − 1 = 25.0%.") == []


def test_the_ratio_minus_one_form_is_checked_too():
    assert len(problems("Revenue growth: 8,000 ÷ 10,000 − 1 = −20.0%.")) == 1  # the later value as the base


def test_a_decline_written_from_the_old_value_passes():
    chunks = [{"content": "Revenues: FY2015 8,000; FY2014 10,000."}]
    assert problems("Revenue declined (10,000 − 8,000) ÷ 10,000 = 20.0%.", chunks) == []


def test_a_margin_of_one_year_is_not_a_growth_rate():
    assert problems("Gross margin changed to (10,000 − 6,000) ÷ 10,000 = 40.0% in FY2015.", TABLE) == []  # both figures are FY2015


def test_a_table_gives_the_periods():
    assert len(problems("Revenue growth = (10,000 − 8,000) ÷ 10,000 = 20.0%.", TABLE)) == 1
    assert problems("Revenue growth = (10,000 − 8,000) ÷ 8,000 = 25.0%.", TABLE) == []


def test_unknown_or_ambiguous_periods_are_left_alone():
    assert problems("Growth = (10,000 − 8,000) ÷ 10,000 = 20.0%.", [{"content": "Revenues 10,000 and 8,000."}]) == []
    same = [{"content": "| Item | 2015 | 2014 |\n| --- | --- | --- |\n| Revenues | 10,000 | 10,000 |\n| Other | 8,000 | 8,000 |\n"}]
    assert problems("Growth = (10,000 − 8,000) ÷ 10,000 = 20.0%.", same) == []  # each figure sits under both years


def test_without_a_word_about_change_nothing_is_judged():
    assert problems("The difference is (10,000 − 8,000) ÷ 10,000 = 20.0% of FY2015 revenue.") == []


def test_vietnamese_answers_are_checked_the_same_way():
    assert len(problems("Tăng trưởng doanh thu = (10.000 − 8.000) ÷ 10.000 = 20,0%.")) == 1
    assert problems("Tăng trưởng doanh thu = (10.000 − 8.000) ÷ 8.000 = 25,0%.") == []
    assert len(problems("Doanh thu tăng (10,000 − 8,000) ÷ 10,000 = 20.0%.", [{"content": "Doanh thu năm 2015: 10.000; năm 2014: 8.000."}])) == 1


def test_a_cited_claim_in_the_answer_gives_the_periods():
    answer = "Revenue was 10,000 in FY2015 [1] and 8,000 in FY2014 [1]. Growth = (10,000 − 8,000) ÷ 10,000 = 20.0%."
    assert len(problems(answer, [{"content": "Revenues 10,000 8,000"}])) == 1


# ---------------------------------------------------------------- a written calculation whose result is wrong (found 14/11 with the P0 cases E01 and E03)
# Since the rewrite was removed, a wrong written result was only "not accepted" by rule B; but the number check could still accept the figure through another
# derivation of the stated figures: "(10,000 − 8,000) ÷ 8,000 = 20.0%" (should be 25.0%) passed as the 20 % decline from 10,000 to 8,000, and
# "2,000 / 12,000 = 20.0%" (should be 16.7%) as 1 % of 2,000. The answer states a false equation: it is reported, whatever else the figure matches.
def test_a_written_calculation_with_a_wrong_result_is_reported():
    found = check_formulas("Growth = (10,000 − 8,000) ÷ 8,000 = 20.0%.", TEXT)
    assert [f["kind"] for f in found] == ["arithmetic"] and "25.0%" in found[0]["problem"]
    found = check_formulas("ROA = 2,000 / 12,000 = 20.0%", [{"content": "Net income 2,000. Total assets 12,000."}])
    assert [f["kind"] for f in found] == ["arithmetic"] and "16.7%" in found[0]["problem"]


def test_a_percent_written_with_times_100_is_read_as_one():
    assert problems("Margin = 2,000 / 12,000 × 100 = 16.7%", []) == []
    found = check_formulas("Margin = 2,000 / 12,000 × 100 = 20.0%", [])
    assert [f["kind"] for f in found] == ["arithmetic"] and "16.67" in found[0]["problem"]


def test_right_calculations_and_unreadable_steps_are_not_reported():
    assert problems("ROA = 2,000 / 12,000 = 16.7%", [{"content": "Net income 2,000. Total assets 12,000."}]) == []
    assert problems("Total = 1,185 + 454 = 1,639.", []) == []
    assert problems("Turnover = 16,830 ÷ 2,694 = 6.25x.", []) == []
    assert problems("Margin = (1,185 + 454) ÷ 1,513 = 1,639 ÷ 1,513 = 1.08.", []) == []  # an equal step, then the result
    assert problems("EPS = 2.09 vs 2.55 = −18.0%.", []) == []  # a comparison, not a written calculation


def test_a_wrong_result_written_with_vietnamese_numbers_is_reported_and_a_right_one_is_not():
    assert problems("ROA = 2.000 / 12.000 = 16,7%", []) == []
    found = check_formulas("ROA = 2.000 / 12.000 = 20,0%", [])
    assert [f["kind"] for f in found] == ["arithmetic"]


# ---------------------------------------------------------------- in the checks of an answer
def test_verify_reports_it_for_the_one_repair_only_when_the_switch_is_on(monkeypatch):
    answer = "Growth = (10,000 − 8,000) ÷ 10,000 = 20.0% [1]."
    monkeypatch.setattr(settings, "FORMULA_CHECK_ENABLED", False)
    numbers, _, issues = verify(answer, TEXT, [])
    assert numbers["formulas"] == [] and not any("earlier" in i for i in issues)
    monkeypatch.setattr(settings, "FORMULA_CHECK_ENABLED", True)
    numbers, cites, issues = verify(answer, TEXT, [])
    assert len(numbers["formulas"]) == 1 and any("earlier period" in i for i in issues)
    note = flag_unverified(answer, numbers, cites, "en")
    assert "growth rate" in note and "⚠️" in note
    assert "tốc độ tăng trưởng" in flag_unverified(answer, numbers, cites, "vi")


def test_the_switch_is_on_by_default():
    """Turned on 14/11 by the owner after the free measurement: 6 reports on 317 stored answers, all genuine wrong divisions; none on 247 thinking-on answers."""
    from app.core.config import Settings

    assert Settings.model_fields["FORMULA_CHECK_ENABLED"].default is True
