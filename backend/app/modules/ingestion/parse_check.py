"""Pages to check against the original, found at upload (owner 23/11: report a parse problem to the user instead of staying silent; research note
docs/VERSION_4/PARSING_SUA_VA_BAO_LOI_2026-11-23.md).

Runs after the OCR step and the figure step, on the pages as they will be chunked (no model), so a page is listed whether the OCR step is off, failed,
or returned a text it would not take:
  unread  a scanned page (no text layer, mostly picture) that still has no text, or a page of the PDF the parse did not return at all (owner 23/11,
          D4a: docling-parse <= 7.16 dropped pages when threaded; 0 such pages in 23,176 measured, TRIED NP-18, so a safety net): its figures cannot
          be found by any question
  tables  a page page_quality still finds garbled, short of most of its figures, holding printed table lines no table holds, or whose tables
          table_check.misread_tables finds misread (measured 39 of 40 flagged pages really misread), or whose Markdown tables show a defect with
          >= 1 wrong printed row (page_quality reason "defect", 36 of 40 really misread, plan 24/11 step 4). Its chunks get the flag "table_check"
          (chunker.py), so the citation of an excerpt from it says to check the page.
  figures a page with a picture the figure step chose and could not read (figures.py "figure_failed", owner 24/11: the user is told what was not
          processed), or a page whose vector picture holds printed figures the parse lost ("chart_unread": Docling drops the text inside a picture
          box; reading those charts failed twice, TRIED NP-17 / NP-25; 26 of 30 such pictures really charts or figures, rule_layout_checks.txt V);
          the key is only there when some page has one. Both kinds give their chunks the flag "picture_unread" (chunker.py).
The document keeps the lists (DocumentRecord.parse_issues); the document card shows them with the page numbers, naming no component.
"""
import asyncio
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import fitz  # PyMuPDF

from app.core.logging import logger
from app.modules.ingestion.page_quality import MIN_LAYER_CHARS, bad_pages

IMAGE_MARK = "<!-- image -->"
# A vector picture whose printed figures the parse lost (rule_layout_checks.txt part V, the D3 detector of experiments chart_text._block, unchanged):
# at least CHART_MIN_WORDS text-layer words inside its box (figures.MAX_WORDS_INSIDE: fewer go to the vision model), under CHART_MAX_PRESENT of them
# already in the page's text, and at least CHART_MIN_NEW_NUMBERS numbers new to it. Or (plan B4, 25/11, rule_b4_charts.txt, TRIED NP-47: a chart's axis
# years, title and legend are often printed elsewhere on the page, so its words look "present" while its values are lost): at least CHART_MIN_NEW_NUMBERS
# of its distinct numbers new to the page, and at least CHART_MIN_NEW_SHARE of them. On 170 documents it adds 30 pages: 15 lose printed figures, 9 are charts
# that print no values (owner 25/11: listed too, their content is not in the text either), 2 borderline, 4 diagrams with numbering.
CHART_MIN_WORDS = 5
CHART_MAX_PRESENT = 0.5
CHART_MIN_NEW_NUMBERS = 2
CHART_MIN_NEW_SHARE = 0.5
_PUNCT = "$€£¥()%,.;:*\"'“”‘’[]"


def _charts_unread(doc: "fitz.Document", pages: Sequence[Dict[str, Any]]) -> set:
    out = set()
    for p in pages:
        n = p["page_number"]
        if not p.get("pictures") or not 1 <= n <= len(doc):
            continue
        tokens = (p.get("text") or "").replace("|", " ").split()
        seen_words = {t.strip(_PUNCT).lower() for t in tokens}
        seen_numbers = {re.sub(r"\D", "", t) for t in tokens} - {""}
        words = doc[n - 1].get_text("words")
        for x0, y0, x1, y1 in p["pictures"]:
            inside = [w[4] for w in words if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1]
            if len(inside) < CHART_MIN_WORDS:
                continue
            digits = [re.sub(r"\D", "", t) for t in inside]
            present = sum(1 for t, d in zip(inside, digits) if (d in seen_numbers if d else t.strip(_PUNCT).lower() in seen_words))
            new = sum(1 for d in digits if d and d not in seen_numbers)
            numbers = {d for d in digits if d}
            lost = numbers - seen_numbers
            if (present < CHART_MAX_PRESENT * len(inside) and new >= CHART_MIN_NEW_NUMBERS) or \
                    (len(lost) >= CHART_MIN_NEW_NUMBERS and len(lost) >= CHART_MIN_NEW_SHARE * len(numbers)):
                out.add(n)
                break
    return out


def check_pages(pdf_path: Path, pages: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, List[int]]]:
    """(pages, with "table_check": True on the pages to check; {"tables": [page numbers], "unread": [page numbers]})."""
    text = {p["page_number"]: p.get("text") or "" for p in pages}
    # the broad reasons of the re-read, minus "rows" (40 % really misread): "defect" was 36 of 40 really misread (plan 24/11 step 4, rule_user_list_defect.txt)
    bad = {n: why for n, why in bad_pages(pdf_path, pages, broad=True).items() if why != "rows"}
    unread = {n for n, why in bad.items() if why == "scanned" and len(re.sub(r"\s", "", text[n].replace(IMAGE_MARK, ""))) < MIN_LAYER_CHARS}
    with fitz.open(str(pdf_path)) as doc:
        missing = [n for n in range(1, len(doc) + 1) if n not in text]
        charts = _charts_unread(doc, pages)
    if missing:
        logger.warning(f"Pages missing from the parse of {Path(pdf_path).name}: {missing}")
    tables = {n for n, why in bad.items() if why != "scanned"}
    tables |= {p["page_number"] for p in pages if p.get("ocr_unsure")}  # a scan re-read with chart text the reader wrote (page_quality.CHART_TEXT)
    issues ={"tables": sorted(tables), "unread": sorted(unread | set(missing))}
    figures = sorted({p["page_number"] for p in pages if p.get("figure_failed")} | charts)
    if figures:
        issues["figures"] = figures
    marks = lambda n: {**({"table_check": True} if n in tables else {}), **({"chart_unread": True} if n in charts else {})}
    return [{**p, **marks(p["page_number"])} if marks(p["page_number"]) else p for p in pages], issues


async def check_safely(pdf_path: Path, pages: List[Dict[str, Any]], info: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, List[int]]]:
    """check_pages in a thread; an extra like the OCR step: a failure leaves the pages as they are and lists nothing. `info` (the pipeline's timings)
    receives check (seconds), check_tables and check_unread (how many pages)."""
    t0 = time.perf_counter()
    try:
        pages, issues = await asyncio.to_thread(check_pages, pdf_path, pages)
    except Exception as exc:
        logger.warning(f"Page check skipped for {Path(pdf_path).name}: {type(exc).__name__}: {str(exc)[:160]}")
        return pages, {}
    info.update(check=round(time.perf_counter() - t0, 2), check_tables=len(issues["tables"]), check_unread=len(issues["unread"]))
    return pages, issues
