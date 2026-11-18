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


# ---------------------------------------------------------------- false alarms on right answers (system test 18/11, T3: replay of 923 stored answers)
from app.modules.generation.answer_check.calculations import wrong_steps  # noqa: E402

MARGINS = [{"content": "Net income 116, 131 and 155; revenue 6,489, 7,500 and 7,017"}]


def test_an_average_of_percents_is_a_written_calculation():
    """financebench_id_07966: "(1.7876% + 1.7467% + 2.2095%) / 3 = 1.9146%": a "%" between a number and its operator hid the calculation."""
    en = ("FY2019: 116 / 6,489 × 100 = 1.7876%\nFY2018: 131 / 7,500 × 100 = 1.7467%\nFY2017: 155 / 7,017 × 100 = 2.2095%\n"
          "Average: (1.7876% + 1.7467% + 2.2095%) / 3 = {avg}, rounded to 1.9%.")
    vi = ("Năm 2019: 116 / 6.489 × 100 = 1,7876%\nNăm 2018: 131 / 7.500 × 100 = 1,7467%\nNăm 2017: 155 / 7.017 × 100 = 2,2095%\n"
          "Trung bình: (1,7876% + 1,7467% + 2,2095%) / 3 = {avg}, làm tròn 1,9%.")
    assert unverified(en.format(avg="1.9146%"), MARGINS) == []
    assert unverified(vi.format(avg="1,9146%"), MARGINS) == []
    assert "1.9846%" in unverified(en.format(avg="1.9846%"), MARGINS)
    assert "1,9846%" in unverified(vi.format(avg="1,9846%"), MARGINS)


def test_a_difference_of_bracketed_losses_is_a_written_calculation():
    """mdg_b16_005: "(33) − (498) = 465": a closing bracket between a number and its operator hid the calculation."""
    chunks = [{"content": "| Net income (loss) | (33) | (498) |"}]
    assert unverified("Net income FY2016→FY2017: (33) − (498) = **465 USD million improvement**.", chunks) == []
    assert unverified("Lợi nhuận ròng 2016 → 2017: (33) − (498) = **465 triệu USD**.", chunks) == []
    assert unverified("Net income FY2016→FY2017: (33) − (498) = **565 USD million improvement**.", chunks) == ["565"]


TURNOVER = [{"content": "Cost of sales 24,576; inventories 7,367 and 6,854; cash 4,258, short-term investments 56, receivables 4,947; current liabilities 10,936"}]


def test_unit_words_inside_a_written_calculation_are_read_through():
    """financebench_id_04080 and 00807: "million", "times", "days" between the numbers cut the calculation into pieces nobody could check."""
    assert unverified("Calculation: $24,576 million ÷ (($7,367 million + $6,854 million) ÷ 2) = **3.46 times**.", TURNOVER) == []
    assert unverified("Vòng quay = 24.576 triệu USD ÷ ((7.367 triệu USD + 6.854 triệu USD) ÷ 2) = 3,46 lần.", TURNOVER) == []
    assert unverified("Quick assets = $4,258 million + $56 million + $4,947 million = $9,261 million", TURNOVER) == []
    assert unverified("Tài sản nhanh = 4.258 triệu + 56 triệu + 4.947 triệu = 9.261 triệu USD; tỷ số nhanh = 9.261 / 10.936 = 0,85.", TURNOVER) == []
    assert unverified("Calculation: $24,576 million ÷ (($7,367 million + $6,854 million) ÷ 2) = **3.66 times**.", TURNOVER) == ["3.66"]
    assert unverified("Quick assets = $4,258 million + $56 million + $4,947 million = $9,361 million", TURNOVER) == ["$9,361"]


def test_the_arithmetic_check_reads_through_unit_words_too():
    found = wrong_steps("Quick assets = $4,258 million + $56 million + $4,947 million = $9,361 million.")
    assert len(found) == 1 and found[0][2].startswith("9,261")
    assert wrong_steps("Quick assets = $4,258 million + $56 million + $4,947 million = $9,261 million.") == []


