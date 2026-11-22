"""The 2026-10-20 extension of error 12 (values rebuilt into columns from the PDF words), ported from the research postprocess
(FinAnalyst-AI/tests/test_docling_postprocess_12.py, src/parsing/postprocess.py), which the backend lacked since the module split.

Measured 20/11 (experiments/results/docs/parsing/parsing_fixes_research.md): the backend postprocess run on the 134 study documents gave worse
tables than the research one on 67 pages of 23 documents and better on none (712 vs 489 cells holding only "$", 350 vs 302 value cells holding two
amounts, e.g. Coca-Cola 2021 p120 "| | 36 87 |" for "| 36 | 87 |"), and every retrieval measurement was made on the research output.
The extension: (a) a "$" printed at the left edge of its column, close to the previous column's number, joins two columns (Coca-Cola 2022 p63):
when the old split cannot place the header labels, the values are split again by their number part only (`column_layouts`);
(b) a header cell spanning from the "$" column over leaves with their own labels is a group heading, not a leaf (Coca-Cola 2022 p98);
(c) a header with the wrong number of columns is also repaired (`relaxed_names`) on tables whose rows were not rebuilt, with stricter conditions;
(e) a currency sign glued after a number ("(29.8)$", General Mills 2022 p62) is cut off (`split_signs`).
Not ported: (d) `find_pdf` (the pipeline hands the PDF path to the postprocess).
"""
from collections import Counter

import pytest

import app.modules.ingestion.postprocess.table_regrid as tr
import app.modules.ingestion.postprocess.table_values as tv
from app.modules.ingestion.postprocess.grids import Grid, TableCell, row_cells


# --- (e) split_signs: a currency sign glued after the digits ---

def test_split_signs_cuts_a_trailing_currency_sign_into_a_touching_word():
    out = tv.split_signs([(381.2, 396.1, "(29.8)$")])
    assert [text for _, _, text in out] == ["(29.8)", "$"]
    assert out[0][0] == 381.2 and out[1][1] == 396.1 and out[0][1] == out[1][0]  # the two words touch: no gap, no overlap
    assert 381.2 < out[0][1] < 396.1


@pytest.mark.parametrize("text, why", [
    ("$", "a sign on its own"),
    ("$1,234", "a sign before the number is one value"),
    ("US$", "no digit"),
    ("12#", "'#' is not a currency sign"),
    ("1,234", "a plain number"),
])
def test_split_signs_leaves_other_words(text, why):
    assert tv.split_signs([(10.0, 20.0, text)]) == [(10.0, 20.0, text)], why


# --- (a) group_value_words also returns where the number part starts ---

def test_group_value_words_records_where_the_number_starts():
    groups = tv.group_value_words([(390.0, 394.0, "$"), (430.4, 452.4, "43,004"), (496.9, 518.9, "15,357")])
    assert groups == [(390.0, 452.4, ["$", "43,004"], 430.4), (496.9, 518.9, ["15,357"], 496.9)]


def test_group_value_words_suffix_keeps_the_start_of_the_number():
    groups = tv.group_value_words([(100.0, 104.0, "$"), (110.0, 120.0, "(13)"), (300.0, 310.0, "40.1"), (311.0, 315.0, "%")])
    assert groups == [(100.0, 120.0, ["$", "(13)"], 110.0), (300.0, 315.0, ["40.1", "%"], 300.0)]


def test_group_value_words_splits_a_glued_sign_before_grouping():
    """General Mills 2022 p62: "(29.8)$ -" is the value "(29.8)" and then "$ -" of the next column."""
    groups = tv.group_value_words([(381.2, 396.1, "(29.8)$"), (410.5, 412.1, "-")])
    assert [tokens for _, _, tokens, _ in groups] == [["(29.8)"], ["$", "-"]]
    assert groups[1][3] == 410.5


# --- (a) column_layouts ---

