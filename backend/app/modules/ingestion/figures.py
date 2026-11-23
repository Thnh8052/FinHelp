"""Pictures whose figures are only in the pixels are described by the vision model (22/11), after the OCR fallback, before chunking.

Docling writes MARKER for each picture of a page and the worker sends each picture's box ("pictures": [[x0, y0, x1, y1], ...] in PDF points, top-left origin,
postprocess/pictures.page_pictures) in the same order: checked on 130 of 130 raw pages and 607 of 607 pages after the backend postprocess (SEC 134).
A picture is read when (the "image" class of the VLM bench, experiments/scripts/parsing_metric/vlm_bench_build.py):
  - it covers at least MIN_PICTURE_SHARE of the page,
  - embedded raster images cover at least MIN_RASTER_COVER of it, and
  - fewer than MAX_WORDS_INSIDE words of the PDF text layer are inside it.
Not read: a vector chart (its printed values are text already), a small logo, a page the OCR fallback read again ("ocr": Chandra describes its pictures itself).
The description replaces the picture's marker, prefixed "[Figure read from the image, page N]" (the chunk gets the flag "figure"); "NO_DATA" (a photo, a logo)
or a failed call leaves the marker. A failed call also marks the page "figure_failed", so the document card lists it (owner 24/11: the user is told what
was not processed). If the markers and the boxes do not match in number, the descriptions go at the end of the page.
"""
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from app.core.config import settings
from app.core.logging import logger
from app.modules.ingestion.api_readers import describe_picture

MARKER = "<!-- image -->"
FIGURE_MARK = "[Figure read from the image"
MIN_PICTURE_SHARE = 0.03
MIN_RASTER_COVER = 0.6
MAX_WORDS_INSIDE = 5
DPI = 150
PAD = 6.0  # points around the box, as in the bench crops


def _raster_cover(page: "fitz.Page", rect: "fitz.Rect") -> float:
    covered = 0.0
    for info in page.get_image_info():
        inter = fitz.Rect(info["bbox"]) & rect
        if not inter.is_empty:
            covered += inter.width * inter.height
    return min(1.0, covered / ((rect.width * rect.height) or 1.0))


def pictures_to_read(pdf_path: Path, pages: List[Dict[str, Any]]) -> List[Tuple[int, int, list]]:
    """[(page number, index of the picture on its page, box)] of the pictures to describe."""
    out = []
    todo = [p for p in pages if p.get("pictures") and not p.get("ocr")]
    if not todo:
        return out
    with fitz.open(str(pdf_path)) as doc:
        for p in todo:
            n = p["page_number"]
            if not 1 <= n <= len(doc):
                continue
            page = doc[n - 1]
            area = (page.rect.width * page.rect.height) or 1.0
            words = page.get_text("words")
            for k, box in enumerate(p["pictures"]):
                rect = fitz.Rect(box) & page.rect
                if rect.is_empty or rect.width * rect.height < MIN_PICTURE_SHARE * area:
                    continue
                inside = sum(1 for w in words if rect.contains(fitz.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)))
                if inside < MAX_WORDS_INSIDE and _raster_cover(page, rect) >= MIN_RASTER_COVER:
                    out.append((n, k, box))
    return out


def _crop(pdf_path: Path, jobs: List[Tuple[int, int, list]]) -> List[bytes]:
    with fitz.open(str(pdf_path)) as doc:
        return [doc[n - 1].get_pixmap(dpi=DPI, clip=(fitz.Rect(box) + (-PAD, -PAD, PAD, PAD)) & doc[n - 1].rect).tobytes("png") for n, _, box in jobs]


def _place(page: Dict[str, Any], found: Dict[int, str]) -> str:
    n, text = page["page_number"], page["text"]
    blocks = {k: f"[Figure read from the image, page {n}] {d}" for k, d in found.items()}
    parts = text.split(MARKER)
    if len(parts) - 1 != len(page["pictures"]):
        return text.rstrip() + "".join(f"\n\n{blocks[k]}" for k in sorted(blocks))
    return parts[0] + "".join(blocks.get(k, MARKER) + rest for k, rest in enumerate(parts[1:]))


async def read_figures(pdf_path: Path, pages: List[Dict[str, Any]], describe) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """(pages with the descriptions in place, report {"chosen", "described", "no_data", "failed"}). `describe(png) -> str | None`."""
    jobs = await asyncio.to_thread(pictures_to_read, pdf_path, pages)
    report = {"chosen": len(jobs), "described": 0, "no_data": 0, "failed": 0}
    if not jobs:
        return pages, report
    images = await asyncio.to_thread(_crop, pdf_path, jobs)
    gate = asyncio.Semaphore(settings.API_READ_CONCURRENCY)

    async def one(png: bytes) -> Optional[str]:
        async with gate:
            try:
                return await describe(png)
            except Exception as exc:  # an extra: the marker stays
                logger.warning(f"Picture description failed: {type(exc).__name__}")
                return None

    replies = await asyncio.gather(*(one(png) for png in images))
    found: Dict[int, Dict[int, str]] = {}
    failed = set()  # owner 24/11: a picture chosen and left unread is reported on the document card (parse_check.py "figures")
    for (n, k, _), reply in zip(jobs, replies):
        if not reply:
            report["failed"] += 1
            failed.add(n)
        elif reply.lstrip().upper().startswith("NO_DATA"):
            report["no_data"] += 1
        else:
            found.setdefault(n, {})[k] = " ".join(reply.split())
            report["described"] += 1
    out = [{**p, "text": _place(p, found[p["page_number"]])} if p["page_number"] in found else p for p in pages]
    return [{**p, "figure_failed": True} if p["page_number"] in failed else p for p in out], report


async def read_figures_if_enabled(pdf_path: Path, pages: List[Dict[str, Any]], info: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """`pages` unchanged unless FIGURE_READER_ENABLED; `info` (the pipeline's timings) receives figures_chosen and figures_described, and figures_failed
    when a picture could not be read."""
    if not settings.FIGURE_READER_ENABLED or not any(p.get("pictures") for p in pages):
        return pages
    pages, report = await read_figures(pdf_path, pages, describe_picture)
    if info is not None:
        info.update({"figures_chosen": report["chosen"], "figures_described": report["described"]})
        if report["failed"]:
            info["figures_failed"] = report["failed"]
    if report["chosen"]:
        logger.info(f"Pictures of {pdf_path.name}: {report}")
    return pages
