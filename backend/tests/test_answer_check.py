from app.modules.generation.answer_check.numbers import check_numbers

TABLE = [{"content": "| | 2019 | 2015 |\n|---|---:|---:|\n| Income from operations | 2,321 | 2,197 |\n| Total revenue | 10,800 | 8,592 |\n"
                     "| Net income (loss) | (1,016) | 1,725 |"}]


def status(answer, chunks=TABLE):
    return {f["text"]: f["status"] for f in check_numbers(answer, chunks)["figures"]}


def test_printed_figures_and_scale_change():
    s = status("Operating income was $2,321 million in FY2019 [1], or about $2.3 billion, and revenue $10.8 billion.")
    assert s == {"$2,321": "verified", "$2.3": "verified", "$10.8": "verified"}


def test_parenthesised_loss_matches_without_sign():
    assert status("The company lost $1,016 million in 2019.") == {"$1,016": "verified"}


def test_difference_percent_and_growth_are_derived():
    s = status("Operating income rose from $2,197M to $2,321M: +$124M, or 5.64%.")
    assert s == {"$2,197": "verified", "$2,321": "verified", "$124": "derived", "5.64%": "derived"}


def test_change_needs_its_inputs_in_the_answer():
    # 124 = 2,321 - 2,197 only counts when the answer states both: any two table numbers would cover almost any value
    assert status("Operating income rose by $124 million.")["$124"] == "unverified"


def test_percent_of_an_amount():
    chunks = TABLE + [{"content": "The statutory tax rate was 15.0%."}]
    assert status("At a 15.0% rate on revenue of $10,800M, the implied amount is $1,620M.", chunks)["$1,620"] == "derived"


def test_ratio_from_figures_the_answer_states():
    # margin = 2,321 / 10,800 = 21.49 %; without the two inputs in the answer the margin is not derived from table numbers
    assert status("Operating income of $2,321 million on revenue of $10,800 million: a 21.5% margin.")["21.5%"] == "derived"
    assert status("The operating margin was 21.5% in FY2019.")["21.5%"] == "unverified"


def test_invented_figure_is_unverified():
    report = check_numbers("Operating income was $3,456 million in FY2019.", TABLE)
    assert report["unverified"] == ["$3,456"] and report["checked"] == 1


def test_years_citations_list_markers_and_meta_are_skipped():
    answer = "1. In FY2015 [2] and 2019, see note 5.\n<answer_meta>{\"short_answer\": \"$9,999\"}</answer_meta>"
    assert check_numbers(answer, TABLE)["checked"] == 0


def test_no_excerpts_leaves_figures_unverified():
    assert check_numbers("Revenue was $10,800 million.", [])["unverified"] == ["$10,800"]


# Statements that group thousands with a space (Canadian / French style, e.g. Suncor "89 913") and answers in Vietnamese ("89.913")
SPACED = [{"content": "| ($ millions) | December 31 2025 | December 31 2024 |\n|---|---:|---:|\n| Total assets | 89 913 | 89 784 |\n| Equity | 45 124 | 44 514 |"}]


def test_vietnamese_dot_thousands_matches_a_space_grouped_statement():
    assert status("Tổng tài sản là 89.913 triệu và vốn chủ sở hữu 45.124 triệu.", SPACED) == {"89.913": "verified", "45.124": "verified"}


def test_space_grouped_figure_is_one_number_not_two_fragments():
    assert status("Total assets were 89 913 million and equity 45 124 million.", SPACED) == {"89 913": "verified", "45 124": "verified"}
    # 89 and 913 each appear in this excerpt, but 89 913 does not: it used to pass as two fragments
    assert status("Total assets were 89 913 million.", [{"content": "Total assets 89 000, other items 913"}]) == {"89 913": "unverified"}


def test_a_wrong_figure_in_either_notation_is_still_caught():
    assert status("Tổng tài sản là 89.314 triệu.", SPACED) == {"89.314": "unverified"}
    assert status("Total assets were 89 314 million.", SPACED) == {"89 314": "unverified"}


def test_excerpt_in_vietnamese_notation_matches_an_english_answer():
    vi_table = [{"content": "| Tổng tài sản | 89.913 | 89.784 |"}]
    assert status("Total assets were 89,913 million.", vi_table) == {"89,913": "verified"}


def test_derived_figure_uses_the_reading_that_matched():
    # 89.913 - 89.784 = 129 only if 89.913 is read as 89,913; the sum of the two stated figures must follow the matched reading
    s = status("Tổng tài sản tăng từ 89.784 lên 89.913 triệu, tức tăng 129 triệu.", SPACED)
    assert s == {"89.784": "verified", "89.913": "verified", "129": "derived"}


def test_columns_of_a_flattened_row_are_not_merged_for_the_excerpt():
    assert status("Cash was 3 650 million.", [{"content": "Cash and cash equivalents 3 650 3 484"}]) == {"3 650": "verified"}


