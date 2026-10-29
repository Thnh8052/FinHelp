from app.services.answer_check.numbers import check_numbers

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
