"""Which pages did Docling read badly, and an OCR fallback for those pages only (spec L8; stage 1 of the OCR fallback, 14/11).

Docling runs with do_ocr=False, so a scanned page (a picture of text) gives an empty text. Three signals, all from the PDF and Docling's own output, no model:
  scanned  the page has no text layer (fewer than MIN_LAYER_CHARS characters) and pictures cover at least SCAN_IMAGE_SHARE of it; a cover with a small logo and a blank page are not scans
  garbled  Docling's text holds MIN_GARBLED or more broken glyphs ("(cid:12)", U+FFFD): a font the parser could not decode
  missing  the PDF's text layer holds at least MIN_LAYER_NUMBERS figures and Docling's text holds fewer than NUMBER_RECALL of them (figures compared by their digits, so "1,037"
           and "1037" are the same): text was lost. A page with few figures is not judged by them.

`rescue_pages` sends the bad pages (at most `max_pages`, in page order) to an OCR reader once, and takes what comes back for a page only when it is not empty and has at least as many
figures as the text it replaces; the page is marked "ocr": True (the chunker turns that into the chunk flag "ocr", and the answer is told those excerpts came from OCR). A reader that
fails leaves Docling's pages: the fallback is an extra and never fails an ingestion. `READERS` maps a backend name (settings.OCR_BACKEND) to an async reader
`(pdf_path, page_numbers) -> {page_number: markdown}`; it is empty until stage 2 registers one.
"""
import asyncio
import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF

from app.core.config import settings
from app.core.logging import logger

MIN_LAYER_CHARS = 20
SCAN_IMAGE_SHARE = 0.5
MIN_GARBLED = 3
MIN_LAYER_NUMBERS = 10
NUMBER_RECALL = 0.5
GARBLED = re.compile(r"\(cid:\d+\)|�")
NUMBER = re.compile(r"\d[\d,.]*\d|\d")

OcrReader = Callable[[Path, List[int]], Awaitable[Dict[int, str]]]
READERS: Dict[str, OcrReader] = {}


def garbled(text: str) -> bool:
    return len(GARBLED.findall(text)) >= MIN_GARBLED


def _numbers(text: str) -> set:
    """The figures of a text as digit strings of three or more digits ("1,037" and "1037" alike): shorter numbers are list markers and counts."""
    return {d for d in (re.sub(r"\D", "", token) for token in NUMBER.findall(text)) if len(d) >= 3}


def _image_share(pdf_page) -> float:
    rect = pdf_page.rect
    area = (rect.width * rect.height) or 1.0
    covered = 0.0
    for info in pdf_page.get_image_info():
        box = fitz.Rect(info["bbox"]) & rect
        if not box.is_empty:
            covered += box.width * box.height
    return min(1.0, covered / area)


def bad_pages(pdf_path: Path, pages: Sequence[Dict[str, Any]]) -> Dict[int, str]:
    """{page number: "garbled" | "scanned" | "missing"} for the pages Docling's text (`pages`: [{"page_number", "text"}]) does not do justice to. A page number outside the PDF is ignored."""
    out: Dict[int, str] = {}
    with fitz.open(str(pdf_path)) as doc:
        for p in pages:
            n, text = p["page_number"], p.get("text") or ""
            if not 1 <= n <= len(doc):
                continue
            if garbled(text):
                out[n] = "garbled"
                continue
            pdf_page = doc[n - 1]
            layer = pdf_page.get_text()
            if len(re.sub(r"\s", "", layer)) < MIN_LAYER_CHARS:
                if _image_share(pdf_page) >= SCAN_IMAGE_SHARE:
                    out[n] = "scanned"
                continue
            wanted = _numbers(layer)
            if len(wanted) >= MIN_LAYER_NUMBERS and len(wanted & _numbers(text)) / len(wanted) < NUMBER_RECALL:
                out[n] = "missing"
    return out


async def rescue_pages(pdf_path: Path, pages: List[Dict[str, Any]], read: OcrReader, max_pages: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """(pages with the OCR text of the rescued ones, report {"bad": {page: reason}, "sent": [pages], "replaced": [pages], "over_cap": int, "error"?: type name})."""
    bad = await asyncio.to_thread(bad_pages, pdf_path, pages)
    sent = sorted(bad)[:max_pages]
    report: Dict[str, Any] = {"bad": bad, "sent": sent, "replaced": [], "over_cap": len(bad) - len(sent)}
    if not sent:
        return pages, report
    try:
        read_pages = await read(pdf_path, sent)
    except Exception as exc:  # the fallback is an extra: Docling's pages stand
        report["error"] = type(exc).__name__
        logger.warning(f"OCR fallback skipped for {pdf_path.name}: {type(exc).__name__}: {str(exc)[:160]}")
        return pages, report
    out: List[Dict[str, Any]] = []
    for p in pages:
        text = (read_pages.get(p["page_number"]) or "").strip() if p["page_number"] in sent else ""
        if text and len(_numbers(text)) >= len(_numbers(p.get("text") or "")):  # never swap in a text with fewer figures
            out.append({**p, "text": text, "ocr": True})
            report["replaced"].append(p["page_number"])
        else:
            out.append(p)
    return out, report


async def rescue_if_enabled(pdf_path: Path, pages: List[Dict[str, Any]], info: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """`pages` unchanged unless OCR_FALLBACK_ENABLED and OCR_BACKEND names a registered reader; `info` receives ocr_bad_pages and ocr_replaced_pages (the pipeline's timings)."""
    read = READERS.get(settings.OCR_BACKEND)
    if not settings.OCR_FALLBACK_ENABLED or read is None:
        return pages
    pages, report = await rescue_pages(pdf_path, pages, read, settings.OCR_FALLBACK_MAX_PAGES)
    if info is not None:
        info.update({"ocr_bad_pages": len(report["bad"]), "ocr_replaced_pages": len(report["replaced"])})
    if report["bad"]:
        logger.info(f"OCR fallback on {pdf_path.name}: bad pages {report['bad']}, replaced {report['replaced']}, left over the cap {report['over_cap']}")
    return pages