# ---------------------------------------------------------------- the day of a date is not a figure (found 13/11: "ended June 30, 2021" made a repair call over the figure 30)
DATES = ["Microsoft's fiscal year ended June 30, 2021.", "Microsoft's fiscal year ended 30 June 2021.", "The year ended 2021-06-30 (FY2021).", "Oracle ended on May 31st, 2021.",
         "Kết thúc ngày 30 tháng 6 năm 2021.", "Tại ngày 30/06/2021, báo cáo kết thúc.", "As of Dec. 31 the year closed.", "Năm tài chính kết thúc ngày 31/12."]


def test_the_day_of_a_date_is_not_a_figure_to_verify():
    for text in DATES:
        assert check_numbers(text, TABLE)["figures"] == [], text


def test_a_figure_beside_a_word_that_only_starts_like_a_month_is_still_checked():
    for text, shown in (("Revenue decreased 25 million [1].", "25"), ("The market 30 percent share.", "30"), ("Margins declined 18 points.", "18"), ("Sales in marginal 45 stores.", "45")):
        assert [f["text"] for f in check_numbers(text, TABLE)["figures"]] == [shown], text
    assert check_numbers("In May 25% of stores closed.", TABLE)["unverified"] == ["25%"]  # a percent after a month name is a figure, not a day


def test_a_date_next_to_a_wrong_figure_does_not_hide_it():
    out = check_numbers("The year ended June 30, 2021 had net income of 7,777 million [1].", TABLE)
    assert out["unverified"] == ["7,777"]


# ---------------------------------------------------------------- a multiple with its x glued to it ("5.99x") is a figure (L21: the scanner took it for part of a word, so a wrong one passed unseen)
TURNOVER = [{"content": "| | 2019 | 2018 |\n|---|---:|---:|\n| Cost of products sold | 16,830 | 16,200 |\n| Inventories | 2,694 | 2,500 |"}]


def test_a_multiple_with_the_x_glued_to_it_is_a_figure():
    for text in ("The turnover was 6.25x.", "The turnover was 6.25X.", "Turnover: **6.25x**", "Turnover: 6.25x, up", "Turnover (6.25x)", "Turnover 6.25x\nnext line"):
        assert [f["text"] for f in check_numbers(text, TURNOVER)["figures"]] == ["6.25"], text


def test_a_wrong_multiple_is_caught_and_a_right_one_is_not_flagged():
    assert check_numbers("Inventory turnover was 7.52x [1].", TURNOVER)["unverified"] == ["7.52"]
    right = check_numbers("Cost of products sold of $16,830 million over inventories of $2,694 million gives a turnover of 6.25x [1].", TURNOVER)
    assert right["unverified"] == [] and right["derived"] == 1  # the quotient of two figures the answer states
    assert check_numbers("Turnover = 16,830 ÷ 2,694 = 6.25x [1].", TURNOVER)["unverified"] == []  # a written calculation that checks
    assert check_numbers("Turnover = 16,830 ÷ 2,694 = 7.52x [1].", TURNOVER)["unverified"] == ["7.52"]  # one that does not, is not accepted


def test_an_x_inside_a_word_or_a_product_or_a_count_is_not_a_multiple():
    for text in ("The 6.25xyz code.", "A6.25x sample.", "Sized 6.25x3.5 inches.", "The 6.25xs.", "About 2x as much, a 10x jump."):
        assert check_numbers(text, TURNOVER)["figures"] == [], text  # a word, a product of two sizes, or a small count: nothing to verify


# ------------------------------------------------------------------ rounding of figures the answer derives (system test 18/11, D1)
# An answer wrote "0.1417" for the change between margins printed as 3.3299 and 3.1883: the printed numbers give 0.1416, the unrounded margins give
# 0.1417. The check called it unverified and the whole answer was written again (53.6 s). Two rounded numbers can be one unit of their last digit off.
MARGINS = [{"content": "| | 2020 | 2015 |\n|---|---:|---:|\n| Operating margin (%) | 3.1883 | 3.3299 |"}]


def test_a_difference_of_two_rounded_figures_may_be_one_unit_of_the_last_digit_off():
    s = status("The margin was 3.3299 in 2015 and 3.1883 in 2020: it changed by 0.1417 points [1].", MARGINS)
    assert s["0.1417"] == "derived"  # 3.3299 - 3.1883 = 0.1416 from the printed numbers
    assert status("The margin was 3.3299 in 2015 and 3.1883 in 2020: it changed by 0.1416 points [1].", MARGINS)["0.1416"] == "derived"


def test_a_difference_two_units_off_is_still_unverified():
    s = status("The margin was 3.3299 in 2015 and 3.1883 in 2020: it changed by 0.1418 points [1].", MARGINS)
    assert s["0.1418"] == "unverified"
    assert status("The margin was 3.3299 in 2015 and 3.1883 in 2020: it changed by 0.1414 points [1].", MARGINS)["0.1414"] == "unverified"


def test_a_whole_number_difference_must_still_be_exact():
    # amounts printed in millions are exact table values: their difference has no rounding in it (2,321 - 2,197 = 124)
    assert status("Operating income rose from $2,197M to $2,321M: +$124M.")["$124"] == "derived"
    assert status("Operating income rose from $2,197M to $2,321M: +$125M.")["$125"] == "unverified"
    assert status("Operating income rose from $2,197M to $2,321M: +$123M.")["$123"] == "unverified"


