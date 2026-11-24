"""Pages to check against the original, found at upload (owner 23/11: report a parse problem instead of staying silent).
After the OCR step and the figure step, the pages that still fail page_quality's checks are listed: a scanned page still without text is "unread",
a page whose figures or tables are still lost or garbled is "tables" and its chunks carry the flag "table_check" (the citation says to check the page).
A page the OCR step read well, a blank page and a clean page are not listed. The PDFs are made here with PyMuPDF.
"""
import fitz

from app.modules.ingestion.parse_check import check_pages

LINES = [f"Revenue line {i}  {1000 + i * 37:,}  {2000 + i * 91:,}" for i in range(30)]
TABLE = "\n".join(f"| Revenue line {i} | {1000 + i * 37:,} | {2000 + i * 91:,} |" for i in range(30))


def _write_lines(page):
    y = 72
    for line in LINES:
        page.insert_text((72, y), line, fontsize=9)
        y += 14


def make_pdf(path, kinds):
    doc = fitz.open()
    for kind in kinds:
        page = doc.new_page()
        if kind == "text":
            _write_lines(page)
        elif kind == "scan":
            source = fitz.open()
            _write_lines(source.new_page())
            page.insert_image(page.rect, pixmap=source[0].get_pixmap(dpi=72))
    doc.save(str(path))
    return path


def page(n, text, **extra):
    return {"page_number": n, "text": text, "tables": [], **extra}


