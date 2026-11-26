"""Which pages did Docling read badly, and an OCR fallback for those pages only (spec L8; stage 1 of the OCR fallback, 14/11).

Docling runs with do_ocr=False, so a scanned page (a picture of text) gives an empty text. Three signals, all from the PDF and Docling's own output, no model:
  scanned  the page has no text layer (fewer than MIN_LAYER_CHARS characters) and pictures cover at least SCAN_IMAGE_SHARE of it; a cover with a small logo and a blank page are not scans
  garbled  Docling's text holds MIN_GARBLED or more broken glyphs ("(cid:12)", U+FFFD): a font the parser could not decode
  missing  the PDF's text layer holds at least MIN_LAYER_NUMBERS figures and Docling's text holds fewer than NUMBER_RECALL of them (figures compared by their digits, so "1,037"
           and "1037" are the same): text was lost. A page with few figures is not judged by them.
  lost_table  the F3 detector (postprocess/table_rebuild.lost_regions) still finds printed table lines whose figures are in the text but in no table: a table F3 could not
           rebuild or place (22/11; rebuild first, OCR only where it fails: 234 vs 201 of 244 true rows on the F3 pages, ocr_vs_rebuild_2026-11-21.md).
  table_check  the table check (table_check.misread_tables, 23/11) finds the page's tables misread: printed rows not held exactly AND a defect of the Markdown
           tables (two amounts in a cell...). 39 of 40 flagged pages really misread; Chandra fixed 29 of a 40-page pilot (true rows 51.5 % -> 98.0 % on them),
           9 of 10 checked by hand better (rule_reread_flagged.txt). Its OCR text is taken only when it has FEWER wrong rows (and not fewer figures).

`rescue_pages` sends every bad page (no cap, owner 22/11) to an OCR reader once, and takes what comes back for a page only when it is not empty and has at least as many
figures as the text it replaces; the page is marked "ocr": True (the chunker turns that into the chunk flag "ocr", and the answer is told those excerpts came from OCR). A reader that
fails leaves Docling's pages: the fallback is an extra and never fails an ingestion. `READERS` maps a backend name (settings.OCR_BACKEND) to an async reader
`(pdf_path, page_numbers) -> {page_number: markdown}`: "chandra" (api_readers.read_chandra, Datalab) since 22/11.
"""
import asyncio
import re
from collections import Counter
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF

from app.core.config import settings
from app.core.logging import logger
from app.modules.ingestion.api_readers import read_chandra
from app.modules.ingestion.page_confidence import reread_reason
from app.modules.ingestion.postprocess.constants import NAV_HEADER_MIN_PAGES
from app.modules.ingestion.postprocess.table_rebuild import lost_regions
from app.modules.ingestion.table_check import FLAG_MIN_SHARE, FLAG_MIN_WRONG, table_defects, wrong_rows, wrong_rows_pair

# Broad re-read reasons (owner-approved plan 24/11: "re-read broadly, tell users strictly"; rule_d1_reread_v2.txt, 40 pages, 17 accepted, 10 of 10 checked by
# hand better, labelled rows right 336 -> 384 of 386 on them). Used only to choose pages to read again, never for the user's list (parse_check.py):
#   rows    labelled printed rows not held exactly >= FLAG_MIN_WRONG and >= FLAG_MIN_SHARE, without a defect of the Markdown tables
#   defect  a defect of the Markdown tables and >= 1 printed row (rows that start with a number included) not held exactly
#   rows1   >= 1 labelled printed row not held exactly, below "rows" and "defect" (plan 25/11 night step 2 = B7 part 3, TRIED NP-51 / NP-52)
TABLE_REASONS = ("table_check", "rows", "defect", "rows1")  # a reply is taken only with fewer wrong rows
# A reply holding FOREIGN_MAX or more figures (3+ digits) that the page's text layer does not print is refused: the reader estimated chart values
# (Lockheed 2022 p26, FinStats p48: 19 to 73 such figures). Measured 24/11 (rule_chandra_modes.txt): 0 of the good replies on 40 table pages refused.
FOREIGN_MAX = 2
# With picture captions off (api_readers), the reader still describes a chart now and then ("A line chart showing ...", numbers read off the axes).
# A reply holding such words that the page does not print is refused on a page with a text layer ("chart_text"); a scan has nothing to compare with,
# so its reply is taken (it was listed for the user until 25/11: right on 0 of 1 page, TRIED NP-59). Measured 24/11 (rule_caption_marker_v2.txt): 6 of 6
# chart pages with a description caught, 0 of 16 good replies refused. Words of estimates ("approximately") are NOT used: the notes of scanned statements
# print them (4 of 40 scans flagged, rule_caption_marker.txt).
CHART_TEXT = re.compile(r"\b(a|an|the)\s+(line|bar|donut|doughnut|pie|stacked|column|area|scatter|waterfall|combo)[ -]?(chart|graph)\b|\b(line|bar|pie|donut) chart:|"
                        r"\bchart (showing|shows|depicting|displaying)\b|\binfographic\b", re.I)

