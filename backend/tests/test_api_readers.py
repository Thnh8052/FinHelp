"""The two paid readers of the parsing pipeline (22/11): Datalab Chandra reads a whole page again (scanned, garbled, missing text, lost table),
the vision model describes one picture. Both are called with httpx (no new dependency); here the HTTP side is a fake transport, nothing leaves the machine.

Measured before (experiments/results/docs/parsing/ocr_scan_2026-11-22.md, vlm_bench_2026-11-22.md): Chandra 97.1 % of 648 true table rows on 40 scanned
IFRS pages once its markup is cleaned (53.2 % raw: "\\$" and <b> stick to the figures), Docling with OCR 92.0 %; gpt-4.1-mini labels next to their values 92 %."""
import json

import fitz
import httpx
import pytest

from app.core.config import settings
from app.modules.ingestion import api_readers
from app.modules.ingestion.api_readers import clean_ocr, describe_picture, read_chandra


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    monkeypatch.setattr(api_readers, "POLL_SECONDS", 0)
    monkeypatch.setattr(api_readers, "RETRY_SECONDS", 0)


def make_pdf(path, n):
    doc = fitz.open()
    for i in range(n):
        doc.new_page().insert_text((72, 72), f"Page {i + 1} revenue 1,000", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


# ---------------------------------------------------------------- cleaning what Chandra writes
def test_escaped_symbols_and_formatting_tags_are_removed():
    assert clean_ocr(r"| Revenue | \$ 1,234 | <b>463</b> | <u>50,100</u> | <i>(59,807)</i> |") == "| Revenue | $ 1,234 | 463 | 50,100 | (59,807) |"
    assert clean_ocr(r"Growth was 5\% and 7\%") == "Growth was 5% and 7%"


def test_a_line_break_inside_a_cell_becomes_a_space_not_nothing():
    assert clean_ocr("| <b>Share capital</b><br><b>£</b> | <b>Profit and loss<br/>account</b> |") == "| Share capital £ | Profit and loss account |"


def test_a_superscript_note_mark_is_kept_apart_from_the_figure():
    """23/11 (F4): a digit mark becomes superscript digits glued to the figure, the same form as the postprocess ("1,016²", not "1,016 [2]")."""
    assert clean_ocr("| Subordinated notes <sup>3</sup> | 1,016<sup>2</sup> |") == "| Subordinated notes³ | 1,016² |"


def test_image_links_are_dropped():
    assert clean_ocr("Signed\n\n![Handwritten signature of a director](003082e5_img.jpg)\n\nDirector") == "Signed\n\nDirector"
    assert clean_ocr("![](2dfa6ac3_img.jpg)\n\n# Consolidated statement") == "# Consolidated statement"


def test_an_html_table_becomes_a_markdown_table():
    html = "<table><tr><th>Item</th><th>2024</th></tr><tr><td>Revenue &amp; other</td><td><b>1,234</b></td></tr></table>"
    assert clean_ocr("Before\n\n" + html + "\n\nAfter") == "Before\n\n| Item | 2024 |\n|---|---|\n| Revenue & other | 1,234 |\n\nAfter"


def test_plain_markdown_is_left_alone():
    text = "# Notes\n\n| Bank loans | 121,582 | 146,421 |\n|---|---|---|\n\nThe loans are secured."
    assert clean_ocr(text) == text


# ---------------------------------------------------------------- Chandra (Datalab), one page per request
def datalab(pages_md, seen, fail_pages=(), empty_pages=()):
    """A fake Datalab: POST /api/v1/convert -> a check URL; the first poll says processing, the second gives the page's Markdown."""
    polls = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.headers["X-Api-Key"] == "test-key"
            body = request.content
            page = int(fitz.open("pdf", body[body.index(b"%PDF"):]).load_page(0).get_text().split()[1])  # each request carries one page
            seen.append(page)
            if page in fail_pages:
                return httpx.Response(500, json={"error": "boom"})
            return httpx.Response(200, json={"success": True, "request_id": f"r{page}", "request_check_url": f"https://www.datalab.to/api/v1/convert/r{page}"})
        page = int(request.url.path.rsplit("r", 1)[1])
        polls[page] = polls.get(page, 0) + 1
        if polls[page] == 1:
            return httpx.Response(200, json={"status": "processing"})
        return httpx.Response(200, json={"status": "complete", "success": True, "markdown": "" if page in empty_pages else pages_md[page]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_each_page_is_sent_alone_and_comes_back_cleaned(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATALAB_API_KEY", "test-key")
    pdf = make_pdf(tmp_path / "a.pdf", 3)
    seen = []
    client = datalab({1: "one", 3: r"| Revenue | \$ <b>1,000</b> |"}, seen)
    out = await read_chandra(pdf, [1, 3], client=client)
    assert sorted(seen) == [1, 3]
    assert out == {1: "one", 3: "| Revenue | $ 1,000 |"}


async def test_a_page_that_keeps_failing_is_left_out_and_the_others_still_come_back(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATALAB_API_KEY", "test-key")
    pdf = make_pdf(tmp_path / "b.pdf", 2)
    seen = []
    out = await read_chandra(pdf, [1, 2], client=datalab({1: "one", 2: "two"}, seen, fail_pages={2}))
    assert out == {1: "one"}
    assert seen.count(2) == api_readers.ATTEMPTS  # tried again, then given up


async def test_an_empty_reply_is_asked_again_then_left_out(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATALAB_API_KEY", "test-key")
    pdf = make_pdf(tmp_path / "c.pdf", 1)
    seen = []
    assert await read_chandra(pdf, [1], client=datalab({1: "x"}, seen, empty_pages={1})) == {}
    assert seen == [1] * api_readers.ATTEMPTS


async def test_no_key_means_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATALAB_API_KEY", None)
    seen = []
    assert await read_chandra(make_pdf(tmp_path / "d.pdf", 1), [1], client=datalab({1: "x"}, seen)) == {}
    assert seen == []


async def test_the_request_turns_picture_captions_off(tmp_path, monkeypatch):
    """24/11 (rule_caption_marker_v2.txt): by default Datalab writes a caption for each picture ("A line chart showing ...", numbers read off the axes,
    up to 73 figures a page the PDF does not print). disable_image_captions turns that off; table rows unchanged (80.4 % vs 80.5 % right on 40 pages)."""
    monkeypatch.setattr(settings, "DATALAB_API_KEY", "test-key")
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            bodies.append(request.content)
            return httpx.Response(200, json={"request_check_url": "https://www.datalab.to/api/v1/convert/r1"})
        return httpx.Response(200, json={"status": "complete", "markdown": "one"})

    out = await read_chandra(make_pdf(tmp_path / "e.pdf", 1), [1], client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert out == {1: "one"}
    assert b'name="disable_image_captions"\r\n\r\ntrue' in bodies[0]
    assert b'name="mode"\r\n\r\n' + settings.DATALAB_MODE.encode() in bodies[0]


def test_chandra_is_the_registered_ocr_reader():
    from app.modules.ingestion.page_quality import READERS

    assert READERS["chandra"] is read_chandra


# ---------------------------------------------------------------- the vision model, one picture per request
def openai(reply, seen, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer test-key"
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "boom"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_a_picture_is_sent_with_the_one_prompt_and_its_description_comes_back(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    seen = []
    out = await describe_picture(b"\x89PNG fake", client=openai("  Bar chart of revenue, 2022 to 2024: 1,000; 1,200; 1,500.  ", seen))
    assert out == "Bar chart of revenue, 2022 to 2024: 1,000; 1,200; 1,500."
    body = seen[0]
    assert body["model"] == settings.FIGURE_MODEL == "gpt-4.1-mini" and body["temperature"] == 0
    text, image = body["messages"][0]["content"]
    assert text == {"type": "text", "text": api_readers.FIGURE_PROMPT} and "NO_DATA" in text["text"] and "~" in text["text"]
    assert image["image_url"]["url"].startswith("data:image/png;base64,")


async def test_a_failing_vision_call_gives_nothing_and_never_raises(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    seen = []
    assert await describe_picture(b"png", client=openai("x", seen, status=500)) is None
    assert len(seen) == api_readers.ATTEMPTS


async def test_no_openai_key_means_no_request(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    seen = []
    assert await describe_picture(b"png", client=openai("x", seen)) is None and seen == []


# ---------------------------------------------------------------- "busy" answers (22/11: Datalab gave 429 to 5 of 28 pages of a scanned report read 4 at a time)
def busy_then(after, busy_times, header):
    """A transport that answers 429 (with Retry-After when `header`) `busy_times` times, then hands the request to `after`."""
    seen = {"busy": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if seen["busy"] < busy_times:
            seen["busy"] += 1
            return httpx.Response(429, headers={"Retry-After": "7"} if header else {}, json={"error": "rate limited"})
        return after(request)

    return handler, seen


async def test_a_busy_answer_is_waited_out_and_is_not_an_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATALAB_API_KEY", "test-key")
    waits = []

    async def sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(api_readers.asyncio, "sleep", sleep)
    pdf = make_pdf(tmp_path / "busy.pdf", 1)
    seen_pages = []
    inner = datalab({1: "one"}, seen_pages)._transport.handler
    handler, seen = busy_then(inner, api_readers.ATTEMPTS + 2, header=True)  # more busy answers than attempts
    out = await read_chandra(pdf, [1], client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert out == {1: "one"} and seen["busy"] == api_readers.ATTEMPTS + 2
    assert waits.count(7.0) == api_readers.ATTEMPTS + 2  # the server's Retry-After


async def test_without_retry_after_the_wait_grows(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    waits = []

    async def sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(api_readers.asyncio, "sleep", sleep)
    seen = []
    inner = openai("Bar chart", seen)._transport.handler
    handler, busy = busy_then(inner, 3, header=False)
    assert await describe_picture(b"png", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) == "Bar chart"
    assert waits == [api_readers.BUSY_SECONDS, 2 * api_readers.BUSY_SECONDS, 4 * api_readers.BUSY_SECONDS]


async def test_busy_answers_are_waited_out_only_so_many_times(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATALAB_API_KEY", "test-key")

    async def sleep(seconds):
        pass

    monkeypatch.setattr(api_readers.asyncio, "sleep", sleep)
    pdf = make_pdf(tmp_path / "busy2.pdf", 1)
    handler, seen = busy_then(lambda r: httpx.Response(500), 10 ** 6, header=True)
    assert await read_chandra(pdf, [1], client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) == {}
    assert seen["busy"] == api_readers.BUSY_WAITS + api_readers.ATTEMPTS  # the waits, then the attempts, all busy


def test_one_page_is_cut_out_without_form_fields(tmp_path):
    """23/11: cutting a page out of the HSBC 2025 annual report (generality set) copied its form-field tree and MuPDF raised "exception stack
    overflow" for every page, so the OCR step of that report always failed (silently). The reader needs the page, not the form fields."""
    import fitz
    from app.modules.ingestion.api_readers import _one_page
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Net revenues 1,037", fontsize=9)
    field = fitz.Widget()
    field.field_name, field.field_type, field.rect = "box", fitz.PDF_WIDGET_TYPE_TEXT, fitz.Rect(72, 100, 200, 120)
    page.add_widget(field)
    doc.save(str(tmp_path / "form.pdf"))
    with fitz.open(stream=_one_page(tmp_path / "form.pdf", 1), filetype="pdf") as one:
        assert "Net revenues 1,037" in one[0].get_text() and list(one[0].widgets()) == []
