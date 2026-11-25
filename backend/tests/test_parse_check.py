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


CHART_BOX = [60.0, 520.0, 540.0, 640.0]  # top-left origin, as the worker sends picture boxes; 12 % of a letter page


def _image_pdf(path, rect, words_over=0):
    """A text page with a raster image at `rect` (a table or chart pasted as a picture) and `words_over` text-layer words printed on it."""
    doc = fitz.open()
    pg = doc.new_page()
    _write_lines(pg)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 40), False)
    pix.clear_with(200)
    pg.insert_image(fitz.Rect(*rect), pixmap=pix)
    for i in range(words_over):
        pg.insert_text((rect[0] + 10, rect[1] + 14 + 12 * (i // 4)), f"word{i}", fontsize=8)
    doc.save(str(path))
    return path


def test_a_page_with_a_picture_is_listed_as_not_processed(tmp_path):
    """Owner 25/11 (plan "parsing gọn lại"): no model reads pictures any more; a page with a picture of >= 3 % of the page (a Docling picture box) is
    listed under "figures" (the document card: pictures not processed) and marked "picture_unread" (every chunk of the page gets the flag)."""
    pdf = make_pdf(tmp_path / "v.pdf", ["text", "text"])
    pages, issues = check_pages(pdf, [page(1, TABLE), page(2, TABLE + "\n\n<!-- image -->", pictures=[CHART_BOX])])
    assert issues == {"tables": [], "unread": [], "figures": [2]}
    assert pages[1].get("picture_unread") is True and not pages[1].get("table_check") and not pages[0].get("picture_unread")


def test_a_small_picture_is_not_listed(tmp_path):
    """A logo or an icon (under 3 % of the page) holds no figures worth telling the user about."""
    pdf = make_pdf(tmp_path / "w.pdf", ["text"])
    assert check_pages(pdf, [page(1, TABLE + "\n\n<!-- image -->", pictures=[[72.0, 100.0, 172.0, 150.0]])])[1] == {"tables": [], "unread": []}


def test_an_image_pasted_on_a_text_page_without_a_picture_box_is_listed(tmp_path):
    """A raster image Docling gave no picture box for (a table pasted as a picture, Enablence p42) is not processed either: listed the same way."""
    pdf = _image_pdf(tmp_path / "r.pdf", (72, 500, 400, 700))
    pages, issues = check_pages(pdf, [page(1, TABLE)])
    assert issues == {"tables": [], "unread": [], "figures": [1]} and pages[0].get("picture_unread") is True


def test_an_image_the_region_reader_read_is_not_listed(tmp_path):
    """Condition 2 (owner 25/11): a pasted image the region reader answered for (image_regions.py "regions_read") was processed, so it is not listed; one it
    could not read stays listed. A page Chandra read again is not listed for its pasted images either: the reader read the whole page image."""
    pdf = _image_pdf(tmp_path / "q.pdf", (72, 500, 400, 700))
    with fitz.open(str(pdf)) as doc:
        drawn = [round(v, 1) for v in doc[0].get_image_info()[0]["bbox"]]  # the image keeps its proportions inside the rectangle it was put in
    assert check_pages(pdf, [page(1, TABLE, regions_read=[drawn])])[1] == {"tables": [], "unread": []}
    assert check_pages(pdf, [page(1, TABLE, regions_read=[[72.0, 100.0, 400.0, 300.0]])])[1]["figures"] == [1]  # another region was read, not this one
    assert check_pages(pdf, [page(1, TABLE, ocr=True)])[1] == {"tables": [], "unread": []}


def test_a_docling_picture_is_listed_even_on_a_page_whose_pasted_image_was_read(tmp_path):
    pdf = _image_pdf(tmp_path / "z.pdf", (72, 500, 400, 700))
    got = check_pages(pdf, [page(1, TABLE, regions_read=[[72.0, 500.0, 400.0, 700.0]], pictures=[[420.0, 500.0, 560.0, 700.0]])])[1]
    assert got == {"tables": [], "unread": [], "figures": [1]}


def test_an_image_under_printed_words_is_not_listed(tmp_path):
    """An image with >= 5 text-layer words on it is a background or carries a hidden text layer (AMCOR): its text is read already."""
    pdf = _image_pdf(tmp_path / "h.pdf", (72, 500, 400, 700), words_over=8)
    assert check_pages(pdf, [page(1, TABLE)])[1] == {"tables": [], "unread": []}


def test_a_scanned_page_is_not_listed_as_a_picture(tmp_path):
    """A scan is one big picture with no text layer: the OCR step reads it, so it is never on the picture list (unread when still without text)."""
    pdf = make_pdf(tmp_path / "s.pdf", ["text", "scan"])
    full = [0.0, 0.0, 612.0, 792.0]
    assert check_pages(pdf, [page(1, TABLE), page(2, TABLE, ocr=True, pictures=[full])])[1] == {"tables": [], "unread": []}
    assert check_pages(pdf, [page(1, TABLE), page(2, "<!-- image -->", pictures=[full])])[1] == {"tables": [], "unread": [2]}


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
