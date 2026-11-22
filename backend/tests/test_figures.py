"""Pictures read by the vision model (22/11): Docling writes "<!-- image -->" for each picture and the worker sends each picture's box, in the same order.
A picture is read when its figures can only be in the pixels: it covers >= 3 % of the page, an embedded raster image covers >= 60 % of it, and fewer than
5 words of the PDF text layer are inside (the "image" class of the VLM bench: 213 of 19,702 pages). A vector chart (its numbers are text already), a small
logo and a page Chandra read again are not sent. The description replaces the picture's marker; "NO_DATA" (a photo, a logo) leaves the marker.
Checked before: the backend postprocess keeps every marker (607 of 607 pages with pictures, SEC 134), raw Docling 130 of 130."""
import fitz

from app.core.config import settings
from app.modules.ingestion import figures
from app.modules.ingestion.chunker import FinancialChunkerService
from app.modules.ingestion.figures import MARKER, pictures_to_read, read_figures, read_figures_if_enabled

M = MARKER


def raster(page, rect, gray=120):
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, int(rect.width), int(rect.height)), False)
    pix.clear_with(gray)
    page.insert_image(rect, pixmap=pix)


def make_pdf(path):
    """p1: a raster chart (200 x 150 pt) and a wider one below; p2: a vector chart (numbers as text, no raster); p3: a small logo; p4: a raster chart."""
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 60), "Revenue by segment", fontsize=11)
    raster(p1, fitz.Rect(72, 80, 272, 230))
    raster(p1, fitz.Rect(72, 300, 472, 500), gray=60)
    p2 = doc.new_page()
    for i, v in enumerate(["1,000", "1,200", "1,500", "1,800", "2,100", "2,400"]):
        p2.insert_text((90 + 60 * i, 200), v, fontsize=9)
    p2.draw_rect(fitz.Rect(80, 100, 480, 260))
    p3 = doc.new_page()
    raster(p3, fitz.Rect(72, 40, 112, 70))
    p4 = doc.new_page()
    raster(p4, fitz.Rect(72, 80, 372, 330))
    doc.save(str(path))
    doc.close()
    return path


CHART1, CHART2 = [72.0, 80.0, 272.0, 230.0], [72.0, 300.0, 472.0, 500.0]


def pages():
    return [{"page_number": 1, "text": f"## Revenue by segment\n\n{M}\n\nSome text.\n\n{M}", "pictures": [CHART1, CHART2]},
            {"page_number": 2, "text": f"{M}\n\nGrowth text.", "pictures": [[80.0, 100.0, 480.0, 260.0]]},
            {"page_number": 3, "text": f"{M}\n\nAnnual Report", "pictures": [[72.0, 40.0, 112.0, 70.0]]},
            {"page_number": 4, "text": "| Revenue | 1,000 |", "pictures": [[72.0, 80.0, 372.0, 330.0]], "ocr": True},
            {"page_number": 5, "text": "No pictures here."}]


