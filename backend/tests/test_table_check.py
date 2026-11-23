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
