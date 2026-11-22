"""F3 (21/11): a table the PDF prints but the parse lost (written as one-value paragraphs, or the whole table in one cell) is rebuilt from the PDF words.
Repair only: it runs on pages the two detectors flag, never on a table the parse already has.

Measured before (experiments/results/docs/parsing/audit_rebuild_v2_2026-11-21.md, ocr_vs_rebuild_2026-11-21.md): 24 flagged pages of the 134 study
documents (JPMorgan 10-Q/10-K, Pfizer, J&J, AES, Boeing, MGM, Salesforce), 244 true table rows: the parse had 13 exact, the rebuild 234 (OCR 201).
On 400 tables the parse reads right the rebuild has 95.6 % of rows but only 88 % of the column counts, hence repair only.
"""
from collections import Counter

import app.modules.ingestion.postprocess.table_rebuild as tb
from app.modules.ingestion.postprocess.grids import Grid, row_cells, table_blocks

CHAR = 5.0


def word(x0, y, text, right=False):
    """A PDF word (x0, y0, x1, y1, text, block, line, word); right=True: x0 is the right edge (figures are right-aligned)."""
    w = CHAR * len(text)
    a = x0 - w if right else x0
    return (a, y, a + w, y + 8.0, text, 0, 0, 0)


def label(y, text, x=50.0):
    out, cur = [], x
    for t in text.split():
        out.append(word(cur, y, t))
        cur += CHAR * len(t) + 2.0
    return out


def row(y, name, *values, cols=(260.0, 330.0, 400.0)):
    """A table row: a label, then each value right-aligned on its column edge ("$" printed at the left of the column)."""
    out = label(y, name)
    for v, edge in zip(values, cols):
        tokens = v.split()
        main = next((i for i, t in enumerate(tokens) if any(c.isdigit() for c in t)), 0)
        for i, t in enumerate(tokens):
            if t == "$" and i < main:
                out.append(word(edge - 45.0, y, "$"))
        t = tokens[main]  # the last DIGIT sits on the column edge; a closing ")" hangs to the right, as printed
        tail = len(t) - 1 - max(i for i, c in enumerate(t) if c.isdigit()) if any(c.isdigit() for c in t) else 0
        out.append(word(edge + CHAR * tail, y, t, right=True))
        x = edge + CHAR * tail + 2.0
        for t in tokens[main + 1:]:  # marks and "%" printed after the figure
            out.append(word(x, y, t))
            x += CHAR * len(t) + 2.0
    return out


def tables_of(text):
    lines = text.split("\n")
    return [[row_cells(lines[i]) for i in b] for b in table_blocks(lines)]


# ---- rebuilding a region ----

def test_rows_labels_and_columns_come_back():
    words = (label(100, "2023", 235) + label(100, "2022", 305) + label(100, "2021", 375)
             + row(115, "Total net revenue", "$ 81,737", "$ 63,220", "$ 59,000")
             + row(130, "Total noninterest expense", "6,254", "5,980", "5,500"))
    tables = tb.rebuild(words, (40, 95, 420, 140))
    assert len(tables) == 1
    t = [row_cells(l) for l in tables[0]]
    assert t[0] == ["", "2023", "2022", "2021"]
    assert t[2] == ["Total net revenue", "$ 81,737", "$ 63,220", "$ 59,000"]
    assert t[3] == ["Total noninterest expense", "6,254", "5,980", "5,500"]


def test_percent_printed_on_some_rows_stays_in_its_column():
    # JPMorgan prints "%" only on the first and total rows: the column is placed by the last digit, not the end of the word
    words = (row(100, "Residential real estate", "(0.03) %", "(0.12) %", "1,000")
             + row(115, "Auto and other", "0.89", "0.56", "1,100") + row(130, "Total consumer", "0.91 %", "0.53 %", "2,100"))
    t = [row_cells(l) for l in tb.rebuild(words, (40, 95, 420, 140))[0]]
    assert [len(r) for r in t[2:]] == [4, 4, 4]
    assert t[3] == ["Auto and other", "0.89", "0.56", "1,100"]


def test_letter_mark_stays_with_its_value_but_a_negative_amount_is_a_value():
    words = (row(100, "Credit Portfolio VaR", "17 (b)", "6", "31") + row(115, "Diversification benefit", "(373)", "(43)", "(15)")
             + row(130, "Total VaR", "$ 54", "$ 41", "$ 71"))
    t = [row_cells(l) for l in tb.rebuild(words, (40, 95, 420, 140))[0]]
    assert t[2] == ["Credit Portfolio VaR", "17 (b)", "6", "31"]
    assert t[3] == ["Diversification benefit", "(373)", "(43)", "(15)"]