IMAGE_MARK = "<!-- image -->"  # Docling's picture marker: not text
MIN_LAYER_CHARS = 20
SCAN_IMAGE_SHARE = 0.5
MIN_GARBLED = 3
MIN_LAYER_NUMBERS = 10
NUMBER_RECALL = 0.5
GARBLED = re.compile(r"\(cid:\d+\)|�")
NUMBER = re.compile(r"\d[\d,.]*\d|\d")

OcrReader = Callable[[Path, List[int]], Awaitable[Dict[int, str]]]
READERS: Dict[str, OcrReader] = {"chandra": read_chandra}


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


def _scanned(pdf_page) -> bool:
    return len(re.sub(r"\s", "", pdf_page.get_text())) < MIN_LAYER_CHARS and _image_share(pdf_page) >= SCAN_IMAGE_SHARE


def scanned_pages(pdf_path: Path) -> List[int]:
    """The scanned pages, known from the PDF alone (no Docling text needed): they can be read while Docling runs."""
    with fitz.open(str(pdf_path)) as doc:
        return [n for n, pdf_page in enumerate(doc, 1) if _scanned(pdf_page)]


def text_signals(pdf_page, text: str, broad: bool = False) -> List[str]:
    """Every signal of page_confidence.SIGNALS that `text` raises against its PDF page, in the order of the re-read reasons (the first one sure enough names
    the reason): "garbled"; a scan, "scanned_unread" (still no text) or "scanned_read"; "missing"; "lost_table"; "table_check"; and with `broad` one of
    "rows", "defect" or "rows1" (>= 1 labelled printed row not held exactly, below the other two)."""
    if garbled(text):
        return ["garbled"]
    layer = pdf_page.get_text()
    if len(re.sub(r"\s", "", layer)) < MIN_LAYER_CHARS:
        if _image_share(pdf_page) < SCAN_IMAGE_SHARE:
            return []
        return ["scanned_unread" if len(re.sub(r"\s", "", text.replace(IMAGE_MARK, ""))) < MIN_LAYER_CHARS else "scanned_read"]
    out = []
    wanted = _numbers(layer)
    if len(wanted) >= MIN_LAYER_NUMBERS and len(wanted & _numbers(text)) / len(wanted) < NUMBER_RECALL:
        out.append("missing")
    if lost_regions(text, pdf_page.get_text("words")):
        out.append("lost_table")
    has_table = "|" in text
    if not (has_table or broad):
        return out
    total, wrong = wrong_rows(pdf_page, text)
    many = bool(total) and wrong >= FLAG_MIN_WRONG and wrong / total >= FLAG_MIN_SHARE
    defects = has_table and table_defects(text) > 0
    if many and defects:  # table_check.misread_tables
        out.append("table_check")
    elif broad:
        if many:
            out.append("rows")
        elif defects and wrong_rows(pdf_page, text, labelled=False)[1] >= 1:
            out.append("defect")
        elif wrong >= 1:
            out.append("rows1")
    return out


