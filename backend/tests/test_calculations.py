"""H1 of plan v2: the number check reads the calculations an answer writes out and accepts a figure that a written, correct calculation of checked
numbers produces (rule B). Code only, no model.

Code never rewrites a result (decided 14/11 after measuring 317 stored answers): with the model's thinking on, 247 answers and 325 written steps needed no rewrite,
and before the fix of 14/11 the rewrite changed right figures into wrong ones on 2 of 27 new answers. A wrong written result is left as it is and the number check
reports it ("unverified"), which costs the one repair call."""
from app.modules.generation.answer_check import numbers
from app.modules.generation.answer_check.calculations import evaluate, written_results
from app.modules.generation.answer_check.numbers import check_numbers

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
    assert evaluate("1 185 + 454")[0] == 1639  # a space also groups thousands in an English answer


def test_the_checks_never_rewrite_an_answer():
    """The rewrite of a wrong written result was removed: nothing in the number check returns a changed answer."""
    assert not hasattr(numbers, "correct_calculations")


def test_a_wrong_written_result_is_reported_not_rewritten():
    assert unverified("Total = 1,185 + 454 = 1,649 [1].", AMD) == ["1,649"]
    assert unverified("Leverage: 16,830 ÷ 2,694 = 5.99 times.", [{"content": "Net debt 16,830 and EBITDA 2,694"}]) == ["5.99"]


# ---------------------------------------------------------------- rule B: what a written, correct calculation establishes
def test_rule_b_accepts_a_written_sum_of_several_checked_numbers():
    answer = "Quick assets FY2017: 1,185 + 0 + 454 + 33 = 1,672 [1]."
    # 1,672 is no sum of TWO stated figures, so without rule B it was flagged and caused a rewrite
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


def test_a_percent_closed_by_a_bracket_is_a_percent():
    """"(2018: 8,364 ÷ 10,746 = 77.8%)": the closing bracket is not part of the unit. Read as 0.778 against 77.8 the right step was refused."""
    known = {8364.0, 10746.0}
    assert 77.8 in written_results("Gross margin (2018: 8,364 ÷ 10,746 = 77.8%).", known)
    assert 79.8 not in written_results("Gross margin (2018: 8,364 ÷ 10,746 = 79.8%).", known)


def test_a_lone_number_and_a_vs_comparison_are_not_written_calculations():
    """"EPS = 2.09 vs 2.55 = −18.0%" is no calculation of its own: nothing is established from it."""
    assert written_results("Diluted EPS = 2.09 vs 2.55 = −18.0% [1].", set()) == set()


def test_references_and_dates_are_not_calculations():
    assert written_results("See excerpt 4/6) = 1,424 and the note dated 4/6/2019 [1].", set()) == set()


def test_a_result_next_to_the_following_number_is_not_read_as_one_number():
    """Found on a stored answer (financebench_id_06247): "… + 737 = 374,133" must leave 737 and 374,133 two numbers, or the chain that follows loses its inputs."""
    chunks = [{"content": "Cost of sales 373,396. Inventories 46,092 and 41,433. LIFO reserve 43,783 and 43,046."}]
    answer = ("(46,092 + 41,433) ÷ 2 = 43,762.5; 43,783 − 43,046 = 737; 373,396 + 737 = 374,133; "
              "365 × 43,762.5 ÷ 374,133 = 15,973,312.5 ÷ 374,133 = **41.93** days [1].")
    assert unverified(answer, chunks) == ["41.93"]  # every step before the last is right and accepted; the wrong last result is reported, not rewritten


# ---------------------------------------------------------------- numbers written the Vietnamese way (found 13/11 on a stored ROIC answer: a repair call nobody needed)
AMZN = [{"content": "| | 2018 | 2017 |\n|---|---|---|\n| Operating income | 12,421 | 4,106 |\n| Provision for income taxes | 1,197 | 769 |\n"
                    "| Income before income taxes | 11,261 | 3,806 |\n| Long-term debt | 23,495 | 24,743 |\n| Total stockholders' equity | 43,549 | 27,709 |"}]
ROIC = ("Thuế suất = {a} / {b} = 10,63%. NOPAT = {c} × (1 − 0,1063) = {c} × 0,8937 = {d} [1]. "
        "Vốn đầu tư = {e} + {f} = {g} [1]. ROIC = {d} / {g} = 16,6% [1].")
SPACES = dict(a="1 197", b="11 261", c="12 421", d="11 100,6", e="23 495", f="43 549", g="67 044")   # 11 100,6: space groups, decimal comma
DOTS = dict(a="1.197", b="11.261", c="12.421", d="11.100,6", e="23.495", f="43.549", g="67.044")     # 11.100,6: dot groups, decimal comma
MIXED = dict(a="1,197", b="11,261", c="12,421", d="11 100,6", e="23,495", f="43,549", g="67,044")    # inputs as the report prints them, results the Vietnamese way


def test_a_calculation_written_with_vietnamese_numbers_is_accepted():
    for style in (SPACES, DOTS, MIXED):
        assert unverified(ROIC.format(**style), AMZN) == [], style


def test_a_right_vietnamese_percent_is_accepted_and_a_wrong_one_reported():
    assert unverified("Thuế suất = 1.197 / 11.261 = 10,63% [1].", AMZN) == []
    assert unverified("Vốn đầu tư = 23 495 + 43 549 = 66 044 [1].", AMZN) == ["66 044"]
    assert unverified("(năm 2018: 8 364 ÷ 10 746 = 77,8%)", [{"content": "Gross profit 8,364 and net revenues 10,746"}]) == []


def test_a_result_with_an_uncertain_reading_is_reported_not_guessed():
    """Report-style thousands in an answer that writes its decimals with a comma: "23,495" may be 23495 or 23.495; the wrong result is simply reported."""
    answer = "Thuế suất = 1,197 / 11,261 = 10,63%. Vốn đầu tư = 23,495 + 43,549 = 66 044 [1]."
    assert unverified(answer, AMZN) == ["66 044"]
