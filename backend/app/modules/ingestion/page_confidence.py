"""Page confidence: one measure decides what happens to a page after the parse (plan 25/11 night; owner: "set up a confidence metric to decide the flow").

Each signal page_quality.text_signals can raise carries p: the share of the pages it fires on that were really misread, as measured (source in the table).
A page is as likely wrong as its strongest signal, p_wrong = max(p); the signals overlap (a "table_check" page also has wrong rows), so their shares are
not multiplied. Every signal sends its page to be read again first (owner 25/11: always try the re-read before telling the user):
  p_wrong >= REREAD_AT   the page is read again (page_quality.rescue_pages, the OCR reader), behind the acceptance gates
  p_wrong >= REPORT_AT   on the final text, the page goes on the user's list (parse_check.check_pages: the document card's messages, by `kind`)
  in between             read again, never shown to the user (the admin's log)
REPORT_AT is the owner's floor (25/11, plan "parsing gọn lại", TRIED NP-60): a signal right at least half the time is worth telling the user. Pictures are
not read by any model since 25/11: parse_check lists them by geometry, outside this table.
"""
from typing import Dict, Iterable, Optional, Set, Tuple

REREAD_AT = 0.10
REPORT_AT = 0.5

# name: (p = share of pages really misread when it fires, kind = list of the document card, source)
SIGNALS: Dict[str, Tuple[float, str, str]] = {
    "garbled": (1.0, "tables", "definition: 3+ broken glyphs, the font was not decoded (0 pages in 170 documents)"),
    "scanned_unread": (1.0, "unread", "definition: a scan (no text layer, mostly picture) still without text"),
    "scanned_read": (0.3, "tables", "policy: a scan the OCR step read; read again when Docling's text is not empty, never listed (no text layer to judge it by)"),
    "page_missing": (1.0, "unread", "definition: a page the parse did not return (0 of 23,176 measured, NP-18)"),
    "missing": (0.9, "tables", "NP-16: 4/4; NP-60: 1/1"),
    "lost_table": (0.25, "tables", "NP-55, NP-59: 0/2 (SEC consent pages)"),
    "table_check": (0.975, "tables", "NP-12: 39/40"),
    "rows": (0.33, "tables", "NP-60: 7/21 (NP-11: about 55 %)"),
    "defect": (0.9, "tables", "NP-24: 36/40; NP-60: 43/44"),
    "rows1": (0.27, "tables", "NP-60: 6/22 (NP-51: 11-22 %); read again since B7 part 3 (NP-52: 16/40 re-reads taken, about 12 better, 0 worse)"),
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
    """The lists of the document card ("tables", "unread") the page goes on."""
    return {SIGNALS[s][1] for s in signals if SIGNALS[s][0] >= REPORT_AT}
