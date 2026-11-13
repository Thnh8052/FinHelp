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
        answer = ROIC.format(**style)
        assert correct_calculations(answer, AMZN) == (answer, []), style  # every step is right: nothing to correct
        assert unverified(answer, AMZN) == [], style


def test_a_right_vietnamese_result_is_never_rewritten():
    answer = "Thuế suất = 1.197 / 11.261 = 10,63% [1]."  # before the fix "10,63" was read as 1063 and replaced by "11"
    assert correct_calculations(answer, AMZN) == (answer, [])


def test_a_wrong_vietnamese_result_is_corrected_in_its_own_style():
    fixed, fixes = correct_calculations("Vốn đầu tư = 23 495 + 43 549 = 66 044 [1].", AMZN)
    assert fixed == "Vốn đầu tư = 23 495 + 43 549 = 67 044 [1]." and [(f["was"], f["now"]) for f in fixes] == [("66 044", "67 044")]
    fixed, _ = correct_calculations("Thuế suất = 1.197 / 11.261 = 10,53% và NOPAT = 12.421 × 0,8937 = 11.100,6 [1].", AMZN)
    assert "= 10,63% và" in fixed and "11.100,6" in fixed


def test_a_result_is_not_rewritten_when_its_reading_is_not_certain():
    """Report-style thousands in an answer that writes its decimals with a comma: "23,495" may be 23495 or 23.495, and the two readings would
    write different corrections ("67 044" or "67"), so the wrong result is left for the number check to report (the model rewrites it)."""
    answer = "Thuế suất = 1,197 / 11,261 = 10,63%. Vốn đầu tư = 23,495 + 43,549 = 66 044 [1]."
    assert correct_calculations(answer, AMZN) == (answer, [])
    assert unverified(answer, AMZN) == ["66 044"]


def test_english_answers_read_as_before():
    assert evaluate("1 185 + 454")[0] == 1639  # a space also groups thousands in an English answer
    fixed, fixes = correct_calculations("Total = 1,185 + 454 = 1,649 [1].", AMD)
    assert fixed == "Total = 1,185 + 454 = 1,639 [1]." and len(fixes) == 1


def test_a_result_next_to_the_following_number_is_not_read_as_one_number():
    """Found on a stored answer (financebench_id_06247): "… + 737 = 374,133" must leave 737 and 374,133 two numbers, or the chain that follows loses its inputs."""
    chunks = [{"content": "Cost of sales 373,396. Inventories 46,092 and 41,433. LIFO reserve 43,783 and 43,046."}]
    answer = ("(46,092 + 41,433) ÷ 2 = 43,762.5; 43,783 − 43,046 = 737; 373,396 + 737 = 374,133; "
              "365 × 43,762.5 ÷ 374,133 = 15,973,312.5 ÷ 374,133 = **41.93** days [1].")
    fixed, fixes = correct_calculations(answer, chunks)
    assert [(f["was"], f["now"]) for f in fixes] == [("41.93", "42.69")] and "**42.69** days" in fixed