def bad_pages(pdf_path: Path, pages: Sequence[Dict[str, Any]], broad: bool = False) -> Dict[int, str]:
    """{page number: "garbled" | "scanned" | "missing" | "lost_table" | "table_check"} for the pages Docling's text (`pages`: [{"page_number", "text"}]) does not
    do justice to: page_confidence sends them to be read again (the first signal of text_signals with p >= REREAD_AT names the reason); `broad` adds "rows",
    "defect" and "rows1". A page number outside the PDF is ignored."""
    out: Dict[int, str] = {}
    with fitz.open(str(pdf_path)) as doc:
        for p in pages:
            n, text = p["page_number"], p.get("text") or ""
            if not 1 <= n <= len(doc):
                continue
            why = reread_reason(text_signals(doc[n - 1], text, broad))
            if why:
                out[n] = why
    return out


Early = Tuple[List[int], Dict[int, str]]  # (pages sent before Docling ended, what came back)


async def _read_early(pdf_path: Path, read: OcrReader) -> Early:
    pages = await asyncio.to_thread(scanned_pages, pdf_path)
    return pages, (await read(pdf_path, pages) if pages else {})


def start_early_ocr(pdf_path: Path) -> Optional["asyncio.Task[Early]"]:
    """Owner 22/11: the scanned pages go to the reader as soon as the file arrives, while Docling parses (a 44-page scan: about 45 s of reading no longer
    waits for the parse). None when the fallback is off or has no reader. The caller awaits the task through rescue_if_enabled(early=...)."""
    read = READERS.get(settings.OCR_BACKEND)
    if not settings.OCR_FALLBACK_ENABLED or read is None:
        return None
    return asyncio.ensure_future(_read_early(pdf_path, read))


def _fewer_wrong_rows(pdf_path: Path, texts: Dict[int, Tuple[str, str]], reasons: Optional[Dict[int, str]] = None) -> set:
    """The pages whose new text is cleaner than the old one: strictly fewer wrong rows under symmetrical OCR comparison, OR a defect-flagged page whose
    table defects fell without adding wrong rows (labelled or unlabelled)."""
    if not texts:
        return set()
    accepted = set()
    with fitz.open(str(pdf_path)) as doc:
        for n, (old, new) in texts.items():
            page = doc[n - 1]
            old_w, new_w = wrong_rows_pair(page, old, new)
            if new_w < old_w:
                accepted.add(n)
            elif reasons and reasons.get(n) in ("defect", "table_check") and new_w <= old_w:
                if table_defects(old) > 0 and table_defects(new) < table_defects(old):
                    old_u, new_u = wrong_rows_pair(page, old, new, labelled=False)
                    if new_u <= old_u:
                        accepted.add(n)
    return accepted


def _running_header_years(doc: "fitz.Document") -> set:
    """Four-digit years printed in running headers or footers repeated across NAV_HEADER_MIN_PAGES or more pages of `doc`."""
    edge_counts: Counter = Counter()
    for p in doc:
        lines = [ln.strip() for ln in p.get_text().splitlines() if ln.strip()]
        if not lines:
            continue
        for edge in set(lines[:2] + lines[-2:]):
            for yr in re.findall(r"\b(?:19|20)\d\d\b", edge):
                edge_counts[yr] += 1
    return {yr for yr, cnt in edge_counts.items() if cnt >= NAV_HEADER_MIN_PAGES}