def test_a_scanned_page_left_without_text_is_unread(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", ["text", "scan"])
    pages, issues = check_pages(pdf, [page(1, TABLE), page(2, "<!-- image -->")])
    assert issues == {"tables": [], "unread": [2]}
    assert not any(p.get("table_check") for p in pages)


def test_a_scan_the_ocr_step_read_is_not_listed(tmp_path):
    pdf = make_pdf(tmp_path / "b.pdf", ["text", "scan"])
    assert check_pages(pdf, [page(1, TABLE), page(2, TABLE, ocr=True)])[1] == {"tables": [], "unread": []}


def test_a_page_whose_figures_are_still_lost_is_listed_and_flagged(tmp_path):
    pdf = make_pdf(tmp_path / "c.pdf", ["text", "text"])
    pages, issues = check_pages(pdf, [page(1, TABLE), page(2, "Revenue line")])
    assert issues == {"tables": [2], "unread": []}
    assert [p.get("table_check", False) for p in pages] == [False, True]


def test_a_page_whose_picture_could_not_be_read_is_listed(tmp_path):
    """Owner 24/11: a picture the reader was asked to read and could not (figures.py "figure_failed") is listed under "figures"; the key is only
    there when some page has one."""
    pdf = make_pdf(tmp_path / "g.pdf", ["text", "text"])
    pages, issues = check_pages(pdf, [page(1, TABLE), page(2, TABLE, figure_failed=True)])
    assert issues == {"tables": [], "unread": [], "figures": [2]}
    assert not any(p.get("table_check") for p in pages)


CHART_BOX = [60.0, 520.0, 540.0, 640.0]  # top-left origin, as the worker sends picture boxes


def _chart_pdf(path, chart_lines):
    doc = fitz.open()
    pg = doc.new_page()
    _write_lines(pg)
    for i, line in enumerate(chart_lines):
        pg.insert_text((80, 550 + 16 * i), line, fontsize=9)
    doc.save(str(path))
    return path


def test_a_vector_chart_whose_printed_figures_the_parse_lost_is_listed(tmp_path):
    """Owner 24/11 (rule_layout_checks.txt part V, 26 of 30 such pictures really charts or figures): Docling drops the text inside a picture box, so a
    vector chart's printed values are not in the excerpt. A picture with >= 5 text-layer words, < 50 % of them in the page's text and >= 2 numbers new
    to it is listed with the unread pictures and marked "chart_unread" (its chunks get the "picture unread" flag)."""
    chart = ["Revenue by year", "2021 2022 2023 2024 2025", "35,657 44,010 52,618 62,849 70,113"]
    pdf = _chart_pdf(tmp_path / "v.pdf", chart)
    pages, issues = check_pages(pdf, [page(1, TABLE + "\n\n<!-- image -->", pictures=[CHART_BOX])])
    assert issues == {"tables": [], "unread": [], "figures": [1]}
    assert pages[0].get("chart_unread") is True and not pages[0].get("table_check")


def test_a_chart_whose_figures_are_in_the_text_or_with_few_words_is_not_listed(tmp_path):
    chart = ["Revenue by year", "2021 2022 2023 2024 2025", "35,657 44,010 52,618 62,849 70,113"]
    pdf = _chart_pdf(tmp_path / "w.pdf", chart)
    kept = TABLE + "\n\nRevenue by year 2021 2022 2023 2024 2025 35,657 44,010 52,618 62,849 70,113"
    assert check_pages(pdf, [page(1, kept, pictures=[CHART_BOX])])[1] == {"tables": [], "unread": []}
    logo = _chart_pdf(tmp_path / "x.pdf", ["Logo 2024"])
    assert check_pages(logo, [page(1, TABLE + "\n\n<!-- image -->", pictures=[CHART_BOX])])[1] == {"tables": [], "unread": []}


def test_a_scan_read_with_chart_text_is_listed_for_the_user(tmp_path):
    """Owner 24/11: a scan whose re-read holds a chart description the reader wrote (page_quality "ocr_unsure") is listed under "tables" and flagged."""
    pdf = make_pdf(tmp_path / "u.pdf", ["text", "scan"])
    pages, issues = check_pages(pdf, [page(1, TABLE), page(2, TABLE, ocr=True, ocr_unsure=True)])
    assert issues == {"tables": [2], "unread": []}
    assert [p.get("table_check", False) for p in pages] == [False, True]


def test_a_blank_page_is_not_unread(tmp_path):
    pdf = make_pdf(tmp_path / "d.pdf", ["text", "blank"])
    assert check_pages(pdf, [page(1, TABLE), page(2, "")])[1] == {"tables": [], "unread": []}


def test_a_table_the_table_check_finds_misread_is_listed(tmp_path):
    """ingestion/table_check.py: printed rows not held by the Markdown AND two amounts in one value cell."""
    doc = fitz.open()
    pg = doc.new_page()
    rows = [(f"Item {name}", f"{1000 + i * 7:,}", f"{2000 + i * 9:,}") for i, name in enumerate("ABCDEF")]  # "100 200" would read as thousands with a space
    for i, (label, a, b) in enumerate(rows):
        pg.insert_text((72, 100 + 14 * i), label, fontsize=9)
        for text, right in ((a, 380), (b, 480)):
            pg.insert_text((right - fitz.get_text_length(text, fontsize=9), 100 + 14 * i), text, fontsize=9)
    doc.save(str(tmp_path / "e.pdf"))
    fused = "\n".join(["| | 2025 |", "|---|---|"] + [f"| {label} | {a} {b} |" for label, a, b in rows])
    right = "\n".join(["| | 2025 | 2024 |", "|---|---|---|"] + [f"| {label} | {a} | {b} |" for label, a, b in rows])
    assert check_pages(tmp_path / "e.pdf", [page(1, fused)])[1] == {"tables": [1], "unread": []}
    assert check_pages(tmp_path / "e.pdf", [page(1, right)])[1] == {"tables": [], "unread": []}


def _table_pdf(path):
    doc = fitz.open()
    pg = doc.new_page()
    rows = [(f"Item {name}", f"{1000 + i * 7:,}", f"{2000 + i * 9:,}") for i, name in enumerate("ABCDEF")]
    for i, (label, a, b) in enumerate(rows):
        pg.insert_text((72, 100 + 14 * i), label, fontsize=9)
        for text, right in ((a, 380), (b, 480)):
            pg.insert_text((right - fitz.get_text_length(text, fontsize=9), 100 + 14 * i), text, fontsize=9)
    doc.save(str(path))
    return path, rows


def test_a_table_with_a_defect_and_a_wrong_row_is_listed_but_wrong_rows_alone_are_not(tmp_path):
    """Plan 24/11 step 4 (rule_user_list_defect.txt): pages whose Markdown tables show a defect and that have >= 1 wrong printed row were really misread
    on 36 of 40 pages, above the user list's bar (34): they are listed. Wrong rows without a defect ("rows", 40 % real) are only read again, not listed."""
    pdf, rows = _table_pdf(tmp_path / "d.pdf")
    head = ["| | 2025 | 2024 |", "|---|---|---|"]
    one_fused = "\n".join(head + [f"| {l} | {a} | {b} |" for l, a, b in rows[:5]] + [f"| {rows[5][0]} | {rows[5][1]} {rows[5][2]} | |"])
    split = "\n".join(head + [f"| {rows[0][0]} | {rows[0][1]} | |", f"| | {rows[0][2]} | |", f"| {rows[1][0]} | {rows[1][1]} | |", f"| | {rows[1][2]} | |"]
                      + [f"| {l} | {a} | {b} |" for l, a, b in rows[2:]])
    pages, issues = check_pages(pdf, [page(1, one_fused)])
    assert issues == {"tables": [1], "unread": []} and pages[0]["table_check"] is True
    assert check_pages(pdf, [page(1, split)])[1] == {"tables": [], "unread": []}


def test_a_page_the_parser_did_not_return_is_unread(tmp_path):
    """D4a (owner 23/11): a page of the PDF missing from the parse would be lost without a word (docling-parse <= 7.16 dropped pages when threaded);
    it is listed with the pages that have no text. Measured 0 such pages in 23,176 (TRIED NP-18): a safety net."""
    pdf = make_pdf(tmp_path / "g.pdf", ["text", "text", "text"])
    pages, issues = check_pages(pdf, [page(1, TABLE), page(3, TABLE)])
    assert issues == {"tables": [], "unread": [2]}
    assert [p["page_number"] for p in pages] == [1, 3]


def test_a_missing_page_and_an_unread_scan_are_listed_once_in_order(tmp_path):
    pdf = make_pdf(tmp_path / "h.pdf", ["scan", "text", "text"])
    assert check_pages(pdf, [page(1, "<!-- image -->"), page(2, TABLE)])[1] == {"tables": [], "unread": [1, 3]}


def test_the_check_never_fails_an_upload(tmp_path):
    """The check is an extra, like the OCR step: an unreadable PDF leaves the pages as they are and lists nothing."""
    import asyncio
    from app.modules.ingestion.parse_check import check_safely
    pages = [page(1, "Revenue")]
    info = {}
    assert asyncio.run(check_safely(tmp_path / "missing.pdf", pages, info)) == (pages, {})
    assert asyncio.run(check_safely(make_pdf(tmp_path / "f.pdf", ["text"]), [page(1, TABLE)], info))[1] == {"tables": [], "unread": []}
    assert "check" in info
