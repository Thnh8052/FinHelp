"""Images pasted on a page with a text layer that Docling gave no picture box for (a table pasted as a picture: Enablence p42, a bad-debt line of 166),
read by the vision model after the OCR fallback, before the page check (experiments TRIED NP-38 to NP-40, NP-46).

Owner 25/11 (plan "parsing gọn lại"): the one model reader kept, on two conditions:
  1. an image under a Docling picture box (covering REGION_OVERLAP of it or more, the box at least MIN_PICTURE_SHARE of the page) is never read: Docling saw
     a picture there, and parse_check lists those pages as not processed;
  2. a region read is not listed (the page keeps "regions_read", parse_check skips those images); one the model could not read stays listed.
Skipped: a page the OCR fallback read again ("ocr": the reader read the whole page image), a page with no text layer (a scan: the OCR fallback's), an image
drawn twice. Each crop is sent with REGION_PROMPT (api_readers.describe_region) and the reply appended to the page, lines kept, after
"[Figure read from the image, page N]" (the chunk gets the flag "figure"). NO_DATA (a logo, a photo, a signature) is an answer: the image counts as read.
"""
import asyncio
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF

from app.core.config import settings
from app.core.logging import logger
from app.modules.ingestion.api_readers import describe_region

MARKER = "<!-- image -->"
FIGURE_MARK = "[Figure read from the image"
MIN_PICTURE_SHARE = 0.03  # of the page: a logo or an icon is smaller
MAX_WORDS_INSIDE = 5  # text-layer words on an image from this many: a background or a hidden text layer, its text is read already
REGION_MARGIN = 3.0  # points: a word this close to the image counts as on it (AMCOR 409A plan: 144 to 604 hidden words on one line just under the image)
REGION_OVERLAP = 0.5  # share of the image covered by a Docling picture box that makes it Docling's picture (condition 1)
UNPAIRED_RUN = 3  # single values in a row with no label (blank lines between do not count): the reader listed the values apart from their labels
DPI = 150
PAD = 6.0  # points around the box, as in the bench crops
_LETTER = re.compile(r"[^\W\d_]")
_NUMBER = re.compile(r"\d[\d,.]*")
_YEAR = re.compile(r"(?:19|20)\d\d")


def same_box(a: Sequence[float], b: Sequence[float]) -> bool:
    return all(abs(x - y) < 1 for x, y in zip(a, b))


def _share(a: "fitz.Rect", b: "fitz.Rect") -> float:
    inter = a & b
    return 0.0 if inter.is_empty else inter.width * inter.height / ((a.width * a.height) or 1.0)


def pasted_images(page: "fitz.Page", boxes: Sequence[Sequence[float]]) -> List["fitz.Rect"]:
    """The raster images of a page with a text layer (any word) that no step reads but this one: >= MIN_PICTURE_SHARE of the page, fewer than MAX_WORDS_INSIDE
    text-layer words within REGION_MARGIN, drawn once, not under a Docling picture box of >= MIN_PICTURE_SHARE (condition 1)."""
    words = page.get_text("words")
    if not words:  # a scan: the OCR fallback's
        return []
    least = MIN_PICTURE_SHARE * ((page.rect.width * page.rect.height) or 1.0)
    docling = [r for r in (fitz.Rect(b) & page.rect for b in boxes) if not r.is_empty and r.width * r.height >= least]
    seen: List["fitz.Rect"] = []
    out: List["fitz.Rect"] = []
    for info in page.get_image_info():
        rect = fitz.Rect(info["bbox"]) & page.rect
        if rect.is_empty or rect.width * rect.height < least or any(same_box(rect, o) for o in seen):
            continue
        seen.append(rect)
        near = rect + (-REGION_MARGIN, -REGION_MARGIN, REGION_MARGIN, REGION_MARGIN)
        if sum(1 for w in words if near.contains(fitz.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))) >= MAX_WORDS_INSIDE:
            continue
        if any(_share(rect, d) >= REGION_OVERLAP for d in docling):
            continue
        out.append(rect)
    return out