def coca_cola_groups(dollar_2021=453.0):
    """Coca-Cola 2022 p63: "$" at the left edge of its column, numbers right-aligned; the 2021 "$" is less than 3 points from the 2022 number."""
    row1 = tv.group_value_words([(390.0, 394.0, "$"), (430.4, 452.4, "43,004"), (dollar_2021, dollar_2021 + 4.0, "$"), (496.9, 518.9, "38,655"),
                                 (522.9, 526.9, "$"), (563.3, 585.3, "33,014")])
    row2 = tv.group_value_words([(430.4, 452.4, "18,000"), (496.9, 518.9, "15,357"), (563.3, 585.3, "13,433")])
    return row1 + row2


def test_column_layouts_adds_number_only_columns_when_signs_bridge_two_columns():
    layouts = tv.column_layouts(coca_cola_groups())
    assert len(layouts) == 2
    whole, _ = layouts[0]
    numbers, reach = layouts[1]
    assert whole == [[390.0, 518.9], [522.9, 585.3]]  # old split: the 2021 "$" joins the 2022 column to the 2021 column
    assert numbers == [[430.4, 452.4], [496.9, 518.9], [563.3, 585.3]]
    assert reach == [[390.0, 452.4], [453.0, 518.9], [522.9, 585.3]]  # the reach goes left to the column's "$"


def test_column_layouts_signs_that_do_not_bridge_give_the_same_columns_twice():
    """The second split exists (other spans) but gives the same columns and reach, so strict matching gives the same result."""
    layouts = tv.column_layouts(tv.group_value_words([(100.0, 104.0, "$"), (106.0, 118.0, "59"), (200.0, 204.0, "$"), (206.0, 218.0, "60")]))
    assert layouts == [([[100.0, 118.0], [200.0, 218.0]], [[100.0, 118.0], [200.0, 218.0]]), ([[106.0, 118.0], [206.0, 218.0]], [[100.0, 118.0], [200.0, 218.0]])]


def test_column_layouts_one_layout_without_sign_words():
    """No lone "$" (years, page numbers): only the old split, so relaxed names are never tried unless rows were rebuilt."""
    layouts = tv.column_layouts(tv.group_value_words([(100.0, 118.0, "2011"), (200.0, 218.0, "2019")]))
    assert layouts == [([[100.0, 118.0], [200.0, 218.0]], [[100.0, 118.0], [200.0, 218.0]])]


def test_column_layouts_drops_number_columns_when_a_sign_reaches_over_the_column_on_its_left():
    """3M 2018 p106: the 2017 block is printed 12 points right of the 2018 block; splitting by number parts would tear one real column in two."""
    groups = tv.group_value_words([(196.0, 200.0, "$"), (266.0, 276.0, "53")]) + tv.group_value_words([(218.0, 222.0, "$"), (280.0, 292.0, "197")])
    layouts = tv.column_layouts(groups)
    assert len(layouts) == 1 and layouts[0][0] == [[196.0, 292.0]]


def test_column_layouts_a_split_sign_may_touch_the_number_on_its_left():
    groups = tv.group_value_words([(381.2, 396.1, "(29.8)$"), (410.5, 412.1, "-")]) + tv.group_value_words([(373.4, 375.8, "$"), (381.2, 393.0, "(1.0)")])
    numbers, reach = tv.column_layouts(groups)[-1]
    assert len(numbers) == 2 and reach[1][0] == numbers[0][1]


# --- (b) is_group_heading ---

def header_cells(spec):
    """spec: [(row, col, columns spanned, text)]; boxes unused."""
    return tuple(TableCell(r, c, 1, span, text, 0.0, 0.0, 0.0, 0.0) for r, c, span, text in spec)


