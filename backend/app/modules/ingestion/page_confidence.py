"""Page confidence: one measure decides what happens to a page after the parse (plan 25/11 night; owner: "set up a confidence metric to decide the flow").

Each signal a page check can raise (page_quality.text_signals, plus the picture flags of figures.py and parse_check) carries p: the share of the pages it
fires on that were really misread, as measured (source in the table). A page is as likely wrong as its strongest signal, p_wrong = max(p); the signals
overlap (a "table_check" page also has wrong rows), so their shares are not multiplied.
  p_wrong >= REREAD_AT   the page is read again (page_quality.rescue_pages: the OCR reader; the picture readers of figures.py), behind the acceptance gates
  p_wrong >= REPORT_AT   on the final text, the page goes on the user's list (parse_check.check_pages: the document card's two messages, by `kind`)
  in between             read again if it can be, never shown to the user
REPORT_AT matches the owner's bar for the user's list (>= 85 % of listed pages really misread). Shares marked "to measure" hold today's behaviour (listed)
until the B8 v2 labels measure them (plan step 4).
"""
from typing import Dict, Iterable, Optional, Set, Tuple

REREAD_AT = 0.10
REPORT_AT = 0.85

# name: (p = share of pages really misread when it fires, kind = list of the document card, source)
SIGNALS: Dict[str, Tuple[float, str, str]] = {
    "garbled": (1.0, "tables", "definition: 3+ broken glyphs, the font was not decoded (0 pages in 170 documents)"),
    "scanned_unread": (1.0, "unread", "definition: a scan (no text layer, mostly picture) still without text"),
    "scanned_read": (0.5, "tables", "a scan the OCR step read: read again when Docling's text is not empty, never listed (today's behaviour)"),
    "page_missing": (1.0, "unread", "definition: a page the parse did not return (0 of 23,176 measured, NP-18)"),
    "missing": (0.9, "tables", "NP-16: 4/4; to measure (plan step 4)"),
    "lost_table": (0.9, "tables", "to measure (plan step 4); NP-55: 0/2 (SEC consent pages)"),
    "table_check": (0.975, "tables", "NP-12: 39/40"),
    "rows": (0.45, "tables", "NP-11: about 55 %; NP-20"),
    "defect": (0.90, "tables", "NP-24: 36/40"),
    "rows1": (0.15, "tables", "NP-51: 11-22 %; read again since plan step 2 (B7 part 3, NP-52: 16/40 re-reads taken, about 12 better, 0 worse)"),
    "ocr_unsure": (0.9, "tables", "to measure (plan step 4): a scan re-read with chart text the reader wrote (NP-26)"),
    "chart_lost": (0.87, "figures", "NP-31: 26/30; NP-48: 29/30"),
    "figure_failed": (0.9, "figures", "to measure (plan step 4): a picture or an image region the vision model could not read"),
}
REASON = {"scanned_unread": "scanned", "scanned_read": "scanned"}  # the re-read reason page_quality reports (it picks the acceptance gate)


def p_wrong(signals: Iterable[str]) -> float:
    return max((SIGNALS[s][0] for s in signals), default=0.0)


def reread_reason(signals: Iterable[str]) -> Optional[str]:
    """The first signal (in page_quality's order) sure enough to read the page again, as the reason name; None: the page is kept."""
    for s in signals:
        if SIGNALS[s][0] >= REREAD_AT:
            return REASON.get(s, s)
    return None


def reported(signals: Iterable[str]) -> Set[str]:
    """The lists of the document card ("tables", "figures", "unread") the page goes on."""
    return {SIGNALS[s][1] for s in signals if SIGNALS[s][0] >= REPORT_AT}
