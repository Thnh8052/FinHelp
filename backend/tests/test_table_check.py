"""Table check at upload (owner 23/11; rule experiments/scripts/parsing_metric/rule_page_flag_v2.txt, measured 39 of 40 flagged pages really misread).
A page is flagged only when two signals agree: the printed table rows of the PDF (a label, then values in columns) are not held exactly by the page's
Markdown rows, AND the Markdown tables show a defect of their own (two amounts in one value cell, a full-size mark after an amount, rows that lost
their labels). The PDFs are made here with PyMuPDF: a label at x = 72, values right-aligned in two columns.
"""
import fitz

from app.modules.ingestion.table_check import misread_tables

ROWS = [("Net revenues", "1,037", "2,091"), ("Cost of sales", "(412)", "(733)"), ("Gross profit", "625", "1,358"),
        ("Operating expenses", "(301)", "(512)"), ("Operating income", "324", "846"), ("Net income", "251", "702")]


def make_pdf(path, rows=ROWS, label=True):
    doc = fitz.open()
    page = doc.new_page()
    y = 100
    for name, a, b in rows:
        if label:
            page.insert_text((72, y), name, fontsize=9)
        for text, right in ((a, 380), (b, 480)):
            page.insert_text((right - fitz.get_text_length(text, fontsize=9), y), text, fontsize=9)
        y += 14
    doc.save(str(path))
    return path


def markdown(rows):
    return "\n".join(["| | 2025 | 2024 |", "|---|---|---|"] + [f"| {' | '.join(r)} |" for r in rows])


def flagged(pdf, text):
    with fitz.open(str(pdf)) as doc:
        return misread_tables(doc[0], text)


def test_a_table_read_right_is_not_flagged(tmp_path):
    assert flagged(make_pdf(tmp_path / "a.pdf"), markdown(ROWS)) is False


def test_rows_fused_into_one_cell_are_flagged(tmp_path):
    """Docling cut the 2024 column: each value cell holds both years ("1,037 2,091"), as on Nike 2021 p34 or Boeing 2018 p30."""
    fused = [(name, f"{a} {b}", "") for name, a, b in ROWS]
    assert flagged(make_pdf(tmp_path / "b.pdf"), markdown(fused)) is True


def test_wrong_rows_without_a_defect_of_the_table_are_not_flagged(tmp_path):
    """Values one row off (or a page the PDF prints in a way the row check reads wrongly): the Markdown cells look sound, so no flag (precision first)."""
    shifted = [(ROWS[i][0], ROWS[i + 1][1], ROWS[i + 1][2]) for i in range(len(ROWS) - 1)]
    assert flagged(make_pdf(tmp_path / "c.pdf"), markdown(shifted)) is False


def test_printed_lines_without_a_label_are_not_judged(tmp_path):
    """Lines that start with a number (chart labels, phone numbers, a row number) are not table rows the check can trust."""
    fused = [(name, f"{a} {b}", "") for name, a, b in ROWS]
    assert flagged(make_pdf(tmp_path / "d.pdf", label=False), markdown(fused)) is False


def test_a_dash_minus_in_the_pdf_reads_as_a_minus(tmp_path):
    """The IMF prints "–3.5" (an en dash); Docling writes "-3.5". The row is read right."""
    rows = [(name, f"–{a.strip('()')}", b) for name, a, b in ROWS]
    md = [(name, a.replace("–", "-"), b) for name, a, b in rows]
    assert flagged(make_pdf(tmp_path / "e.pdf", rows), markdown(md)) is False


# ---- plan B7 (25/11, experiments rule_b7_rows.txt): general sources of false "wrong rows" on the PDF side, measured on the U1 audit pages
from app.modules.ingestion.table_check import wrong_rows  # noqa: E402


def _page_with_lines(path, lines, rotate=0):
    """`lines`: [(text at x = 72, [values right-aligned at 380, 480, ...])]; `rotate`: the page is drawn turned, as a landscape table in a portrait PDF."""
    doc = fitz.open()
    page = doc.new_page()
    y = 100
    for name, values in lines:
        if rotate:
            page.insert_text((y, 700 - 72), name, fontsize=9, rotate=90)
            for k, text in enumerate(values):
                page.insert_text((y, 700 - 380 + 100 * k * -1 + fitz.get_text_length(text, fontsize=9) - 0), text, fontsize=9, rotate=90)
        else:
            page.insert_text((72, y), name, fontsize=9)
            for k, text in enumerate(values):
                right = 380 + 100 * k
                page.insert_text((right - fitz.get_text_length(text, fontsize=9), y), text, fontsize=9)
        y += 14
    if rotate:
        page.set_rotation(rotate)
    doc.save(str(path))
    return path


def _wrong(pdf, text):
    with fitz.open(str(pdf)) as doc:
        return wrong_rows(doc[0], text)[1]


def test_a_date_spread_into_the_value_columns_is_not_a_table_row(tmp_path):
    """x04 / x05 / x18 of the U1 audit: justified prose puts "21," and "2024," of "On November 21, 2024, CMN paid ..." where values stand; a date
    is not two values."""
    pdf = _page_with_lines(tmp_path / "f.pdf", [("On November", ["21,", "2024,"])] + [(n, [a, b]) for n, a, b in ROWS])
    text = markdown(ROWS) + "\n\nOn November 21, 2024, the company paid the claim in full."
    assert _wrong(pdf, text) == 0


def test_a_header_of_dates_is_not_a_table_row(tmp_path):
    """JPMorgan 2022 p237 / BMC p18: "(in millions)   31, 2022   31, 2021" is the date header of the columns, read as "December 31, 2022"."""
    pdf = _page_with_lines(tmp_path / "g.pdf", [("(in millions)", ["31, 2022", "31, 2021"])] + [(n, [a, b]) for n, a, b in ROWS])
    text = "\n".join(["| (in millions) | December 31, 2022 | December 31, 2021 |", "|---|---|---|"] + [f"| {n} | {a} | {b} |" for n, a, b in ROWS])
    assert _wrong(pdf, text) == 0


def test_a_header_of_year_ranges_is_not_a_table_row(tmp_path):
    """General Mills 2019 p33: "In Millions  Total  2020  2021 -22  2023 -24  Thereafter" is the header of a maturity table."""
    pdf = _page_with_lines(tmp_path / "h.pdf", [("In Millions Total", ["2020", "2021 -22", "2023 -24"])] + [(n, [a, b]) for n, a, b in ROWS])
    text = "\n".join(["| In Millions | Total | 2020 | 2021-22 | 2023-24 |", "|---|---|---|---|---|"]) + "\n\n" + markdown(ROWS)
    assert _wrong(pdf, text) == 0