def regions_to_read(pdf_path: Path, pages: List[Dict[str, Any]]) -> List[Tuple[int, int, list]]:
    """[(page number, index of the region on its page, box in PDF points)] of the images to read (pasted_images), pages the OCR fallback read again skipped."""
    out = []
    with fitz.open(str(pdf_path)) as doc:
        for p in pages:
            n = p["page_number"]
            if p.get("ocr") or not 1 <= n <= len(doc):
                continue
            for k, rect in enumerate(pasted_images(doc[n - 1], p.get("pictures") or [])):
                out.append((n, k, [round(v, 1) for v in rect]))
    return out


def _crop(pdf_path: Path, jobs: List[Tuple[int, int, list]]) -> List[bytes]:
    with fitz.open(str(pdf_path)) as doc:
        return [doc[n - 1].get_pixmap(dpi=DPI, clip=(fitz.Rect(box) + (-PAD, -PAD, PAD, PAD)) & doc[n - 1].rect).tobytes("png") for n, _, box in jobs]


def unpaired_values(reply: str) -> bool:
    """True when UNPAIRED_RUN or more lines in a row hold one number and nothing else (not a year): the values are listed apart from their labels, so a number could
    be quoted against the wrong label (1 of 4 waterfall charts in the NP-40 trial). A row label, a year before its value or several cells on a line is a pair."""
    run = 0
    for line in reply.splitlines():
        s = line.strip()
        if not s:
            continue
        tokens = _NUMBER.findall(s)
        if len(tokens) == 1 and not _LETTER.search(s) and not _YEAR.fullmatch(tokens[0]):
            run += 1
            if run >= UNPAIRED_RUN:
                return True
        else:
            run = 0
    return False


async def read_regions(pdf_path: Path, pages: List[Dict[str, Any]], describe) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """(pages with the replies appended and "regions_read": [boxes answered for], report {"chosen", "described", "no_data", "failed"}). `describe(png) -> str | None`.
    A failed call, or a reply with values apart from their labels, leaves the page as it was (parse_check lists the image); NO_DATA is an answer."""
    jobs = await asyncio.to_thread(regions_to_read, pdf_path, pages)
    report = {"chosen": len(jobs), "described": 0, "no_data": 0, "failed": 0}
    if not jobs:
        return pages, report
    images = await asyncio.to_thread(_crop, pdf_path, jobs)
    gate = asyncio.Semaphore(settings.API_READ_CONCURRENCY)

    async def one(png: bytes) -> Optional[str]:
        async with gate:
            try:
                return await describe(png)
            except Exception as exc:  # an extra: the page keeps Docling's text
                logger.warning(f"Image region reading failed: {type(exc).__name__}")
                return None

    replies = await asyncio.gather(*(one(png) for png in images))
    found: Dict[int, List[str]] = {}
    read: Dict[int, List[list]] = {}
    for (n, _, box), reply in zip(jobs, replies):
        if not reply or unpaired_values(reply):
            report["failed"] += 1
            continue
        read.setdefault(n, []).append(box)
        if reply.lstrip().upper().startswith("NO_DATA"):
            report["no_data"] += 1
        else:
            found.setdefault(n, []).append("\n".join(line.rstrip() for line in reply.strip().splitlines()))
            report["described"] += 1
    out = []
    for p in pages:
        n = p["page_number"]
        if n in found:
            p = {**p, "text": p["text"].rstrip() + "".join(f"\n\n{FIGURE_MARK}, page {n}]\n{t}" for t in found[n])}
        out.append({**p, "regions_read": read[n]} if n in read else p)
    return out, report


async def read_regions_if_enabled(pdf_path: Path, pages: List[Dict[str, Any]], info: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """`pages` unchanged unless IMAGE_REGION_READER_ENABLED; `info` (the pipeline's timings) receives regions_chosen and regions_described, and regions_failed
    when a region could not be read; nothing when the document has no such region."""
    if not settings.IMAGE_REGION_READER_ENABLED:
        return pages
    pages, report = await read_regions(pdf_path, pages, describe_region)
    if report["chosen"]:
        logger.info(f"Image regions of {pdf_path.name}: {report}")
        if info is not None:
            info.update({"regions_chosen": report["chosen"], "regions_described": report["described"]})
            if report["failed"]:
                info["regions_failed"] = report["failed"]
    return pages
