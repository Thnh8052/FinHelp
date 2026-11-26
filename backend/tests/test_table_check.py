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


def test_a_small_percent_change_reads_the_same_with_or_without_a_space(tmp_path):
    """JPM 10-Q 2022 p21 (TRIED NP-63): the PDF prints a change as "(1) %", and the check reads "(1)" as a footnote mark of the amount before it; the OCR reader
    wrote "(1)%". The same printed value must read the same on both sides, either way round, or a right re-read is refused (3 right rows counted wrong)."""
    spaced = _page_with_lines(tmp_path / "s.pdf", [("Total net revenue", ["12,760", "(1) %", "11,947"])])  # values right-aligned at x = 380, 480, 580
    glued = _page_with_lines(tmp_path / "g.pdf", [("Total net revenue", ["12,760", "(1)%", "11,947"])])
    md = lambda change: "\n".join(["| | 2022 | Change | 2021 |", "|---|---|---|---|", f"| Total net revenue | 12,760 | {change} | 11,947 |"])
    for pdf in (spaced, glued):
        for change in ("(1) %", "(1)%"):
            assert _wrong(pdf, md(change)) == 0, (pdf.name, change)
    assert _wrong(spaced, md("(2)%")) == 1  # a different value is still wrong


def test_safe_format_normalization_and_space_thousands(tmp_path):
    """Rotated pages, spaced thousands, trailing '$', HTML '&gt;', and markdown footnote links [(2)] read identically across parsers."""
    from app.modules.ingestion.table_check import _norm_space_numbers, wrong_rows_pair
    assert _norm_space_numbers("1\u202f037.50") == "1037.50"
    doc = fitz.open()
    page = doc.new_page()
    y = 100
    page.insert_text((72, y), "Adjusted balance", fontsize=9)
    page.insert_text((260, y), "1", fontsize=9)
    page.insert_text((267.5, y), "037", fontsize=9)
    page.insert_text((340, y), "$(4.9)$", fontsize=9)
    page.insert_text((420, y), ">(100)", fontsize=9)
    page.insert_text((500, y), "2020 (2)", fontsize=9)
    pdf = tmp_path / "fmt.pdf"
    doc.save(str(pdf))

    md_clean = "\n".join([
        "| Item | A | B | C | Year |",
        "|---|---|---|---|---|",
        "| Adjusted balance | 1\u202f037 | $(4.9) | &gt;(100) | 2020 [(2)] |",
    ])
    with fitz.open(str(pdf)) as opened:
        assert wrong_rows(opened[0], md_clean) == (1, 0)
        assert wrong_rows_pair(opened[0], md_clean, md_clean) == (0, 0)


def test_rotated_page_reads_tables_in_visual_coordinates(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    # Draw unrotated coordinates that become horizontal left-to-right after set_rotation(90)
    page.insert_text((100, 700), "Total equity", fontsize=9, rotate=90)
    page.insert_text((100, 400), "1,250", fontsize=9, rotate=90)
    page.insert_text((100, 300), "2,500", fontsize=9, rotate=90)
    page.set_rotation(90)
    pdf = tmp_path / "rot.pdf"
    doc.save(str(pdf))
    md = "| Item | 2025 | 2024 |\n|---|---|---|\n| Total equity | 1,250 | 2,500 |"
    with fitz.open(str(pdf)) as opened:
        assert wrong_rows(opened[0], md) == (1, 0)


def test_wrong_rows_pair_does_not_penalize_clean_negatives_or_footnote_columns(tmp_path):
    """Nike p84 / HSBC p353 pattern: standalone negative '(32)' across columns and separated Footnotes columns when PDF _drop_marks stripped the mark."""
    from app.modules.ingestion.table_check import wrong_rows_pair
    doc = fitz.open()
    page = doc.new_page()
    # Row 1 (Nike pattern): wide column gap negative numbers '(32)' and '(55)'
    page.insert_text((72, 100), "Net change", fontsize=9)
    page.insert_text((260, 100), "95", fontsize=9)
    page.insert_text((340, 100), "$", fontsize=9)
    page.insert_text((352, 100), "(55)", fontsize=9)
    page.insert_text((440, 100), "(32)", fontsize=9)
    # Row 2 (HSBC pattern): superscript small digit footnote '68' right next to '(48.00)' so _drop_marks strips '68' from PDF
    page.insert_text((72, 130), "Diversified Fund", fontsize=9)
    page.insert_text((260, 130), "100.00", fontsize=9)
    page.insert_text((340, 130), "(48.00)", fontsize=9)
    page.insert_text((373, 128), "68", fontsize=6)
    pdf = tmp_path / "pair.pdf"
    doc.save(str(pdf))

    docling_buggy = "\n".join([
        "| Item | A | B | C |",
        "|---|---|---|---|",
        "| Net change | 95 | $ (55 ) | (32 ) |",
        "| Diversified Fund | 100.00 | (48.00)⁶⁸ | |",
    ])
    chandra_clean = "\n".join([
        "| Item | A | B | C | Footnotes |",
        "|---|---|---|---|---|",
        "| Net change | 95 | $ (55) | (32) | |",
        "| Diversified Fund | 100.00 | (48.00) | | 68 |",
    ])
    with fitz.open(str(pdf)) as opened:
        # Clean negative '(55)' / '(32)' + separated '68' column must not lose to Docling's spaced '(55 )' / glued '⁶⁸'.
        assert wrong_rows_pair(opened[0], docling_buggy, chandra_clean) == (0, 0)


def test_spaced_thousands_respects_column_order_and_gap(tmp_path):
    """Out-of-order PDF stream columns (HSBC p73) and narrow >=3.4pt adjacent columns (HSBC p354) must never merge into 6-digit numbers."""
    doc = fitz.open()
    page = doc.new_page()
    # Row 1: right column '339' emitted before left column '290' on same y line
    page.insert_text((72, 100), "Right before left", fontsize=9)
    page.insert_text((340, 100), "339", fontsize=9)
    page.insert_text((260, 100), "290", fontsize=9)
    # Row 2: tight adjacent columns '151' (x1 ~ 275) and '130' at a 3.4pt gap (> VALUE_GAP_TOLERANCE = 3.0)
    page.insert_text((72, 120), "Tight column pair", fontsize=9)
    page.insert_text((260, 120), "151", fontsize=9)
    page.insert_text((260 + page.get_text("words")[-1][2] - page.get_text("words")[-1][0] + 3.4, 120), "130", fontsize=9)
    pdf = tmp_path / "cols.pdf"
    doc.save(str(pdf))
    md = "\n".join([
        "| Item | A | B |",
        "|---|---|---|",
        "| Right before left | 290 | 339 |",
        "| Tight column pair | 151 | 130 |",
    ])
    with fitz.open(str(pdf)) as opened:
        assert wrong_rows(opened[0], md) == (2, 0)
