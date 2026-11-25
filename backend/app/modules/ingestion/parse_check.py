"""Pages to check against the original, found at upload (owner 23/11: report a parse problem to the user instead of staying silent; research note
docs/VERSION_4/PARSING_SUA_VA_BAO_LOI_2026-11-23.md).

Runs after the OCR step, on the pages as they will be chunked (no model), so a page is listed whether the OCR step is off, failed, or returned a text
it would not take:
  unread  a scanned page (no text layer, mostly picture) that still has no text, or a page of the PDF the parse did not return at all (owner 23/11,
          D4a: docling-parse <= 7.16 dropped pages when threaded; 0 such pages in 23,176 measured, TRIED NP-18, so a safety net): its figures cannot
          be found by any question
  tables  a page whose page_quality signals are right at least REPORT_AT of the time (page_confidence): garbled, short of most of its figures, or whose
          tables table_check finds misread (table_check, defect). Its chunks get the flag "table_check" (chunker.py), so the citation of an excerpt
          from it says to check the page.
  figures a page with a text layer holding a picture of >= MIN_PICTURE_SHARE of the page that no step read: a Docling picture box (Docling drops the text
          inside it, so a chart's printed values are lost too; no model reads those since 25/11, owner, plan "parsing gọn lại"), or a pasted image
          (image_regions.pasted_images) the region reader did not answer for ("regions_read") on a page the OCR fallback did not read again. The user is
          told they were not processed. The key is only there when some page has one; those pages are marked "picture_unread" (every chunk of the page
          gets the flag, chunker.py). A scan is the OCR step's.
The document keeps the lists (DocumentRecord.parse_issues); the document card shows them with the page numbers, naming no component.
"""
import asyncio
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import fitz  # PyMuPDF

from app.core.logging import logger
from app.modules.ingestion.page_confidence import REPORT_AT, REREAD_AT, p_wrong, reported
from app.modules.ingestion.image_regions import MIN_PICTURE_SHARE, pasted_images, same_box
from app.modules.ingestion.page_quality import MIN_LAYER_CHARS, text_signals

def _has_picture(page: "fitz.Page", p: Dict[str, Any]) -> bool:
    if len(re.sub(r"\s", "", page.get_text())) < MIN_LAYER_CHARS:
        return False
    least = MIN_PICTURE_SHARE * ((page.rect.width * page.rect.height) or 1.0)
    for box in p.get("pictures") or []:  # Docling's picture boxes, PDF points with a top-left origin, like PyMuPDF's
        r = fitz.Rect(box) & page.rect
        if not r.is_empty and r.width * r.height >= least:
            return True
    if p.get("ocr"):  # the OCR fallback read the whole page image, pasted images included
        return False
    done = p.get("regions_read") or []
    return any(not any(same_box(r, d) for d in done) for r in pasted_images(page, p.get("pictures") or []))


def check_pages(pdf_path: Path, pages: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, List[int]]]:
    """(pages, with "table_check": True on the pages to check and "picture_unread": True on the pages with a picture; {"tables": [page numbers],
    "unread": [page numbers], "figures"?: [page numbers]}). A page is on "tables" or "unread" when its signals (page_quality.text_signals with the broad
    ones) make page_confidence.p_wrong >= REPORT_AT: "rows" and "rows1" stay off the list, "defect" is on it."""
    text = {p["page_number"]: p.get("text") or "" for p in pages}
    signals: Dict[int, List[str]] = {}
    pictures = set()
    with fitz.open(str(pdf_path)) as doc:
        missing = [n for n in range(1, len(doc) + 1) if n not in text]
        for p in pages:
            n = p["page_number"]
            if 1 <= n <= len(doc):
                signals[n] = text_signals(doc[n - 1], text[n], broad=True)
                if _has_picture(doc[n - 1], p):
                    pictures.add(n)
    if missing:
        logger.warning(f"Pages missing from the parse of {Path(pdf_path).name}: {missing}")
    lists = {n: reported(s) for n, s in signals.items()}
    doubtful = sorted(n for n, s in signals.items() if REREAD_AT <= p_wrong(s) < REPORT_AT)
    if doubtful:  # for the admin's logs: read again where a reader could, never shown to the user
        logger.info(f"Pages of {Path(pdf_path).name} below the user's bar: {doubtful}")
    tables = {n for n, k in lists.items() if "tables" in k}
    issues = {"tables": sorted(tables), "unread": sorted({n for n, k in lists.items() if "unread" in k} | set(missing))}
    if pictures:
        issues["figures"] = sorted(pictures)
    marks = lambda n: {**({"table_check": True} if n in tables else {}), **({"picture_unread": True} if n in pictures else {})}
    return [{**p, **marks(p["page_number"])} if marks(p["page_number"]) else p for p in pages], issues


async def check_safely(pdf_path: Path, pages: List[Dict[str, Any]], info: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, List[int]]]:
    """check_pages in a thread; an extra like the OCR step: a failure leaves the pages as they are and lists nothing. `info` (the pipeline's timings)
    receives check (seconds), check_tables, check_unread and check_figures (how many pages)."""
    t0 = time.perf_counter()
    try:
        pages, issues = await asyncio.to_thread(check_pages, pdf_path, pages)
    except Exception as exc:
        logger.warning(f"Page check skipped for {Path(pdf_path).name}: {type(exc).__name__}: {str(exc)[:160]}")
        return pages, {}
    info.update(check=round(time.perf_counter() - t0, 2), check_tables=len(issues["tables"]), check_unread=len(issues["unread"]),
                check_figures=len(issues.get("figures", [])))
    return pages, issues
