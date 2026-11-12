"""H1 of plan v2: the code calculator corrects the results of calculations an answer writes out, and the number check accepts a
figure that a written, correct calculation of checked numbers produces (rule B). Code only, no model."""
from app.modules.generation.answer_check.calculations import evaluate, fix
from app.modules.generation.answer_check.numbers import check_numbers, correct_calculations

AMD = [{"content": "| | 2018 | 2017 |\n|---|---:|---:|\n| Cash and cash equivalents | 1,078 | 1,185 |\n| Marketable securities | 78 | — |\n"
                   "| Accounts receivable, net | 1,235 | 454 |\n| Prepayment and receivables - related parties | 52 | 33 |\n"
                   "| Total current liabilities | 1,984 | 1,513 |"}]


def unverified(answer, chunks):
    return check_numbers(answer, chunks)["unverified"]


def test_safe_evaluator_reads_answer_notation_and_runs_nothing_else():
    assert evaluate("**1,185 + 454**")[0] == 1639
    assert evaluate("16,830 ÷ 2,694")[0] == 16830 / 2694
    assert evaluate("337 − (33)")[0] == 370  # accounting brackets: a lone number in brackets is negative
    assert evaluate("365 × 43,762.5 ÷ 374,133")[0] == 365 * 43762.5 / 374133
    assert evaluate("__import__('os')") is None and evaluate("2 ** 10") is None


def test_wrong_division_is_corrected_everywhere_it_appears():
    answer = ("| Quick ratio | 1.74 |\n\nFY2017: (1,185 + 0 + 454 + 33) ÷ 1,513 = 1,672 ÷ 1,513 = 1.74\n\nThe quick ratio was 1.74.\n"
              '<answer_meta>{"status": "answered", "short_answer": "Quick ratio 1.74", "citations": [1]}</answer_meta>')
    fixed, fixes = correct_calculations(answer, AMD)
    assert [(f["was"], f["now"]) for f in fixes] == [("1.74", "1.11")]
    assert "1.74" not in fixed and fixed.count("1.11") == 4  # table, step, conclusion and short_answer


def test_a_correct_answer_is_left_alone():
    answer = "FY2018: (1,078 + 78 + 1,235) ÷ 1,984 = 2,391 ÷ 1,984 = 1.21 [1]."
    assert correct_calculations(answer, AMD) == (answer, [])


def test_inputs_not_in_the_excerpts_are_not_rewritten():
    answer = "The ratio is 9,999 ÷ 1,513 = 7.00."  # 9,999 is printed nowhere: the step cannot be trusted, so it is not touched
    assert correct_calculations(answer, AMD) == (answer, [])


def test_references_and_dates_are_not_calculations():
    answer = "See excerpt 4/6) = 1,424 and the note dated 4/6/2019 [1]."
    assert fix(answer, set())[1] == []


def test_ratio_with_a_suffix_is_corrected():
    chunks = [{"content": "Net debt 16,830 and EBITDA 2,694"}]
    fixed, fixes = correct_calculations("Leverage: 16,830 ÷ 2,694 = 5.99x.", chunks)
    assert fixed == "Leverage: 16,830 ÷ 2,694 = 6.25x." and len(fixes) == 1


def test_rule_b_accepts_a_written_sum_of_several_checked_numbers():
    answer = "Quick assets FY2017: 1,185 + 0 + 454 + 33 = 1,672 [1]."
    # today's check: 1,672 is no sum of TWO stated figures, so it was flagged and caused a rewrite
    assert unverified(answer, AMD) == []
    assert check_numbers(answer, AMD)["written"] == 1


def test_rule_b_accepts_standard_constants_in_a_written_calculation():
    chunks = [{"content": "Average accounts payable 43,762.5; cost of sales 374,133"}]
    assert unverified("DPO = 365 × 43,762.5 ÷ 374,133 = 42.69 days.", chunks) == []


def test_rule_b_lets_no_wrong_result_through():
    answer = "Quick assets FY2017: 1,185 + 454 + 33 = 1,700 [1]."
    assert unverified(answer, AMD) == ["1,700"]


def test_rule_b_needs_every_input_checked():
    answer = "Adjusted assets: 1,185 + 7,777 = 8,962 [1]."  # 7,777 is invented, so its sum is not accepted either
    assert set(unverified(answer, AMD)) == {"7,777", "8,962"}