def test_is_group_heading_span_starting_on_the_dollar_column_with_leaves_below():
    """Coca-Cola 2022 p98: "Other Postretirement Benefit Plans" starts on the "$" column (3), "2022" / "2021" on the row below (columns 4, 5)."""
    cells = header_cells([(0, 1, 2, "Pension Plans"), (0, 3, 3, "Other Postretirement Benefit Plans"),
                          (1, 0, 1, "Year Ended December 31,"), (1, 1, 1, "2022"), (1, 2, 1, "2021"), (1, 4, 1, "2022"), (1, 5, 1, "2021")])
    leaves = [1, 2, 3, 4, 5]
    assert tr.is_group_heading(cells, 2, 3, leaves) is True
    assert tr.is_group_heading(cells, 2, 1, leaves) is False  # column 1 has its own label "2022"
    assert tr.is_group_heading(cells, 2, 4, leaves) is False


def test_is_group_heading_not_when_the_covered_label_sits_on_the_same_row():
    """Corning 2022 p61: Docling spans "Year ended 2021" over columns 2-3 next to "December 31," on the same row: a torn header, column 2 stays a leaf."""
    cells = header_cells([(0, 1, 4, "Corning Incorporated and Subsidiary Companies"), (1, 1, 1, "2022"), (1, 2, 2, "Year ended 2021"),
                          (1, 3, 1, "December 31,"), (1, 4, 1, "2020")])
    assert tr.is_group_heading(cells, 2, 2, [1, 2, 3, 4]) is False


def test_is_group_heading_needs_a_leaf_with_its_own_label_under_the_span():
    cells = header_cells([(0, 1, 2, "Group"), (1, 0, 1, "x")])
    assert tr.is_group_heading(cells, 2, 1, [1, 2]) is False


# --- strict_names and crowded_columns (the two guards of the second split) ---

def test_strict_names_gives_each_leaf_label_the_column_under_its_centre():
    rows = [["Year Ended December 31,", "2022", "2021"]]
    assert tr.strict_names(rows, [1, 2], [110.0, 210.0], [[100.0, 120.0], [200.0, 220.0]]) == ["2022", "2021"]


def test_strict_names_refuses_labels_that_land_on_one_column():
    rows = [["", "2022", "2021"]]
    assert tr.strict_names(rows, [1, 2], [110.0, 115.0], [[100.0, 120.0], [200.0, 220.0]]) is None


def test_strict_names_refuses_a_label_off_its_column_when_columns_are_spare():
    rows = [["", "2022"]]
    assert tr.strict_names(rows, [1], [160.0], [[100.0, 120.0], [200.0, 220.0]]) is None


def test_crowded_columns_two_values_of_one_row_in_one_column():
    # amounts of 3+ digits: a 1-2 digit number has the shape of a footnote mark and is not counted (is_footnote_ref)
    columns = [[100.0, 130.0], [200.0, 220.0]]
    crowded = [(["Costs incurred"], [(100.0, 110.0, ["136"], 100.0), (115.0, 130.0, ["2,864"], 115.0)])]
    spread = [(["Costs incurred"], [(100.0, 110.0, ["136"], 100.0), (200.0, 210.0, ["2,864"], 200.0)])]
    assert tr.crowded_columns(columns, crowded) is True
    assert tr.crowded_columns(columns, spread) is False


def test_crowded_columns_ignores_words_that_are_not_amounts():
    # AES 2022 p16: "Expected Date of Commercial Operations" holds "1H 2023": two words, one amount, one column
    columns = [[100.0, 130.0], [200.0, 240.0]]
    body = [(["Cement City (1)"], [(100.0, 110.0, ["20"], 100.0), (200.0, 210.0, ["1H"], 200.0), (215.0, 240.0, ["2023"], 215.0)])]
    assert tr.crowded_columns(columns, body) is False
    ranged = [(["Cavalier (1)"], [(100.0, 110.0, ["155"], 100.0), (200.0, 205.0, ["2H"], 200.0), (206.0, 220.0, ["2023-1H"], 206.0),
                                   (225.0, 240.0, ["2024"], 225.0)])]  # "2H 2023-1H 2024": a date range is text
    assert tr.crowded_columns(columns, ranged) is False