def _enough_figures(pdf_path: Path, candidates: Dict[int, Tuple[str, str]], accepted_tables: set) -> set:
    """Pages whose replacement keeps at least as many figures as Docling. On text-layer pages, compare against numbers actually printed in the PDF layer
    (filtering carried headers / split glitches from Docling), and allow a dropped repeating running-header year when table defects were repaired."""
    if not candidates:
        return set()
    kept = set()
    header_years: Optional[set] = None
    with fitz.open(str(pdf_path)) as doc:
        for n, (old, new) in candidates.items():
            layer = doc[n - 1].get_text() if 1 <= n <= len(doc) else ""
            if len(re.sub(r"\s", "", layer)) < MIN_LAYER_CHARS:
                if len(_numbers(new)) >= len(_numbers(old)):
                    kept.add(n)
                continue
            layer_nums = _numbers(layer)
            old_hits = _numbers(old) & layer_nums
            new_hits = _numbers(new) & layer_nums
            if len(new_hits) >= len(old_hits):
                kept.add(n)
                continue
            dropped = old_hits - new_hits
            if (n in accepted_tables and table_defects(old) > 0 and table_defects(new) < table_defects(old)
                    and dropped and all(re.fullmatch(r"(?:19|20)\d\d", x) for x in dropped)):
                if header_years is None:
                    header_years = _running_header_years(doc)
                if dropped <= header_years:
                    kept.add(n)
    return kept


def _with_foreign_figures(pdf_path: Path, texts: Dict[int, str]) -> set:
    """The pages with a text layer whose new text holds FOREIGN_MAX or more figures the layer does not print ({page: new text})."""
    if not texts:
        return set()
    out = set()
    with fitz.open(str(pdf_path)) as doc:
        for n, new in texts.items():
            layer = doc[n - 1].get_text()
            foreign = {x for x in _numbers(new) - _numbers(layer) if not re.fullmatch(r"(19|20)\d\d", x)}  # a year in a header is not a figure
            if len(re.sub(r"\s", "", layer)) >= MIN_LAYER_CHARS and len(foreign) >= FOREIGN_MAX:
                out.add(n)
    return out


def _chart_text(pdf_path: Path, texts: Dict[int, str]) -> Dict[int, bool]:
    """{page: it has a text layer} of the pages whose new text describes a chart in words the page does not print ({page: new text})."""
    out: Dict[int, bool] = {}
    if not texts:
        return out
    with fitz.open(str(pdf_path)) as doc:
        for n, new in texts.items():
            layer = doc[n - 1].get_text()
            has_layer = len(re.sub(r"\s", "", layer)) >= MIN_LAYER_CHARS
            flat = " ".join(layer.split()).lower()
            if any(not has_layer or " ".join(m.group(0).split()).lower() not in flat for m in CHART_TEXT.finditer(new)):
                out[n] = has_layer
    return out


def _missing_pages(pdf_path: Path, pages: Sequence[Dict[str, Any]]) -> List[int]:
    """The pages of the PDF the parse did not return (0 of 23,176 measured, TRIED NP-18: a safety net)."""
    have = {p["page_number"] for p in pages}
    with fitz.open(str(pdf_path)) as doc:
        return [n for n in range(1, len(doc) + 1) if n not in have]


