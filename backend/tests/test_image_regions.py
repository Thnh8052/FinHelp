"""Image regions no step reads today (experiments TRIED NP-38, NP-39, NP-40): a table or chart pasted into a page that has a text layer (Enablence p42, a
bad-debt line of 166) is a raster image Docling gives no picture box for, so neither Docling's text nor the picture reader (figures.py) has it. The page text
stays as it is and each such region is read by the vision model with the measured prompt v2 (api_readers.REGION_PROMPT), the reply appended to the page.
Measured on 30 new images: 99.0 % of the printed numbers stated, 0 of 269 invented, 9 of 10 photos and signatures skipped, 0 of 20 titles made up.
Behind IMAGE_REGION_READER_ENABLED (on since 25/11; the tests run with it off, conftest)."""
import json

import fitz
import httpx
import pytest

from app.core.config import settings
from app.modules.ingestion import api_readers, figures
from app.modules.ingestion.api_readers import REGION_PROMPT, describe_region
from app.modules.ingestion.figures import MARKER, read_regions, read_regions_if_enabled, regions_to_read, unpaired_values

BIG = fitz.Rect(72, 100, 472, 400)  # 400 x 300 points, 25 % of a Letter page


def raster(page, rect, gray=120):
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, int(rect.width), int(rect.height)), False)
    pix.clear_with(gray)
    page.insert_image(rect, pixmap=pix)


def make_pdf(path):
    """p1 a table image under a text title (to read); p2 the same but Docling gave it a picture box (the figure reader's); p3 a small logo; p4 an image with
    its own words on top; p5 an image with a hidden text layer stacked on its bottom edge (the AMCOR 409A plan pages: 144 to 604 words, all on one line just
    under the box); p6 an image and no text layer at all (a scan: the OCR fallback's); p7 like p1 but Chandra read it; p8 two images."""
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 80), "Notes to the financial statements", fontsize=11)
    raster(p1, BIG)
    p2 = doc.new_page()
    p2.insert_text((72, 80), "Revenue by segment", fontsize=11)
    raster(p2, BIG)
    p3 = doc.new_page()
    p3.insert_text((72, 80), "Annual report", fontsize=11)
    raster(p3, fitz.Rect(72, 40, 112, 70))
    p4 = doc.new_page()
    raster(p4, BIG)
    for i in range(12):
        p4.insert_text((90, 120 + 14 * i), f"word{i} printed on the image", fontsize=9)
    p5 = doc.new_page()
    p5.insert_text((72, 80), "Plan text", fontsize=11)
    raster(p5, BIG)
    p5.insert_textbox(fitz.Rect(72, 400.3, 540, 404), " ".join(f"w{i}" for i in range(60)), fontsize=2)
    p6 = doc.new_page()
    raster(p6, BIG)
    p7 = doc.new_page()
    p7.insert_text((72, 80), "Notes to the financial statements", fontsize=11)
    raster(p7, BIG)
    p8 = doc.new_page()
    p8.insert_text((72, 40), "Two tables", fontsize=11)
    raster(p8, fitz.Rect(72, 60, 472, 260), gray=60)
    raster(p8, fitz.Rect(72, 400, 472, 600), gray=90)
    doc.save(str(path))
    doc.close()
    return path


def pages():
    return [{"page_number": 1, "text": "## Notes to the financial statements"},
            {"page_number": 2, "text": f"## Revenue by segment\n\n{MARKER}", "pictures": [[72.0, 100.0, 472.0, 400.0]]},
            {"page_number": 3, "text": "Annual report"},
            {"page_number": 4, "text": "words"},
            {"page_number": 5, "text": "Plan text"},
            {"page_number": 6, "text": "scan"},
            {"page_number": 7, "text": "## Notes to the financial statements", "ocr": True},
            {"page_number": 8, "text": "Two tables"}]


