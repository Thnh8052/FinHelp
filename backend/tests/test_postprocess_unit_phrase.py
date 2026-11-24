"""A unit phrase printed inside the number area of a table ("(in millions)" on the "OPERATING ACTIVITIES:" line, AES 2021 p134) no longer stops
the row rebuild from the PDF lines (error 13), and the phrase stays with the table in its first header cell (rule_unit_phrase.txt, 24/11).
Before: the phrase was a text group over a number column ("mixed") and Docling held it in a value cell ("values_changed"), so the whole table kept
Docling's shifted rows: "Dividends paid on AES" carried (24), which belongs to "Payments for financed capital expenditures"; the true value is (401)."""
from collections import Counter

import pytest

import app.modules.ingestion.postprocess.table_regrid as tr
from app.modules.ingestion.postprocess.grids import Grid, TableCell, row_cells

COLS = {1: (430.4, 452.4), 2: (496.9, 518.9)}


def aes_fixture():
    """Docling: the unit phrase in a value cell of the first body row; "common stock" pulled into the row above, values shifted up one row."""
    texts = [["OPERATING ACTIVITIES:", "2021", "2020"],
             ["", "(in millions)", ""],
             ["Issuance of preferred stock common stock", "1,014 (401)", "- (381)"],
             ["Dividends paid on AES", "(24)", "(60)"],
             ["Payments for financed capital expenditures", "", ""]]
    cells = [TableCell(0, 0, 1, 1, texts[0][0], 24.6, 0.0, 200.0, 10.0),
             TableCell(0, 1, 1, 1, "2021", 440.0, 0.0, 452.4, 10.0), TableCell(0, 2, 1, 1, "2020", 506.9, 0.0, 518.9, 10.0),
             TableCell(1, 1, 1, 1, "(in millions)", 466.0, 20.0, 505.0, 30.0)]
    for r in (2, 3, 4):
        cells.append(TableCell(r, 0, 1, 1, texts[r][0], 24.6, 20.0 * r, 300.0, 20.0 * r + 10.0))
        cells += [TableCell(r, c, 1, 1, texts[r][c], COLS[c][0], 20.0 * r, COLS[c][1], 20.0 * r + 10.0) for c in (1, 2) if texts[r][c]]
    grid = Grid([[(text, c) for c, text in enumerate(row)] for row in texts])
    grid.cells = tuple(cells)
    w = lambda x0, x1, text, r: (x0, 20.0 * r + 1.0, x1, 20.0 * r + 9.0, text, 0, 0, 0)
    words = [w(24.6, 80.0, "OPERATING", 1), w(82.0, 140.0, "ACTIVITIES:", 1), w(466.0, 474.0, "(in", 1), w(476.0, 505.0, "millions)", 1),
             w(24.6, 70.0, "Issuance", 2), w(72.0, 80.0, "of", 2), w(82.0, 130.0, "preferred", 2), w(132.0, 160.0, "stock", 2),
             w(430.4, 452.4, "1,014", 2), w(514.9, 518.9, "-", 2),
             w(24.6, 70.0, "Dividends", 3), w(72.0, 90.0, "paid", 3), w(92.0, 104.0, "on", 3), w(106.0, 126.0, "AES", 3), w(128.0, 170.0, "common", 3),
             w(172.0, 200.0, "stock", 3), w(430.4, 452.4, "(401)", 3), w(496.9, 518.9, "(381)", 3),
             w(24.6, 70.0, "Payments", 4), w(72.0, 84.0, "for", 4), w(86.0, 130.0, "financed", 4), w(132.0, 170.0, "capital", 4),
             w(172.0, 240.0, "expenditures", 4), w(436.4, 452.4, "(24)", 4), w(502.9, 518.9, "(60)", 4)]
    rows = [texts[0], ["---"] * 3] + texts[1:]
    return rows, grid, words


def test_rebuilds_rows_when_a_unit_phrase_sits_in_the_number_area():
    rows, grid, words = aes_fixture()
    counts = Counter()
    table = tr.regrid_block(rows, grid, 1, words, counts)
    assert table is not None, dict(counts)
    body = [row_cells(line) for line in table][2:]
    assert ["Dividends paid on AES common stock", "(401)", "(381)"] in body
    assert ["Payments for financed capital expenditures", "(24)", "(60)"] in body
    assert ["Issuance of preferred stock", "1,014", "-"] in body
    assert counts["reflowed"] == 1


def test_the_unit_phrase_stays_once_in_the_first_header_cell():
    rows, grid, words = aes_fixture()
    table = tr.regrid_block(rows, grid, 1, words, Counter())
    header = row_cells(table[0])
    assert "(in millions)" in header[0]
    assert "\n".join(table).count("(in millions)") == 1


@pytest.mark.parametrize("phrase", ["(in millions)", "(Dollars in millions, except per share data)", "($ in thousands)", "(In Billions)",
                                    "(Đơn vị: triệu đồng)", "(tỷ đồng)"])
def test_unit_phrases_english_and_vietnamese(phrase):
    assert tr.UNIT_PHRASE.fullmatch(phrase)


@pytest.mark.parametrize("text", ["(1)", "(in 2021)", "(see Note 25)", "(401)", "(2.5 million shares)", "in millions"])
def test_not_unit_phrases(text):
    assert not tr.UNIT_PHRASE.fullmatch(text)


def test_a_unit_phrase_in_the_label_column_is_left_alone():
    w = lambda x0, x1, text: (5.0, x0, x1, text)
    kept, phrases = tr.drop_unit_phrases([w(24.6, 40.0, "(in"), w(42.0, 80.0, "millions)"), w(430.4, 452.4, "1,014")], left=428.9)
    assert phrases == [] and len(kept) == 3