@pytest.mark.parametrize("words", [["2025", "-", "2054"], ["0.00", "-", "1.25"], ["4.19%,", "due", "2029"]])
def test_crowded_columns_a_cell_with_text_is_one_value(words):
    # IFRS 22/11: Enbridge "2025 - 2054", Frontera "0.00 - 1.25", George Weston "4.19%, due 2029"
    columns = [[100.0, 130.0], [200.0, 260.0]]
    groups = [(200.0 + 20 * i + 15, [w], 200.0 + 20 * i) for i, w in enumerate(words)]
    body = [(["Notes"], [(100.0, 110.0, ["155"], 100.0)] + [(start, x1, tokens, start) for x1, tokens, start in groups])]
    assert tr.crowded_columns(columns, body) is False


def test_crowded_columns_a_percent_and_an_amount_in_one_column():
    # American Express 2022 p54: "27 % $ 2,864" in one column is two values
    columns = [[100.0, 160.0]]
    body = [(["Card Member loans"], [(100.0, 115.0, ["27", "%"], 100.0), (120.0, 125.0, ["$"], 120.0), (130.0, 160.0, ["2,864"], 130.0)])]
    assert tr.crowded_columns(columns, body) is True


def test_crowded_columns_ignores_a_footnote_mark_next_to_its_value():
    columns = [[100.0, 130.0]]
    body = [(["Revenue"], [(100.0, 110.0, ["336"], 100.0), (112.0, 116.0, ["1"], 112.0)])]
    assert tr.crowded_columns(columns, body) is False


# --- (a) regrid_block on a Coca-Cola 2022 p63 style grid ---

P63_LABEL = (24.6, 300.0)
P63_HEADER = {1: (442.05, 454.85, "2022"), 2: (508.50, 521.29, "2021"), 3: (575.01, 587.80, "2020")}


def p63_fixture(dollar_2021=453.0):
    """Docling: "$ 43,004 $ 38,655" | "$" | "33,014" (TableFormer joined columns at the white space)."""
    texts = [["Year Ended December 31,", "2022", "2021", "2020"],
             ["Net Operating Revenues", "$ 43,004 $ 38,655", "$", "33,014"],
             ["Cost of goods sold", "18,000", "15,357", "13,433"]]
    boxes = {(1, 1): (390.0, 518.9), (1, 2): (522.9, 526.9), (1, 3): (563.3, 585.3), (2, 1): (430.4, 452.4), (2, 2): (496.9, 518.9), (2, 3): (563.3, 585.3)}
    cells = [TableCell(0, 0, 1, 1, texts[0][0], P63_LABEL[0], 0.0, 100.0, 10.0)]
    cells += [TableCell(0, c, 1, 1, text, left, 0.0, right, 10.0) for c, (left, right, text) in P63_HEADER.items()]
    for r in (1, 2):
        cells.append(TableCell(r, 0, 1, 1, texts[r][0], P63_LABEL[0], 20.0 * r, P63_LABEL[1], 20.0 * r + 10.0))
        cells += [TableCell(r, c, 1, 1, texts[r][c], boxes[(r, c)][0], 20.0 * r, boxes[(r, c)][1], 20.0 * r + 10.0) for c in (1, 2, 3)]
    grid = Grid([[(text, c) for c, text in enumerate(row)] for row in texts])
    grid.cells = tuple(cells)
    w = lambda x0, x1, text, r: (x0, 20.0 * r + 1.0, x1, 20.0 * r + 9.0, text, 0, 0, 0)
    words = [w(24.6, 60.0, "Net", 1), w(62.0, 110.0, "Operating", 1), w(112.0, 160.0, "Revenues", 1),
             w(390.0, 394.0, "$", 1), w(430.4, 452.4, "43,004", 1), w(dollar_2021, dollar_2021 + 4.0, "$", 1), w(496.9, 518.9, "38,655", 1),
             w(522.9, 526.9, "$", 1), w(563.3, 585.3, "33,014", 1),
             w(24.6, 50.0, "Cost", 2), w(52.0, 60.0, "of", 2), w(62.0, 90.0, "goods", 2), w(92.0, 110.0, "sold", 2),
             w(430.4, 452.4, "18,000", 2), w(496.9, 518.9, "15,357", 2), w(563.3, 585.3, "13,433", 2)]
    rows = [texts[0], ["---"] * 4, texts[1], texts[2]]
    return rows, grid, words