def test_a_percent_among_plain_numbers_may_be_a_fraction():
    """financebench_id_06247: "495,761 × (1 − 24.7%) = 373,308.0" was evaluated with 24.7 for 24.7% and refused."""
    chunks = [{"content": "Net sales 495,761; gross profit margin 24.7%"}]
    assert unverified("FY2018 COGS = 495,761 × (1 − 24.7%) = 373,308.0 million.", chunks) == []
    assert unverified("Giá vốn năm 2018 = 495.761 × (1 − 24,7%) = 373.308,0 triệu.", chunks) == []
    assert unverified("FY2018 COGS = 495,761 × (1 − 24.7%) = 383,308.0 million.", chunks) == ["383,308.0"]


def test_a_rounded_result_of_a_right_calculation_is_accepted():
    """fb_think 04302 and mdg_b16_007: "= 55.115% ≈ 55.1%" and "= 1.2 (1.205 before rounding)": the rounding of a right result is right."""
    pcts = [{"content": "Cost of sales as a percent of revenue: 56.161%, 55.424%, 53.759%"}]
    assert unverified("Average: (56.161% + 55.424% + 53.759%) ÷ 3 = 55.115% ≈ 55.1%. The three-year average is 55.1%.", pcts) == []
    assert unverified("Trung bình: (56,161% + 55,424% + 53,759%) ÷ 3 = 55,115% ≈ 55,1%. Trung bình ba năm là 55,1%.", pcts) == []
    assert unverified("FY2018: (1,078 + 78 + 1,235) ÷ 1,984 = 1.2 (1.205 before rounding).", AMD) == []
    # one unit of the last digit is not a rounding
    assert unverified("Average: (56.161% + 55.424% + 53.759%) ÷ 3 = 55.115%. The three-year average is 55.3%.", pcts) == ["55.3%"]
    assert unverified("FY2018: (1,078 + 78 + 1,235) ÷ 1,984 = 1.2 (1.215 before rounding).", AMD) == ["1.215"]


def test_bracketed_percents_are_negative_and_a_percent_after_the_bracket_is_a_percent():
    """Found by the replay of this fix: "(5,642) / 58,158 = (9.7)%" and "3.2% + (1.4%) + (3.8%) = (2.0)" are right and were reported as wrong."""
    assert wrong_steps("Gross margin = (5,642) / 58,158 = (9.7)%.") == []
    assert wrong_steps("Biên lợi nhuận gộp = (5.642) / 58.158 = (9,7)%.") == []
    assert wrong_steps("Net effect: 3.2% + (1.4%) + (3.8%) = (2.0)%.") == []
    assert wrong_steps("Tác động ròng: 3,2% + (1,4%) + (3,8%) = (2,0)%.") == []
    assert len(wrong_steps("Gross margin = (5,642) / 58,158 = (8.7)%.")) == 1
    assert len(wrong_steps("Net effect: 3.2% + (1.4%) + (3.8%) = (2.6)%.")) == 1


def test_a_sum_or_difference_of_rounded_figures_may_be_off_by_their_rounding():
    """"34.6% − 36.8% = −2.1": the operands are rounded (34.64 − 36.75 = −2.11), so the printed result is not a wrong step; −2.4 is."""
    assert wrong_steps("Gross margin change: 34.6% − 36.8% = −2.1 percentage points.") == []
    assert wrong_steps("Thay đổi biên gộp: 34,6% − 36,8% = −2,1 điểm phần trăm.") == []
    assert len(wrong_steps("Gross margin change: 34.6% − 36.8% = −2.4 percentage points.")) == 1
    assert len(wrong_steps("Thay đổi biên gộp: 34,6% − 36,8% = −2,4 điểm phần trăm.")) == 1


def test_whole_table_values_are_exact_so_their_difference_is_too():
    """Found by the planted-error replay: "1,824 − 1,806 = 19" (a planted 18) got through when every operand counted half a unit."""
    assert len(wrong_steps("Change: 1,824 − 1,806 = 19 million.")) == 1
    assert len(wrong_steps("Thay đổi: 1 824 − 1 806 = 19 triệu.")) == 1
    assert len(wrong_steps("Change: (907 + 128) − (930 + 127) = −24.")) == 1