def test_only_pictures_whose_figures_are_in_the_pixels_are_chosen(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    assert pictures_to_read(pdf, pages()) == [(1, 0, CHART1), (1, 1, CHART2)]  # not the vector chart, the logo, nor the page Chandra read


async def test_each_description_takes_the_place_of_its_own_marker(tmp_path):
    pdf = make_pdf(tmp_path / "b.pdf")

    async def describe(png):  # told apart by the crop's width: the second chart is twice as wide
        return "Bar chart: wide" if fitz.Pixmap(png).width > 600 else "Bar chart: narrow"

    out, report = await read_figures(pdf, pages(), describe)
    assert out[0]["text"] == ("## Revenue by segment\n\n[Figure read from the image, page 1] Bar chart: narrow\n\nSome text.\n\n"
                              "[Figure read from the image, page 1] Bar chart: wide")
    assert [p["text"] for p in out[1:]] == [p["text"] for p in pages()[1:]]
    assert report == {"chosen": 2, "described": 2, "no_data": 0, "failed": 0}


async def test_no_data_and_a_failed_call_leave_the_marker(tmp_path):
    pdf = make_pdf(tmp_path / "c.pdf")
    replies = iter(["NO_DATA: company logo", None])

    async def describe(png):
        return next(replies)

    out, report = await read_figures(pdf, pages(), describe)
    assert out[0]["text"] == pages()[0]["text"]
    assert report == {"chosen": 2, "described": 0, "no_data": 1, "failed": 1}


async def test_when_the_markers_do_not_match_the_pictures_the_description_goes_at_the_end(tmp_path):
    pdf = make_pdf(tmp_path / "d.pdf")
    one = [{"page_number": 1, "text": "## Revenue by segment\n\nSome text.", "pictures": [CHART1]}]

    async def describe(png):
        return "Pie chart: 40 % / 60 %"

    out, _ = await read_figures(pdf, one, describe)
    assert out[0]["text"] == "## Revenue by segment\n\nSome text.\n\n[Figure read from the image, page 1] Pie chart: 40 % / 60 %"


async def test_a_page_with_nothing_to_read_costs_no_call(tmp_path):
    pdf = make_pdf(tmp_path / "e.pdf")

    async def describe(png):
        raise AssertionError("no call expected")

    plain = [p for p in pages() if p["page_number"] in (2, 3, 4, 5)]
    out, report = await read_figures(pdf, plain, describe)
    assert out == plain and report["chosen"] == 0


async def test_the_switch(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path / "f.pdf")
    calls = []

    async def describe(png):
        calls.append(png)
        return "Line chart"

    monkeypatch.setattr(figures, "describe_picture", describe)
    monkeypatch.setattr(settings, "FIGURE_READER_ENABLED", False)
    before = pages()
    assert await read_figures_if_enabled(pdf, before) is before and calls == []
    monkeypatch.setattr(settings, "FIGURE_READER_ENABLED", True)
    info = {}
    out = await read_figures_if_enabled(pdf, pages(), info)
    assert out[0]["text"].count("[Figure read from the image, page 1] Line chart") == 2
    assert info == {"figures_chosen": 2, "figures_described": 2}


def test_chunks_holding_a_picture_description_carry_the_figure_flag():
    pages_in = [{"page_number": 1, "text": "Revenue was 100 million."},
                {"page_number": 2, "text": "[Figure read from the image, page 2] Bar chart of revenue: ~240 in 2023.", "ocr": True}]
    chunks = FinancialChunkerService.chunk_document("nb", "d", pages_in, count_tokens=lambda t: len(t.split()))
    assert [(c.page, c.flags) for c in chunks] == [(1, []), (2, ["ocr", "figure"])]


def test_the_docling_worker_sends_each_pictures_box_in_marker_order():
    """postprocess/pictures.page_pictures runs where Docling runs (laptop worker and the Kaggle notebook): boxes in PDF points, top-left origin."""
    from docling_core.types.doc import BoundingBox, CoordOrigin, DoclingDocument, ProvenanceItem, Size

    from app.modules.ingestion.postprocess.pictures import page_pictures

    doc = DoclingDocument(name="t")
    doc.add_page(page_no=1, size=Size(width=600, height=800))
    doc.add_page(page_no=2, size=Size(width=600, height=800))
    for page_no, (l, t, r, b) in [(1, (72, 720, 272, 570)), (1, (72, 500, 472, 300)), (2, (10, 790, 50, 760))]:
        doc.add_picture(prov=ProvenanceItem(page_no=page_no, bbox=BoundingBox(l=l, t=t, r=r, b=b, coord_origin=CoordOrigin.BOTTOMLEFT), charspan=(0, 0)))
    assert page_pictures(doc) == {1: [[72.0, 80.0, 272.0, 230.0], [72.0, 300.0, 472.0, 500.0]], 2: [[10.0, 10.0, 50.0, 40.0]]}
    assert doc.export_to_markdown(page_no=1).count(MARKER) == 2