async def rescue_pages(pdf_path: Path, pages: List[Dict[str, Any]], read: OcrReader, early: Optional[Early] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """(pages with the OCR text of the rescued ones, report {"bad": {page: reason}, "early": [pages read during the parse], "sent": [pages sent after it],
    "replaced": [pages], "error"?: type name}). A page read early is not sent again, even when nothing came back for it (the reader already tried it).
    A page the parse did not return ("page_missing") is sent too and put back in its place when text comes back (owner 25/11: read again before telling)."""
    done, found = early or ([], {})
    bad = await asyncio.to_thread(bad_pages, pdf_path, pages, True)
    missing = set(await asyncio.to_thread(_missing_pages, pdf_path, pages))
    bad.update({n: "page_missing" for n in missing})
    sent = [n for n in sorted(bad) if n not in done]
    report: Dict[str, Any] = {"bad": bad, "early": list(done), "sent": sent, "replaced": []}
    if not bad:
        return pages, report
    read_pages = dict(found)
    if sent:
        try:
            read_pages.update(await read(pdf_path, sent))
        except Exception as exc:  # the fallback is an extra: Docling's pages (and what the early read gave) stand
            report["error"] = type(exc).__name__
            logger.warning(f"OCR fallback skipped for {pdf_path.name}: {type(exc).__name__}: {str(exc)[:160]}")
    checked = {n for n, why in bad.items() if why in TABLE_REASONS and (read_pages.get(n) or "").strip()}
    fewer = await asyncio.to_thread(_fewer_wrong_rows, pdf_path, {n: (p.get("text") or "", read_pages[n]) for p in pages if (n := p["page_number"]) in checked}, bad)
    replies = {n: read_pages[n] for n in bad if (read_pages.get(n) or "").strip()}
    foreign = await asyncio.to_thread(_with_foreign_figures, pdf_path, replies)
    chart = await asyncio.to_thread(_chart_text, pdf_path, replies)
    all_pages = sorted(pages + [{"page_number": n, "text": "", "pictures": []} for n in missing], key=lambda p: p["page_number"])
    orig_by_page = {p["page_number"]: p.get("text") or "" for p in pages}
    survivors: Dict[int, Tuple[str, str]] = {}
    rejected: Dict[int, str] = {}
    for p in all_pages:
        n = p["page_number"]
        text = (read_pages.get(n) or "").strip() if n in bad else ""
        if n in bad and not text:
            rejected[n] = "empty"
        elif n in foreign:  # figures the page does not print: the reader estimated them; the page keeps its text and stays on the user's list
            rejected[n] = "foreign_numbers"
        elif chart.get(n):  # a chart described in words the page does not print: the reader's own caption, refused like estimated figures
            rejected[n] = "chart_text"
        elif n in checked and n not in fewer:  # a misread table is swapped only for one with fewer wrong rows
            rejected[n] = "more_wrong_rows"
        elif text:
            survivors[n] = (orig_by_page.get(n, ""), text)
    enough = await asyncio.to_thread(_enough_figures, pdf_path, survivors, fewer)
    out: List[Dict[str, Any]] = []
    for p in all_pages:
        n = p["page_number"]
        if n in enough:  # a scan whose reply describes a chart: nothing to compare with, so taken
            out.append({**p, "text": survivors[n][1], "ocr": True})
            report["replaced"].append(n)
        else:
            if n in survivors:
                rejected[n] = "fewer_figures"
            if n not in missing:  # a page still missing stays out: parse_check lists it as unread
                out.append(p)
    if rejected:
        report["rejected"] = rejected
    return out, report


async def rescue_if_enabled(pdf_path: Path, pages: List[Dict[str, Any]], info: Optional[Dict[str, Any]] = None,
                            early: Optional["asyncio.Future[Early]"] = None) -> List[Dict[str, Any]]:
    """`pages` unchanged unless OCR_FALLBACK_ENABLED and OCR_BACKEND names a registered reader; `info` receives ocr_bad_pages, ocr_early_pages and
    ocr_replaced_pages (the pipeline's timings). `early`: the task of start_early_ocr; if it failed, its pages are read now like the others."""
    read = READERS.get(settings.OCR_BACKEND)
    if not settings.OCR_FALLBACK_ENABLED or read is None:
        return pages
    got: Optional[Early] = None
    if early is not None:
        try:
            got = await early
        except Exception as exc:
            logger.warning(f"Early OCR of {pdf_path.name} failed ({type(exc).__name__}): its pages are read after the parse")
    pages, report = await rescue_pages(pdf_path, pages, read, got)
    if info is not None:
        info.update({"ocr_bad_pages": len(report["bad"]), "ocr_early_pages": len(report["early"]), "ocr_replaced_pages": len(report["replaced"])})
        if report.get("rejected"):  # why re-read pages were refused, for the admin documents page (plan 24/11, channel D)
            info["ocr_rejected"] = dict(Counter(report["rejected"].values()))
    if report["bad"]:
        logger.info(f"OCR fallback on {pdf_path.name}: bad pages {report['bad']}, read during the parse {report['early']}, replaced {report['replaced']}")
    return pages