# ---------------------------------------------------------------- the last easy false alarms of the replay (19/11)
BOEING = [{"content": "Total revenues 58,158; cost of products 54,568; cost of services 9,232"}]


def test_a_dollar_sign_before_an_accounting_bracket_is_read():
    """financebench_id_00678: "= $(5,642) million" was not read as a result, so the loss and the margin from it were flagged."""
    en = "Gross profit FY2020 = 58,158 − 54,568 − 9,232 = {gp} million; margin = (5,642) / 58,158 = (9.7)%."
    vi = "Lợi nhuận gộp năm 2020 = 58.158 − 54.568 − 9.232 = {gp} triệu; biên = (5.642) / 58.158 = (9,7)%."
    assert unverified(en.format(gp="$(5,642)"), BOEING) == []
    assert unverified(vi.format(gp="$(5.642)"), BOEING) == []
    assert "$(5,742)" in unverified(en.format(gp="$(5,742)"), BOEING)


def test_square_brackets_group_like_round_ones_and_citations_stay_citations():
    """luna_fb 04412 and 04103: "65,398 ÷ [(47,528 + 50,710) ÷ 2] = 1.33" was not read."""
    chunks = [{"content": "Revenue 65,398; assets 47,528 and 50,710; inventories 1,642.2 and 1,559.3; cost of sales 11,108.4"}]
    assert unverified("Turnover = 65,398 ÷ [(47,528 + 50,710) ÷ 2] = 1.33 times [1].", chunks) == []
    assert unverified("Vòng quay = 65.398 ÷ [(47.528 + 50.710) ÷ 2] = 1,33 lần [1].", chunks) == []
    assert unverified("DIO = 365 × [(1,642.2 + 1,559.3) ÷ 2] ÷ 11,108.4 = **52.60** [1, 2]", chunks) == []
    assert unverified("Turnover = 65,398 ÷ [(47,528 + 50,710) ÷ 2] = 1.43 times [1].", chunks) == ["1.43"]
    assert written_results("Revenue 1,185 [1] + 454 [2] = 1,639", {1185.0, 454.0}) == {1185.0, 454.0}  # a citation is no bracket


def test_an_exponent_is_evaluated():
    """fb150 qwen3_v3_5 03718: a growth rate "(65,984 / 65,398)^(1/2) − 1 = 0.00447 = 0.4%" was not read."""
    chunks = [{"content": "Net sales 65,984 and 65,398"}]
    assert unverified("CAGR = (65,984 / 65,398)^(1/2) − 1 = 0.00447 = 0.4%", chunks) == []
    assert unverified("CAGR = (65.984 / 65.398)^(1/2) − 1 = 0,00447 = 0,4%", chunks) == []
    assert "0.00547" in unverified("CAGR = (65,984 / 65,398)^(1/2) − 1 = 0.00547 = 0.5%", chunks)
    assert len(wrong_steps("CAGR = (65,984 / 65,398)^(1/2) − 1 = 0.00547.")) == 1
    assert evaluate("2^(3)")[0] == 8  # "(3)" after an exponent is not an accounting negative
    assert evaluate("(-8)^(1/3)") is None and evaluate("10^400") is None  # no complex number, no overflow


def test_a_change_of_percents_written_in_basis_points_is_right():
    """Held-out chat answer msg_b9a48a4e (19/11): "11,20% − 11,02% = 18 điểm cơ bản" is right (0.18 points = 18 basis points) and was reported."""
    assert wrong_steps("Biên gộp tăng: 11,20% − 11,02% = 18 điểm cơ bản [2].") == []
    assert wrong_steps("Gross margin rose: 11.20% − 11.02% = 18 basis points [2].") == []
    assert len(wrong_steps("Gross margin rose: 11.20% − 11.02% = 28 basis points [2].")) == 1
    assert unverified("Gross margin rose from 11.02% to 11.20% [1]: 11.20% − 11.02% = 18 bps.", [{"content": "margin 11.20% and 11.02%"}]) == []
