"""F2 (21/11): a data row that TableFormer flagged as a column header goes back to the table body.

Docling's Markdown writes every header row of a table as ONE line, each column joining its header texts with " - " (checked on 2,670 tables
with 2+ header rows: 2,670 match). When TableFormer flags a data row as header, its values end up inside the column names:
Amazon 2017 p37 "Year Ended December 31, - 2015 - $ 14,557" for the cash at the beginning of the period, Pfizer 2021 p57 "... - 2021 - $ 81,288"
for revenues, Walmart 2019 p78 "6,005 - 5,680" (two data rows joined, no real header on that page). In the 134 study documents: 20 such tables,
19 of them real (the 20th, PG&E 2022 p242, has stock prices as column names). A header row counts as data with the test of error 14
(`table_continued.is_data_row`: a text label, then only values, no year). Tables whose single header row is a data row are left to error 14.
"""
from collections import Counter

from app.modules.ingestion.postprocess.grids import Grid, row_cells, table_blocks
from app.modules.ingestion.postprocess.table_regrid import render_table, unspan_tables


def grid_of(rows):
    """rows: lists of (text, start column) slots, as load_table_grids builds them."""
    return Grid([list(r) for r in rows])


def docling_markdown(grid, headers):
    """The Markdown Docling writes for `grid` with `headers` header rows: one header line (" - " joins, a text equal to the one above written once)."""
    def join(col):
        out = []
        for r in range(headers):
            text = grid[r][col][0]
            if text and (not out or out[-1] != text):
                out.append(text)
        return " - ".join(out)
    header = [join(col) for col in range(len(grid[0]))]
    return "\n".join(render_table([header] + [[t for t, _ in row] for row in grid[headers:]]))


def tables_of(text):
    lines = text.split("\n")
    return [[row_cells(lines[i]) for i in block] for block in table_blocks(lines)]


def plain(cells):
    return [[(t, c) for c, t in enumerate(row)] for row in cells]


AMAZON = [
    [("", 0), ("Year Ended December 31,", 1), ("Year Ended December 31,", 1), ("Year Ended December 31,", 1)],
    [("", 0), ("2015", 1), ("2016", 2), ("2017", 3)],
    [("CASH AND CASH EQUIVALENTS, BEGINNING OF PERIOD", 0), ("$ 14,557", 1), ("$ 15,890", 2), ("$ 19,334", 3)],
    [("Net income", 0), ("596", 1), ("2,371", 2), ("3,033", 3)],
]


def test_data_row_inside_a_two_row_header_goes_back_to_the_body():
    grid = grid_of(AMAZON)
    text = docling_markdown(grid, 3)
    assert "Year Ended December 31, - 2015 - $ 14,557" in text  # what Docling writes today
    counts = Counter()
    table = tables_of(unspan_tables(text, [grid], counts))[0]
    assert table[0] == ["", "Year Ended December 31, - 2015", "Year Ended December 31, - 2016", "Year Ended December 31, - 2017"]
    assert table[2] == ["CASH AND CASH EQUIVALENTS, BEGINNING OF PERIOD", "$ 14,557", "$ 15,890", "$ 19,334"]
    assert table[3] == ["Net income", "596", "2,371", "3,033"]
    assert counts["header_rows_demoted"] == 1


WALMART = plain([
    ["Depreciation and amortization", "6,005", "2,601", "698"],
    ["Capital expenditures", "5,680", "2,607", "626"],
    ["Total assets", "105,811", "122,821", "14,520"],
])


def test_header_made_only_of_data_rows_becomes_rows_again():
    """Walmart 2019 p78 (the table goes on from the page before): the first data row is written as the Markdown header line, as Docling writes a table without
    a header, so that error 14 can put the previous page's header above it or a blank header."""
    grid = grid_of(WALMART)
    text = docling_markdown(grid, 2)
    assert "6,005 - 5,680" in text
    counts = Counter()
    table = tables_of(unspan_tables(text, [grid], counts))[0]
    assert table[0] == ["Depreciation and amortization", "6,005", "2,601", "698"]
    assert table[2] == ["Capital expenditures", "5,680", "2,607", "626"]
    assert table[3] == ["Total assets", "105,811", "122,821", "14,520"]
    assert not any(" - " in cell for row in table for cell in row)
    assert counts["header_rows_demoted"] == 2


def test_header_of_years_is_left_alone():
    grid = grid_of(plain([["", "Year Ended", "Year Ended"], ["(in millions)", "2022", "2021"], ["Revenue", "100", "90"]]))
    text = docling_markdown(grid, 2)
    counts = Counter()
    assert unspan_tables(text, [grid], counts) == text
    assert counts["header_rows_demoted"] == 0


def test_header_row_that_is_not_data_by_error_14_is_left_alone():
    # "+0.25%" is not a number for the backend (3M 2018 p40); "737" as the first cell is not a text label (Boeing aircraft models)
    for rows in (plain([["", "Discount Rate", "Discount Rate"], ["(Millions)", "-0.25%", "+0.25%"], ["Cost", "12", "(11)"]]),
                 plain([["", "Program", "Program"], ["737", "747", "767"], ["Deliveries", "529", "6"]])):
        grid = grid_of(rows)
        text = docling_markdown(grid, 2)
        counts = Counter()
        assert unspan_tables(text, [grid], counts) == text
        assert counts["header_rows_demoted"] == 0


def test_single_data_header_row_is_left_to_error_14():
    grid = grid_of(plain([["Depreciation and amortization", "6,005", "2,601"], ["Capital expenditures", "5,680", "2,607"]]))
    text = docling_markdown(grid, 1)
    counts = Counter()
    assert unspan_tables(text, [grid], counts) == text
    assert counts["header_rows_demoted"] == 0


def test_true_header_row_below_a_data_row_keeps_the_header_as_it_is():
    grid = grid_of(plain([["Net sales", "1,234", "1,100"], ["", "2022", "2021"], ["Cost", "800", "700"]]))
    text = docling_markdown(grid, 2)
    counts = Counter()
    assert unspan_tables(text, [grid], counts) == text
    assert counts["header_rows_demoted"] == 0


def test_a_later_table_on_the_page_is_still_matched_after_lines_were_added():
    first, second = grid_of(AMAZON), grid_of(plain([["", "2022", "2021"], ["Revenue", "100", "90"]]))
    text = docling_markdown(first, 3) + "\n\nSome text.\n\n" + docling_markdown(second, 1)
    counts = Counter()
    out = unspan_tables(text, [first, second], counts)
    tables = tables_of(out)
    assert tables[0][2][0] == "CASH AND CASH EQUIVALENTS, BEGINNING OF PERIOD"
    assert tables[1] == tables_of(docling_markdown(second, 1))[0]
    assert counts["matched"] == 2