def test_only_a_raster_image_nothing_else_reads_is_chosen(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    out = regions_to_read(pdf, pages())
    # not p2 (a picture box the figure reader reads), p3 (small), p4 (its own words), p5 (hidden text layer), p6 (no text layer), p7 (Chandra read it)
    assert [(n, k) for n, k, _ in out] == [(1, 0), (8, 0), (8, 1)]
    assert out[0][2] == pytest.approx([72.0, 100.0, 472.0, 400.0], abs=0.5)


def test_a_picture_box_the_figure_reader_does_not_choose_does_not_hide_the_region(tmp_path):
    """Docling's box on p2 covers less than the raster does, so figures.pictures_to_read skips it (a vector-like box: raster cover under 60 %): the image is still
    nobody's, and is chosen here."""
    pdf = make_pdf(tmp_path / "b.pdf")
    small_box = pages()
    small_box[1]["pictures"] = [[72.0, 100.0, 120.0, 130.0]]  # 48 x 30 points: under 3 % of the page, never read by figures.py
    assert (2, 0) in [(n, k) for n, k, _ in regions_to_read(pdf, small_box)]


def test_the_prompt_is_the_measured_v2():
    p = REGION_PROMPT
    assert p.startswith("You read one picture cut from a company report")
    assert "reply exactly: NO_DATA" in p
    assert "If any number is printed on the picture, never reply NO_DATA" in p  # v1 sent small data crops to NO_DATA (3 of 20)
    assert "only if it is printed on the picture; never add one that is not printed" in p  # v1 made up a title for a revenue chart
    assert "Never estimate a value from an axis" in p and "Never compute a new number" in p


async def test_a_reply_is_appended_to_its_page_with_its_lines_kept(tmp_path):
    pdf = make_pdf(tmp_path / "c.pdf")
    replies = iter(["June 30, 2026 | June 30, 2025\nTrade | 3,761 | 1,747\nOther | 635 | 389", "NO_DATA: company logo", None])

    async def describe(png):
        return next(replies)

    out, report = await read_regions(pdf, pages(), describe)
    assert out[0]["text"] == ("## Notes to the financial statements\n\n[Figure read from the image, page 1]\n"
                              "June 30, 2026 | June 30, 2025\nTrade | 3,761 | 1,747\nOther | 635 | 389")
    assert out[7]["text"] == "Two tables" and out[7]["figure_failed"] is True  # the second image got no answer: the page is listed for the user
    assert not any(p.get("figure_failed") for p in out[:7])
    assert [p["text"] for p in out[1:7]] == [p["text"] for p in pages()[1:7]]
    assert report == {"chosen": 3, "described": 1, "no_data": 1, "failed": 1}


async def test_values_listed_apart_from_their_labels_are_not_trusted(tmp_path):
    """NP-40: for 1 of 4 waterfall charts the reader wrote the values first and the labels after, so no number can be tied to its label. Stored as text it could
    be quoted against the wrong label: the page is listed as unread instead."""
    pdf = make_pdf(tmp_path / "d.pdf")
    apart = "(in millions)\n\n$1,902\n\n($260)\n\n$1,073\n\n$2,715\n\n2021\n\nChange in Adjusted Net Income (1)\n\n2022"

    async def describe(png):
        return apart

    out, report = await read_regions(pdf, pages()[:1], describe)
    assert out[0]["text"] == "## Notes to the financial statements" and out[0]["figure_failed"] is True
    assert report == {"chosen": 1, "described": 0, "no_data": 0, "failed": 1}


def test_unpaired_values_tells_a_labelled_reply_from_a_loose_one():
    labelled = ["2021 | ($3,051)\nCapex | ($2,435)\nNet Short-Term Investments | ($540)\n2022 | ($5,836)",
                "$797\n2021\n$3,012 Non-Recourse Debt\n$690 Non-Recourse Revolvers\n$569 Sales to NCI\n$3,758\n2022",
                "Year ending June 30 | $\n2027 665\n2028 680\n2029 675\n2030 695\nTotal 3,491",
                "- | 4,666 | - | 4,666\n287 | - | 9,286 | 5,154\n293 | 231 | 49 | 79\nBalance 5,661 | 6,932 | 4,016 | 6,295",
                "2022 0\n2023 1,7\n2024 11,5\n2025 37,0\n6,8x", "", "NO_DATA: logo"]
    assert not any(unpaired_values(t) for t in labelled)
    assert unpaired_values("$1,902\n\n($260)\n\n$1,073\n\n$2,715")  # four single values in a row, blank lines between
    assert unpaired_values("(in millions)\n$1,902\n($260)\n$1,073\n2021\nChange in Adjusted Net Income (1)")
    assert not unpaired_values("$1,902\n($260)\nChange in working capital")  # only two in a row


async def test_the_switch_and_the_report(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path / "e.pdf")
    calls = []

    async def describe(png):
        calls.append(png)
        return "Total | 100 | 90"

    monkeypatch.setattr(figures, "describe_region", describe)
    monkeypatch.setattr(settings, "IMAGE_REGION_READER_ENABLED", False)
    before = pages()
    assert await read_regions_if_enabled(pdf, before) is before and calls == []
    monkeypatch.setattr(settings, "IMAGE_REGION_READER_ENABLED", True)
    info = {}
    out = await read_regions_if_enabled(pdf, pages(), info)
    assert out[0]["text"].endswith("[Figure read from the image, page 1]\nTotal | 100 | 90")
    assert info == {"regions_chosen": 3, "regions_described": 3} and len(calls) == 3

    async def broken(png):
        raise RuntimeError("down")

    monkeypatch.setattr(figures, "describe_region", broken)
    info = {}
    out = await read_regions_if_enabled(pdf, pages(), info)
    assert out[0]["figure_failed"] is True and out[0]["text"] == pages()[0]["text"]
    assert info == {"regions_chosen": 3, "regions_described": 0, "regions_failed": 3}


async def test_a_document_with_no_such_region_costs_no_call(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path / "f.pdf")
    monkeypatch.setattr(settings, "IMAGE_REGION_READER_ENABLED", True)

    async def describe(png):
        raise AssertionError("no call expected")

    monkeypatch.setattr(figures, "describe_region", describe)
    plain = [p for p in pages() if p["page_number"] in (2, 3, 4, 5, 6, 7)]
    info = {}
    assert await read_regions_if_enabled(pdf, plain, info) == plain and info == {}


def test_the_pipeline_runs_the_step_and_the_default_is_on():
    from app.core.config import Settings
    from app.modules.ingestion import pipeline

    assert pipeline.read_regions_if_enabled is figures.read_regions_if_enabled
    assert Settings.model_fields["IMAGE_REGION_READER_ENABLED"].default is True  # owner 25/11: turned on after rule_b2_check.txt passed (experiments TRIED NP-46)
    assert settings.IMAGE_REGION_READER_ENABLED is False  # tests run with it off (conftest)


# ---------------------------------------------------------------- the request
def openai(reply, seen, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer test-key"
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "boom"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_a_region_is_sent_with_the_v2_prompt_and_room_for_a_whole_table(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    seen = []
    out = await describe_region(b"\x89PNG fake", client=openai("  Trade | 3,761 | 1,747\nOther | 635 | 389  ", seen))
    assert out == "Trade | 3,761 | 1,747\nOther | 635 | 389"  # the rows stay on their own lines
    body = seen[0]
    assert body["model"] == settings.FIGURE_MODEL and body["temperature"] == 0 and body["max_tokens"] >= 4000  # a full page of text came to 700 tokens, a table 400
    text, image = body["messages"][0]["content"]
    assert text == {"type": "text", "text": REGION_PROMPT}
    assert image["image_url"]["url"].startswith("data:image/png;base64,")


async def test_a_failing_region_call_gives_nothing_and_no_key_means_no_request(monkeypatch):
    monkeypatch.setattr(api_readers, "RETRY_SECONDS", 0)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    seen = []
    assert await describe_region(b"png", client=openai("x", seen, status=500)) is None and len(seen) == api_readers.ATTEMPTS
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    seen.clear()
    assert await describe_region(b"png", client=openai("x", seen)) is None and seen == []
