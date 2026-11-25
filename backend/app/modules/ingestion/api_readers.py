"""The two paid readers of the parsing pipeline (22/11), called with httpx (already a dependency; the Datalab and OpenAI client libraries are not needed).

  read_chandra      Datalab Chandra reads whole pages again: one single-page PDF per request (the measured setup), the Markdown cleaned by `clean_ocr`.
                    Registered in page_quality.READERS["chandra"]. Measured: 97.1 % of 648 true table rows on 40 scanned IFRS pages once cleaned, 53.2 % raw
                    ("\\$" and <b> stick to the figures), Docling with OCR 92.0 % (experiments/results/docs/parsing/ocr_scan_2026-11-22.md).
  describe_region   the vision model (settings.FIGURE_MODEL) copies one image pasted on a page with a text layer (image_regions.py) with REGION_PROMPT v2
                    (TRIED NP-40: 99.0 % of the printed numbers, 0 of 269 invented). The picture describer (describe_picture) was removed 25/11 (owner).

Both are extras: no key means no request, a call that fails ATTEMPTS times gives nothing, and the caller keeps Docling's text. Keys are never logged.
"""
import asyncio
import base64
import html
import re
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.modules.ingestion.postprocess.table_regrid import DIGIT_MARK
from app.modules.ingestion.postprocess.tokens import superscript

DATALAB_URL = "https://www.datalab.to/api/v1/convert"
ATTEMPTS = 3
POLL_SECONDS = 1.0
MAX_POLLS = 300  # 5 minutes for one page
RETRY_SECONDS = 2.0
# Ý nghĩa: câu trả lời "bận" (429, 503) được chờ rồi hỏi lại, không tính vào ATTEMPTS: chờ đúng Retry-After của máy chủ, không có thì BUSY_SECONDS x 2^(k-1).
# Giữ vì: 22/11 đọc 28 trang scan Walmart 2019, 4 trang một lúc, Datalab trả 429 cho 5 trang ở cả 3 lần thử (chờ 2, 4, 6 giây): 5 trang mất chữ.
BUSY_SECONDS = 5.0
BUSY_WAITS = 8
BUSY_CODES = (429, 503)

# The prompt for a region of a page that is only an image (a table pasted as a picture, image_regions.regions_to_read): it must copy the whole table, so the reply keeps
# its lines. Measured as v2 on 30 images (experiments TRIED NP-40): 99.0 % of the printed numbers stated, 0 of 269 invented, 9 of 10 photos and signatures NO_DATA,
# 0 of 20 titles made up. The two lines marked v2 are the only change from v1 (NP-39), which sent 3 of 20 small data crops to NO_DATA and made up a chart title.
REGION_PROMPT = """You read one picture cut from a company report, so that what is printed on it can be found and quoted as text.
If the picture is only a logo, a photo, a signature or a decoration, with no digit printed on it and no table, chart or text with content, reply exactly: NO_DATA: <at most 8 words on what it shows>
If any number is printed on the picture, never reply NO_DATA, even when the picture is small or cut: copy what is visible.
Otherwise write plain text, in the language printed on the picture:
- Table: its title, unit and column headings as printed, then one line per row: the row label, then every cell separated by " | ", left to right. Write a printed dash as "-" and keep brackets, signs, % and currency marks as printed.
- Chart or infographic: its title, unit and period, then each label with its printed value, one per line.
- Text: copy the text.
Rules: copy every number exactly as printed (same digits, same separators, same unit). Write a title, unit or period only if it is printed on the picture; never add one that is not printed. Never compute a new number. Never estimate a value from an axis or from the height of a bar: write only what is printed. Do not guess what is cut off or not visible. No markdown, no commentary."""
REGION_MAX_TOKENS = 4000  # a full page of text came to 700 tokens, a table to 400

def _busy_wait(exc: Exception, n: int) -> Optional[float]:
    """Seconds to wait when `exc` is a busy answer (the server's Retry-After, else a growing pause), None for any other failure."""
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code not in BUSY_CODES:
        return None
    try:
        return float(exc.response.headers.get("Retry-After", ""))
    except ValueError:
        return min(60.0, BUSY_SECONDS * 2 ** (n - 1))


async def _call(job, label: str) -> Optional[str]:
    """`job()` until it gives a non-empty text: ATTEMPTS failures or empty replies, plus up to BUSY_WAITS busy answers waited out."""
    attempt = busy = 0
    while attempt < ATTEMPTS:
        try:
            text = await job()
            if text:
                return text
            attempt += 1
        except Exception as exc:  # recorded, never raised: the caller keeps Docling's text
            wait = _busy_wait(exc, busy + 1) if busy < BUSY_WAITS else None
            if wait is not None:
                busy += 1
                await asyncio.sleep(wait)
                continue
            attempt += 1
            logger.warning(f"{label}, attempt {attempt}: {type(exc).__name__}: {str(exc)[:160]}")
        await asyncio.sleep(RETRY_SECONDS * attempt)
    return None