def test_a_dash_goes_to_the_column_it_is_printed_in():
    words = (row(100, "Deposits", "3,360", "165", "671") + row(115, "Short-term borrowings", "1,674", "338", "5,140")
             + label(130, "Other") + [word(235, 130, "-"), word(300, 130, "-"), word(400, 130, "12", right=True)])
    t = [row_cells(l) for l in tb.rebuild(words, (40, 95, 420, 140))[0]]
    assert t[4] == ["Other", "-", "-", "12"]


def test_first_phrase_of_a_line_is_the_label_even_if_it_has_no_lowercase():
    words = row(100, "US", "1,000", "986", "3,897") + row(115, "Intl", "1,383", "1,527", "5,793") + row(130, "WW", "2,384", "2,513", "9,690")
    t = [row_cells(l) for l in tb.rebuild(words, (40, 95, 420, 140))[0]]
    assert [r[0] for r in t[2:]] == ["US", "Intl", "WW"]


def test_wrapped_label_is_joined():
    words = (row(100, "Revenue", "100", "90", "80") + label(115, "Total exposure - net of liquid securities and")
             + row(130, "other cash collateral", "1,193", "1,000", "900"))
    t = [row_cells(l) for l in tb.rebuild(words, (40, 95, 420, 140))[0]]
    assert t[3] == ["Total exposure - net of liquid securities and other cash collateral", "1,193", "1,000", "900"]


def test_a_row_with_dashes_and_a_figure_is_not_a_header():
    words = (row(100, "Deposits", "3,360", "165", "671") + row(115, "Short-term borrowings", "1,674", "338", "5,140")
             + label(130, "Other") + [word(235, 130, "-"), word(300, 130, "-"), word(400, 130, "12", right=True)]
             + row(145, "Total", "5,034", "503", "5,823"))
    assert len(tb.rebuild(words, (40, 95, 420, 155))) == 1


def test_stacked_tables_with_other_columns_are_two_tables():
    first = row(100, "Revenue", "100", "90", "80") + row(115, "Cost", "60", "50", "40")
    head = label(130, "Six months", 230) + label(130, "Twelve months", 330)
    second = row(145, "Revenue", "200", "180", cols=(300.0, 380.0)) + row(160, "Cost", "120", "100", cols=(300.0, 380.0))
    assert len(tb.rebuild(first + head + second, (40, 95, 420, 170))) == 2


def test_a_header_line_over_the_same_columns_does_not_split_the_table():
    first = row(100, "Revenue", "100", "90", "80") + row(115, "Cost", "60", "50", "40")
    head = label(130, "Three months", 230) + label(130, "Six months", 330)
    second = row(145, "Revenue", "200", "180", "160") + row(160, "Cost", "120", "100", "90")
    assert len(tb.rebuild(first + head + second, (40, 95, 420, 170))) == 1


# ---- repairing a page ----

LOST_WORDS = (label(80, "The table below shows revenue by segment and the cost of each.")
              + label(100, "2023", 235) + label(100, "2022", 305) + label(100, "2021", 375)
              + row(115, "Total net revenue", "$ 81,737", "$ 63,220", "$ 59,000")
              + row(130, "Total noninterest expense", "6,254", "5,980", "5,500")
              + row(145, "Pre-provision profit", "75,483", "57,240", "53,500")
              + label(175, "(a) Prior-period amounts have been revised to conform with the current presentation of the Firm."))
LOST_MD = "\n\n".join(["The table below shows revenue by segment and the cost of each.", "2023", "2022", "2021", "Total net revenue", "$",
                       "81,737", "$", "63,220", "$ 59,000", "Total noninterest expense", "6,254", "5,980", "5,500", "Pre-provision profit",
                       "75,483", "57,240", "53,500", "(a) Prior-period amounts have been revised to conform with the current presentation of the Firm."])


def test_table_written_as_paragraphs_is_rebuilt_in_place():
    counts = Counter()
    out = tb.rebuild_lost_tables(LOST_MD, [], LOST_WORDS, 1, counts)
    tables = tables_of(out)
    assert len(tables) == 1 and tables[0][2] == ["Total net revenue", "$ 81,737", "$ 63,220", "$ 59,000"]
    assert out.startswith("The table below shows revenue")
    assert out.rstrip().endswith("current presentation of the Firm.")
    assert "\n\n81,737\n\n" not in out
    assert counts["rebuilt_lost"] == 1


