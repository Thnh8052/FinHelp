"""A year range is not a subtraction (v4/v5 measurement 19/11): "thay đổi 2015–2020 ≈ +3.8 điểm phần trăm" was read as 2015 − 2020 = +3.8 and put a
"calculation gives another result" warning on a right answer. A range runs from an earlier year to a later one; a real subtraction of years is written
later minus earlier ("2020 − 2015 = 5") and is still checked."""
from app.modules.generation.answer_check.calculations import wrong_steps


def test_a_year_range_before_a_result_is_not_checked_as_a_subtraction():
    for text in ("- Amazon: thay đổi 2015–2020 ≈ +3.8 điểm phần trăm.", "Change 2015-2020 = +3.8 percentage points.",
                 "Amazon improved more: +3.84 points over 2015 - 2020 = the widest gap.", "Growth FY2018–FY2020 = 12.5%."):
        assert wrong_steps(text) == [], text


def test_a_subtraction_of_years_and_other_subtractions_are_still_checked():
    assert wrong_steps("Years elapsed: 2020 − 2015 = 6.")  # later minus earlier: arithmetic, and wrong
    assert wrong_steps("Years elapsed: 2020 − 2015 = 5.") == []
    assert wrong_steps("Net: 4,258 - 56 = 4,100 million.")  # not years: still checked