def test_regrid_block_rebuilds_a_table_whose_signs_bridge_columns():
    rows, grid, words = p63_fixture()
    counts = Counter()
    table = tr.regrid_block(rows, grid, 1, words, counts)
    assert table is not None, dict(counts)
    assert [row_cells(line) for line in table][2:] == [["Net Operating Revenues", "$ 43,004", "$ 38,655", "$ 33,014"],
                                                       ["Cost of goods sold", "18,000", "15,357", "13,433"]]
    assert row_cells(table[0]) == ["Year Ended December 31,", "2022", "2021", "2020"]
    assert counts["regridded"] == 1


def test_regrid_block_old_layout_still_wins_when_it_already_fits():
    """"$" more than 3 points from the previous column's number: the old split already gives three columns, as before the extension."""
    rows, grid, words = p63_fixture(dollar_2021=456.4)
    counts = Counter()
    table = tr.regrid_block(rows, grid, 1, words, counts)
    assert [row_cells(line) for line in table][2] == ["Net Operating Revenues", "$ 43,004", "$ 38,655", "$ 33,014"]


# --- (b) a split that puts two values of one row in one column is never taken (Enablence 2026 p26/p28, 22/11) ---

def enablence_fixture():
    """Docling: one header cell over both date columns ("June 30, 2026 June 30, 2025"), two value columns below."""
    head = "June 30, 2026 June 30, 2025"
    texts = [["", head, head], ["Cash", "4,076", "5,000"], ["Restricted Cash", "4", "4"]]
    cells = [TableCell(0, 1, 1, 2, head, 430.0, 0.0, 519.0, 10.0)]
    boxes = {1: (430.4, 452.4), 2: (496.9, 518.9)}
    for r in (1, 2):
        cells.append(TableCell(r, 0, 1, 1, texts[r][0], 24.6, 20.0 * r, 120.0, 20.0 * r + 10.0))
        cells += [TableCell(r, c, 1, 1, texts[r][c], *boxes[c][:1], 20.0 * r, boxes[c][1], 20.0 * r + 10.0) for c in (1, 2)]
    grid = Grid([[("", 0), (head, 1), (head, 1)], [("Cash", 0), ("4,076", 1), ("5,000", 2)], [("Restricted Cash", 0), ("4", 1), ("4", 2)]])
    grid.cells = tuple(cells)
    w = lambda x0, x1, text, r: (x0, 20.0 * r + 1.0, x1, 20.0 * r + 9.0, text, 0, 0, 0)
    words = [w(24.6, 50.0, "Cash", 1), w(430.4, 452.4, "4,076", 1), w(496.9, 518.9, "5,000", 1),
             w(24.6, 70.0, "Restricted", 2), w(72.0, 90.0, "Cash", 2), w(448.4, 452.4, "4", 2), w(514.9, 518.9, "4", 2)]
    rows = [texts[0], ["---"] * 3, texts[1], texts[2]]
    return rows, grid, words


def test_regrid_block_never_takes_a_split_with_two_values_of_a_row_in_one_column(monkeypatch):
    rows, grid, words = enablence_fixture()
    one_column = [[[420.0, 530.0]], [[420.0, 530.0]]]  # the split Enablence p26 got: both dates in one column; the header label fits it "strictly"
    monkeypatch.setattr(tr, "column_layouts", lambda groups: [one_column])
    counts = Counter()
    assert tr.regrid_block(rows, grid, 1, words, counts) is None
    assert counts["regrid_skip_columns"] == 1
