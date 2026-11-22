"""The two paid readers of the parsing pipeline (22/11), called with httpx (already a dependency; the Datalab and OpenAI client libraries are not needed).

  read_chandra      Datalab Chandra reads whole pages again: one single-page PDF per request (the measured setup), the Markdown cleaned by `clean_ocr`.
                    Registered in page_quality.READERS["chandra"]. Measured: 97.1 % of 648 true table rows on 40 scanned IFRS pages once cleaned, 53.2 % raw
                    ("\\$" and <b> stick to the figures), Docling with OCR 92.0 % (experiments/results/docs/parsing/ocr_scan_2026-11-22.md).
  describe_picture  the vision model (settings.FIGURE_MODEL) describes one cropped picture with FIGURE_PROMPT, the one prompt the bench measured
                    (gpt-4.1-mini: label next to its value 92 %, NO_DATA on 5 of 5 logos and photos; vlm_bench_2026-11-22.md).

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

DATALAB_URL = "https://www.datalab.to/api/v1/convert"
ATTEMPTS = 3
POLL_SECONDS = 1.0
MAX_POLLS = 300  # 5 minutes for one page
RETRY_SECONDS = 2.0

FIGURE_PROMPT = """You describe one picture cut from a company report, so that its content can be found and quoted as text.
If the picture is only a logo, a photo, a signature or a decoration with no data, reply exactly: NO_DATA: <at most 8 words on what it shows>
Otherwise write one plain paragraph of at most 80 words, in the language of the text printed on the picture (English if there is none):
- the kind of picture (line chart, bar chart, pie chart, waterfall chart, table, diagram, ...) and its title if printed;
- the unit and the period;
- each series or category name with its values exactly as printed;
- the main trend or comparison.
Rules: copy numbers exactly as printed (same digits, same unit). Never compute new numbers. If a value is not printed and you read it from an axis, write it with "~" (for example ~240). Do not guess what is not visible. No markdown."""

# ---------------------------------------------------------------- cleaning Chandra's Markdown
# Ý nghĩa: Chandra viết "\$", bọc số trong <b>/<u>/<i>, xuống dòng trong ô bằng <br>, chỉ số chú thích bằng <sup>, chèn link ảnh (logo, chữ ký) và đôi khi bảng HTML.
# Giữ vì: đo 22/11 trên 60 trang, các thẻ này nằm trong 53 trang và làm số không khớp (97,1 % sau khi làm sạch so với 53,2 %); <br> phải thành dấu cách,
#   bỏ hẳn thì chữ hai bên dính nhau ("Share capital£"); chỉ số chú thích thành "[3]" để không dính vào số ("1,016 2" đọc thành 10162, lỗi F4).
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
    text = NOTE_MARK.sub(r" [\1]", text)
    return FORMAT_TAG.sub("", text).strip()


# ---------------------------------------------------------------- Datalab Chandra
def _one_page(pdf_path: Path, page: int) -> bytes:
    with fitz.open(str(pdf_path)) as src, fitz.open() as one:
        one.insert_pdf(src, from_page=page - 1, to_page=page - 1)
        return one.tobytes()


async def _chandra_page(client: httpx.AsyncClient, data: bytes, key: str) -> str:
    headers = {"X-Api-Key": key}
    r = await client.post(DATALAB_URL, headers=headers, files={"file": ("page.pdf", data, "application/pdf")},
                          data={"output_format": "markdown", "mode": settings.DATALAB_MODE})
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
        for attempt in range(1, ATTEMPTS + 1):
            try:
                async with gate:
                    text = clean_ocr(await _chandra_page(client, data, key))
                if text:
                    return text
            except Exception as exc:  # recorded, never raised: Docling's page stands
                logger.warning(f"Chandra page {page} of {pdf_path.name}, attempt {attempt}: {type(exc).__name__}: {str(exc)[:160]}")
            await asyncio.sleep(RETRY_SECONDS * attempt)
        return None

    try:
        texts = await asyncio.gather(*(one(p) for p in pages))
    finally:
        if own:
            await client.aclose()
    return {p: t for p, t in zip(pages, texts) if t}


# ---------------------------------------------------------------- the vision model
async def describe_picture(png: bytes, client: Optional[httpx.AsyncClient] = None) -> Optional[str]:
    """The picture's description, "NO_DATA: ..." for a logo or photo, or None (no key, or ATTEMPTS failures)."""
    key = settings.OPENAI_API_KEY
    if not key:
        return None
    body = {"model": settings.FIGURE_MODEL, "temperature": 0, "max_tokens": 400,
            "messages": [{"role": "user", "content": [{"type": "text", "text": FIGURE_PROMPT},
                                                      {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}]}]}
    own = client is None
    client = client or httpx.AsyncClient(timeout=60.0)
    try:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                r = await client.post(f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body)
                r.raise_for_status()
                text = (r.json()["choices"][0]["message"].get("content") or "").strip()
                if text:
                    return text
            except Exception as exc:
                logger.warning(f"Picture description, attempt {attempt}: {type(exc).__name__}: {str(exc)[:160]}")
            await asyncio.sleep(RETRY_SECONDS * attempt)
        return None
    finally:
        if own:
            await client.aclose()