def test_one_decimal_figures_keep_half_a_unit():
    # at one decimal a whole unit (0.1) is wide: 55.1 matched the average of two other figures (55.0) by chance, and planted wrong figures
    # (13.5, 25.3, 56.9) slipped through the same way in the replay of 923 stored answers
    table = [{"content": "| Cost of sales (%) | 53.8 | 56.2 |"}]
    assert status("Cost of sales was 53.8% and 56.2%; the figure was 55.1%.", table)["55.1%"] == "unverified"


def test_a_whole_number_read_as_three_decimals_keeps_half_a_unit():
    # "36,701" can be read as 36.701 (Vietnamese marks): that reading must not get the wider tolerance and match 36,700 = 34,300 + 2,400 at another scale
    table = [{"content": "| Revenue | 34,300 | Other | 2,400 |"}]
    assert status("Revenue was 34,300 and other income 2,400, in all 36,701.", table)["36,701"] == "unverified"


# ---------------------------------------------------------------- references read as figures (system test 18/11, T3: replay of 923 stored answers)
def test_pages_notes_items_and_short_fiscal_years_are_not_figures():
    for answer in ("AMD's FY22 (year ended December 31, 2022) quick ratio was about 1.6x.",
                   "Boeing's FY2022 10-K (Note 21, page 113) reports ongoing legal matters.",
                   "The table of contents lists Item 3 at page 24; the text comes from page 25.",
                   "Dividends: 10-K, page 68/92, and page 168; pages 108-109.",
                   "Báo cáo FY22 (thuyết minh 21, trang 113) nêu các vụ kiện.",
                   "Adjusted EPS (Diluted), Full Year 2022 % change: 3.6%"):
        report = check_numbers(answer, TABLE)
        assert not {"22", "21", "113", "24", "25", "68", "92", "168", "108", "109", "2022 %"} & set(report["unverified"]), answer
    assert check_numbers("Adjusted EPS (Diluted), Full Year 2022 % change: 3.6%", TABLE)["unverified"] == ["3.6%"]


def test_a_figure_after_a_reference_word_is_still_checked():
    assert check_numbers("Note: revenue was $3,456 million (page 4).", TABLE)["unverified"] == ["$3,456"]
    assert check_numbers("Ghi chú: doanh thu 3.456 triệu USD (trang 4).", TABLE)["unverified"] == ["3.456"]
    assert check_numbers("Page views rose 113% in FY2019.", TABLE)["unverified"] == ["113%"]


# ---------------------------------------------------------------- figures that were never checked (19/11)
LOSS = [{"content": "| Net income (loss) | 1,725 | (45) |\n| Revenue | 1,999 | 1,725 |"}]


def test_a_small_loss_in_brackets_before_a_unit_is_a_figure_not_a_clause_marker():
    """"(45) million" was read like "(1) Includes ...": never checked, so a wrong "(47) million" went through."""
    assert status("The company lost (45) million in 2019 [1].", LOSS) == {"(45)": "verified"}
    assert status("Công ty lỗ (45) triệu USD năm 2019 [1].", LOSS) == {"(45)": "verified"}
    assert check_numbers("The company lost (47) million in 2019 [1].", LOSS)["unverified"] == ["(47)"]
    assert check_numbers("(1) Includes restructuring costs [1].", LOSS)["checked"] == 0  # a clause marker stays one


def test_an_amount_written_like_a_year_before_a_unit_is_a_figure():
    """"1999 million" was skipped as the year 1999."""
    assert status("Revenue was 1999 million in 2019 [1].", LOSS) == {"1999": "verified"}
    assert status("Doanh thu năm 2019 là 1999 triệu USD [1].", LOSS) == {"1999": "verified"}
    assert check_numbers("Revenue was 1998 million in 2019 [1].", LOSS)["unverified"] == ["1998"]
    assert check_numbers("In 2019 and 2020 revenue grew [1].", LOSS)["checked"] == 0  # years stay years


def test_a_year_heading_an_amount_with_its_currency_is_a_year():
    """E2E planner fb_expert_012 (19/11): "the table adds later years: 2023 USD 159 million, 2024 USD 473 million" put 2023 and 2024 on the warning
    line: the "USD" after the year belongs to the amount that follows it, so the year stays a year. "1999 million" / "1999 USD" stay amounts."""
    chunks = [{"content": "| 2023 | 2024 | Thereafter |\n| 159 | 473 | 7,708 |"}]
    for text in ("The table adds later years: 2023 USD 159 million, 2024 USD 473 million and USD 7,708 million thereafter [6].",
                 "Later years: 2023 USD 159m and 2024 $473m [6].", "Các năm sau: 2023 USD 159 triệu, 2024 USD 473 triệu [6]."):
        assert check_numbers(text, chunks)["unverified"] == [], text
    assert check_numbers("Later years: 2023 USD 169 million [6].", chunks)["unverified"] == ["169"]  # the amount itself is still checked
    assert check_numbers("Revenue was 1998 USD million in 2019 [1].", LOSS)["unverified"] == ["1998"]