# ---------------------------------------------------------------- cleaning Chandra's Markdown
# Ý nghĩa: Chandra viết "\$", bọc số trong <b>/<u>/<i>, xuống dòng trong ô bằng <br>, chỉ số chú thích bằng <sup>, chèn link ảnh (logo, chữ ký) và đôi khi bảng HTML.
# Giữ vì: đo 22/11 trên 60 trang, các thẻ này nằm trong 53 trang và làm số không khớp (97,1 % sau khi làm sạch so với 53,2 %); <br> phải thành dấu cách,
#   bỏ hẳn thì chữ hai bên dính nhau ("Share capital£"); chỉ số chú thích bằng chữ số thành số mũ dính liền ("1,016²", cùng dạng với F4 của postprocess, 23/11),
#   chỉ số khác thành "[a]", để không dính vào số ("1,016 2" đọc thành 10162).
ESCAPED = re.compile(r"\\([$%&#_*()\[\]-])")
BREAK = re.compile(r"\s*<br\s*/?>\s*", re.I)
NOTE_MARK = re.compile(r"\s*<sup>\s*([^<\s]{1,3})\s*</sup>", re.I)
FORMAT_TAG = re.compile(r"</?(?:b|i|u|strong|em|sup|sub|span|mark|s)(?:\s[^>]*)?>", re.I)
IMAGE_LINK = re.compile(r"!\[[^\]]*\]\([^)]*\)[ \t]*\n?\n?")
HTML_TABLE = re.compile(r"<table[^>]*>.*?</table>", re.I | re.S)


def _html_table(match: re.Match) -> str:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", match.group(0), flags=re.I | re.S):
        cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", BREAK.sub(" ", c))).split())
                 for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.I | re.S)]
        if cells:
            rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return ""
    width = rows[0].count(" | ") + 1
    return "\n".join([rows[0], "|" + "---|" * width] + rows[1:])


def clean_ocr(text: str) -> str:
    text = HTML_TABLE.sub(_html_table, text)
    text = IMAGE_LINK.sub("", text)
    text = ESCAPED.sub(r"\1", text)
    text = BREAK.sub(" ", text)
    text = NOTE_MARK.sub(lambda m: superscript(m.group(1)) if DIGIT_MARK.fullmatch(m.group(1)) else f" [{m.group(1)}]", text)
    return FORMAT_TAG.sub("", text).strip()


# ---------------------------------------------------------------- Datalab Chandra
def _one_page(pdf_path: Path, page: int) -> bytes:
    # widgets=False: the form-field tree of some reports (HSBC 2025) made MuPDF raise "exception stack overflow" on every page (23/11)
    with fitz.open(str(pdf_path)) as src, fitz.open() as one:
        one.insert_pdf(src, from_page=page - 1, to_page=page - 1, widgets=False)
        return one.tobytes()


async def _chandra_page(client: httpx.AsyncClient, data: bytes, key: str) -> str:
    headers = {"X-Api-Key": key}
    # disable_image_captions: by default Datalab writes a caption for each picture ("A line chart showing ...", up to 73 figures a page the PDF does not
    # print); off, the table rows are unchanged (80.4 % vs 80.5 % right on 40 pages) and what is left is caught by page_quality (rule_caption_marker_v2.txt, 24/11)
    r = await client.post(DATALAB_URL, headers=headers, files={"file": ("page.pdf", data, "application/pdf")},
                          data={"output_format": "markdown", "mode": settings.DATALAB_MODE, "disable_image_captions": "true"})
    r.raise_for_status()
    check = r.json()["request_check_url"]
    for _ in range(MAX_POLLS):
        await asyncio.sleep(POLL_SECONDS)
        r = await client.get(check, headers=headers)
        r.raise_for_status()
        body = r.json()
        if body.get("status") == "complete":
            if not body.get("markdown") and body.get("result_url"):  # a large result comes as a signed link
                body = (await client.get(body["result_url"])).json()
            return (body.get("markdown") or "").strip()
        if body.get("success") is False:
            raise RuntimeError(f"Datalab: {str(body.get('error'))[:200]}")
    raise TimeoutError("Datalab: no result")


async def read_chandra(pdf_path: Path, pages: List[int], client: Optional[httpx.AsyncClient] = None) -> Dict[int, str]:
    """{page: cleaned Markdown} for the pages Chandra read; a page that fails or comes back empty ATTEMPTS times is left out."""
    key = settings.DATALAB_API_KEY
    if not key or not pages:
        return {}
    own = client is None
    client = client or httpx.AsyncClient(timeout=120.0)
    gate = asyncio.Semaphore(settings.API_READ_CONCURRENCY)

    async def one(page: int) -> Optional[str]:
        data = await asyncio.to_thread(_one_page, pdf_path, page)

        async def job() -> str:
            async with gate:  # a busy wait does not hold a place
                return clean_ocr(await _chandra_page(client, data, key))

        return await _call(job, f"Chandra page {page} of {pdf_path.name}")

    try:
        texts = await asyncio.gather(*(one(p) for p in pages))
    finally:
        if own:
            await client.aclose()
    return {p: t for p, t in zip(pages, texts) if t}


# ---------------------------------------------------------------- the vision model
async def _ask_vision(png: bytes, prompt: str, max_tokens: int, label: str, client: Optional[httpx.AsyncClient], timeout: float = 60.0) -> Optional[str]:
    key = settings.OPENAI_API_KEY
    if not key:
        return None
    body = {"model": settings.FIGURE_MODEL, "temperature": 0, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt},
                                                      {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}]}]}
    own = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    async def job() -> str:
        r = await client.post(f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body)
        r.raise_for_status()
        return (r.json()["choices"][0]["message"].get("content") or "").strip()

    try:
        return await _call(job, label)
    finally:
        if own:
            await client.aclose()


async def describe_region(png: bytes, client: Optional[httpx.AsyncClient] = None) -> Optional[str]:
    """The text of an image region (REGION_PROMPT: a table row by row, a chart's printed values, a text copied), its lines kept; "NO_DATA: ..." for a logo,
    a photo or a signature; None (no key, or ATTEMPTS failures)."""
    return await _ask_vision(png, REGION_PROMPT, REGION_MAX_TOKENS, "Image region", client, timeout=90.0)  # a page of text took 10 s to write