def test_two_lost_tables_on_one_page_are_both_rebuilt():
    # JPMorgan 2023Q2 p23: several tables of one page are lost; each is rebuilt at its own place
    second_words = (label(260, "Assets under management grew in every region, as the next table shows for the year.")
                    + row(280, "Americas", "5,111", "4,900", "4,700") + row(295, "Europe", "2,222", "2,100", "2,000")
                    + row(310, "Asia", "1,333", "1,200", "1,100"))
    second_md = "\n\n".join(["Assets under management grew in every region, as the next table shows for the year.", "Americas", "5,111", "4,900",
                             "4,700", "Europe", "2,222", "2,100", "2,000", "Asia", "1,333", "1,200", "1,100"])
    counts = Counter()
    out = tb.rebuild_lost_tables(LOST_MD + "\n\n" + second_md, [], LOST_WORDS + second_words, 1, counts)
    tables = tables_of(out)
    assert len(tables) == 2 and tables[1][2] == ["Americas", "5,111", "4,900", "4,700"]
    assert counts["rebuilt_lost"] == 2


def test_cells_cut_by_a_heading_still_find_their_place():
    md = LOST_MD.replace("Total noninterest expense", "###### Total noninterest expense")
    counts = Counter()
    out = tb.rebuild_lost_tables(md, [], LOST_WORDS, 1, counts)
    assert counts["rebuilt_lost"] == 1
    assert tables_of(out)[0][2] == ["Total net revenue", "$ 81,737", "$ 63,220", "$ 59,000"]
    assert "\n\n75,483\n\n" not in out


def test_a_figure_shared_with_the_parsed_table_next_door_does_not_hide_the_lost_one():
    # JPM 2022Q2 p142: the lost table repeats a small figure ("5,500") of the table Docling did read
    md = "| | 2023 |\n|---|---|\n| Other | 5,500 |\n\n" + LOST_MD
    counts = Counter()
    out = tb.rebuild_lost_tables(md, [], LOST_WORDS, 1, counts)
    assert counts["rebuilt_lost"] == 1 and len(tables_of(out)) == 2


def test_page_whose_table_is_already_parsed_is_left_alone():
    md = ("The table below shows revenue by segment and the cost of each.\n\n"
          "| | 2023 | 2022 | 2021 |\n|---|---|---|---|\n| Total net revenue | $ 81,737 | $ 63,220 | $ 59,000 |\n"
          "| Total noninterest expense | 6,254 | 5,980 | 5,500 |\n| Pre-provision profit | 75,483 | 57,240 | 53,500 |")
    counts = Counter()
    assert tb.rebuild_lost_tables(md, [], LOST_WORDS, 1, counts) == md
    assert counts["rebuilt_lost"] == 0


def test_two_lost_rows_are_not_enough():
    words = row(115, "Total net revenue", "$ 81,737", "$ 63,220", "$ 59,000") + row(130, "Total noninterest expense", "6,254", "5,980", "5,500")
    md = "\n\n".join(["Total net revenue", "$ 81,737", "$ 63,220", "$ 59,000", "Total noninterest expense", "6,254", "5,980", "5,500"])
    assert tb.rebuild_lost_tables(md, [], words, 1, Counter()) == md


def test_prose_with_figures_is_left_alone():
    words = (label(100, "Revenue was $81,737 million in 2023 compared with $63,220 million in 2022 and $59,000 million in 2021, while")
             + label(115, "expense was 6,254 million, 5,980 million and 5,500 million and the profit grew to 75,483 million, 57,240")
             + label(130, "million and 53,500 million in the three years, as the table on the next page shows in more detail."))
    md = "Revenue was $81,737 million in 2023 compared with $63,220 million in 2022 and $59,000 million in 2021, while expense was ..."
    assert tb.rebuild_lost_tables(md, [], words, 1, Counter()) == md


def test_table_collapsed_into_one_cell_is_rebuilt():
    words = (label(100, "2023", 235) + label(100, "2022", 305) + label(100, "2021", 375)
             + row(115, "Fixed income", "$ 60", "$ 48", "$ 79") + row(130, "Foreign exchange", "8", "4", "13")
             + row(145, "Equities", "11", "7", "15") + row(160, "Commodities", "14", "12", "17") + row(175, "Total VaR", "$ 54", "$ 41", "$ 71"))
    cell = "2023 2022 2021 Fixed income $ 60 $ 48 $ 79 8 4 13 11 7 15 14 12 17 Total VaR $ 54 $ 41 $ 71"
    md = f"###### Total VaR\n\n| {cell} |\n|---|\n\nThe table below shows VaR."
    grid = Grid([[(cell, 0)]])
    grid.extent = {7: (40.0, 95.0, 420.0, 185.0)}
    counts = Counter()
    out = tb.rebuild_lost_tables(md, [grid], words, 7, counts)
    tables = tables_of(out)
    assert len(tables) == 1 and tables[0][2] == ["Fixed income", "$ 60", "$ 48", "$ 79"]
    assert out.startswith("###### Total VaR") and out.rstrip().endswith("The table below shows VaR.")
    assert counts["rebuilt_collapsed"] == 1
