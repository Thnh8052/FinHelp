"""Is a table of this page misread? (owner 23/11: report a parse problem instead of staying silent; rule experiments/scripts/parsing_metric/
rule_page_flag_v2.txt). No model. A page is flagged only when two independent signals agree:
  1. rows: the printed table rows of the PDF text layer that start with a label (a line cut into cells by the horizontal gaps between words, >= 2 value
     cells, not a line of years) are not held exactly by one Markdown row of the page: at least FLAG_MIN_WRONG of them and FLAG_MIN_SHARE of all.
     Same reading as the parsing report's metric (experiments/scripts/parsing_metric/row_metric_v2.py v2.2, copied here), plus a dash minus ("–3.5")
     read as "-" on the PDF side;
  2. defect: the page's Markdown tables show a fault of their own: a value cell with two amounts ("24,222 -4"), an amount followed by a full-size digit
     ("53.5 1"), or a table whose rows lost their labels (copy of experiments remaining_errors.table_kinds; its "header_years" and "space_thousands"
     kinds are known false alarms and not used).
Measured 23/11 (160 report documents + the owner's 10 PDFs): 69 pages flagged, 39 of a fresh sample of 40 really misread (97.5 %); signal 1 alone was
right on about 55 %. It misses a lot: 7 of 21 misread pages that signal 1 found are kept; lost tables and lost chart numbers are page_quality's checks,
and rows that start with a number (the Fed Z.1 line numbers) are not judged.
"""
import re

import fitz  # PyMuPDF

from app.modules.ingestion.postprocess.constants import PHRASE_GAP, SUPERSCRIPT_GAP, SUPERSCRIPT_RAISE, SUPERSCRIPT_RATIO, VALUE_GAP_TOLERANCE
from app.modules.ingestion.postprocess.evidence import split_glued_marks
from app.modules.ingestion.postprocess.tokens import is_marker, is_placeholder

FLAG_MIN_WRONG, FLAG_MIN_SHARE = 2, 0.15

# ---------------------------------------------------------------- signal 1: printed rows (copy of row_metric_v2 v2.2)
NUM = re.compile(r"^[(\-]?\$?[(\-]?\d[\d,]*(\.\d+)?\)?%?\)?$")
SUPERSCRIPT_TAIL = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹][⁰¹²³⁴⁵⁶⁷⁸⁹,]*$")
DIGIT_MARK = re.compile(r"\d{1,2}(?:,\d{1,2})*")
PLACEHOLDERS = {"NM", "NA", "N/A", "N/M", "NMF"}
CURRENCY = {"$", "€", "£", "¥"}
SYMBOLS = {"%", "(", ")", "-", "—", "–", "−"} | CURRENCY
YEAR = re.compile(r"(19[5-9]\d|20[0-4]\d)")
MARK = re.compile(r"\(\d{1,2}\)%?")  # "(1)%" reads like "(1) %" (a printed "(1) %" and an OCR "(1)%" are the same value, TRIED NP-63)
DASH = str.maketrans({"–": "-", "−": "-"})


def number(token: str):
    token = SUPERSCRIPT_TAIL.sub("", token)
    norm = re.sub(r"[^\d.]", "", token).strip(".")
    return norm if NUM.match(token) and norm else None


def is_text(token: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}", token)) and not is_marker(token) and token.strip("()*,.;:").upper() not in PLACEHOLDERS


def _unit(tokens):
    if any(is_text(t) for t in tokens):
        return "text", None
    nums = [(number(t), t) for t in tokens if number(t)]
    if not nums:
        return None, None
    return "value", (tuple(n for n, _ in nums), all(MARK.fullmatch(t) for _, t in nums))


def phrases_of(words):
    """One printed line (PyMuPDF words) -> [(tokens, gap before)] left to right; a currency sign after a number starts a new phrase."""
    phrases, prev = [], None
    for w in sorted(words, key=lambda w: w[0]):
        token = w[4]
        gap = float("inf") if prev is None else w[0] - prev[2]
        if prev is not None and not (token in CURRENCY and number(prev[4])):
            plain = number(token) is None and token not in SYMBOLS and number(prev[4]) is None and prev[4] not in SYMBOLS
            if gap <= VALUE_GAP_TOLERANCE or (gap <= PHRASE_GAP and plain):
                phrases[-1][0].append(token)
                prev = w
                continue
        phrases.append(([token], gap))
        prev = w
    return phrases


def _drop_marks(words):
    """A digit footnote mark printed small and raised right after a number or a placeholder is not a value (same proof as evidence.sits_on)."""
    def sits_on(w, host):
        centre = (w[1] + w[3]) / 2
        return (w[3] > w[1] and centre >= host[1] - 1.0 and w[3] - w[1] <= SUPERSCRIPT_RATIO * (host[3] - host[1])
                and (host[1] + host[3]) / 2 - centre >= SUPERSCRIPT_RAISE)
    return [w for w in words if not (DIGIT_MARK.fullmatch(w[4]) and any(
        h is not w and (number(h[4]) or is_placeholder(h[4])) and w[0] - SUPERSCRIPT_GAP <= h[2] <= w[0] + 1.0 and sits_on(w, h) for h in words))]


def _segments(phrases):
    """phrases -> [(value units, raw number tokens)] per segment; prose (a segment touching a label at a word gap) is left out."""
    segs, cur, prose, prev = [], [], False, None
    for tokens, gap in phrases:
        kind, val = _unit(tokens)
        close = gap <= PHRASE_GAP
        if kind == "text":
            if cur:
                segs.append((cur, prose or (close and prev == "value")))
                cur = []
            prev = "text"
        elif kind == "value":
            nums, marks = val
            raw = [t for t in tokens if number(t)]
            if not cur:
                prose = close and prev == "text"
            if cur and marks:
                cur[-1][0] += nums
                cur[-1][2] += raw
            else:
                cur.append([list(nums), marks, raw])
            prev = "value"
        elif not close:
            prev = None
    if cur:
        segs.append((cur, prose))
    out = []
    for seg, is_prose in segs:
        if is_prose:
            continue
        j = 0
        while j < len(seg) - 1 and seg[j][1]:
            j += 1
        out.append(([tuple(u[0]) for u in seg[j:]], [t for u in seg[j:] for t in u[2]]))
    return out


def _page_lines(words):
    words = sorted(words, key=lambda w: (w[1] + w[3]) / 2)
    lines, cur, last = [], [], None
    for w in words:
        cy = (w[1] + w[3]) / 2
        if last is not None and cy - last > 0.5 * (w[3] - w[1]):
            lines.append(cur)
            cur = []
        cur.append(w)
        last = cy if not cur[:-1] else (last + cy) / 2
    if cur:
        lines.append(cur)
    return lines


def printed_rows(page: "fitz.Page", labelled: bool = True) -> list:
    """The table rows of a PDF page: [value units] per row segment. `labelled`: only rows that start with a label (the table check); False also keeps
    rows that start with a number (the Fed Z.1 line numbers; the re-read reason "defect", page_quality.py)."""
    rows = []
    for line in _page_lines(split_glued_marks(page, page.get_text("words"))):
        line = [(*w[:4], w[4][0].translate(DASH) + w[4][1:] if w[4][1:2].isdigit() else w[4], *w[5:]) for w in line]
        phrases = phrases_of(_drop_marks(line))
        if not phrases or (labelled and _unit(phrases[0][0])[0] != "text"):
            continue
        for units, raw in _segments(phrases):
            units = _undated(units, raw)
            if len(units) >= 2 and not all(YEAR.fullmatch(t.strip("(),.;:$")) or YEAR_TAIL.fullmatch(t) for t in raw):
                rows.append(units)
    return rows


# Plan B7 (25/11, experiments rule_b7_rows.txt): two general sources of false "wrong rows" seen on the audit pages that no list shows (U1).
# A day, a comma and a year ("31, 2022") printed where values stand is a date: a column header "December 31, 2022" or justified prose
# ("On November 21, 2024, ..."), not two values. "2021 -22" of a maturity header is a range of years, like a year.
DAY_COMMA = re.compile(r"^\(?(\d{1,2}),$")
YEAR_TAIL = re.compile(r"^[-–]\d{2}$")


def _undated(units: list, raw: list) -> list:
    dates = set()
    for a, b in zip(raw, raw[1:]):
        day = DAY_COMMA.match(a)
        if day and 1 <= int(day.group(1)) <= 31 and YEAR.fullmatch(b.strip("(),.;:$")):
            dates |= {day.group(1), b.strip("(),.;:$")}
    return [u for u in units if not set(u) <= dates] if dates else units


def _md_rows(text: str) -> list:
    return [[c.strip() for c in line.strip().strip("|").split("|")] for line in text.splitlines()
            if line.startswith("|") and not re.fullmatch(r"[|\-:\s]+", line)]


def wrong_rows(page: "fitz.Page", text: str, labelled: bool = True):
    """(printed rows (labelled ones by default), how many of them no Markdown row of `text` holds exactly)."""
    truth = printed_rows(page, labelled)
    held = {tuple(units) for r in _md_rows(text)
            for units, _ in _segments([(c.replace("\n", " ").split(), float("inf")) for c in r]) if units}
    return len(truth), sum(1 for t in truth if tuple(t) not in held)


# ---------------------------------------------------------------- signal 2: defects of the Markdown tables (copy of remaining_errors.table_kinds)
AMOUNT = r"\$?\s?\(?-?\d(?:[\d,]*\d)?(?:\.\d+)?\)?\s?%?"
MERGED = re.compile(rf"^{AMOUNT}\s+(\d|\d(?:,\d)+|\([a-z]\)(?:\([a-z]\))*)$")
TWO = re.compile(rf"^{AMOUNT}\s+{AMOUNT}$")
SPACE_THOUSANDS = re.compile(r"^\(?\d{1,3}(?: \d{3})+\)?$")
YEAR_WORD = re.compile(r"\b(19|20)\d{2}\b")


def table_defects(text: str) -> int:
    """Value cells with two amounts or an amount + a full-size digit, and tables whose rows lost their labels."""
    lines, k, found = text.split("\n"), 0, 0
    while k < len(lines):
        if not lines[k].startswith("|"):
            k += 1
            continue
        top, block = k, []
        while k < len(lines) and lines[k].startswith("|"):
            block.append(lines[k])
            k += 1
        rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in block if not re.fullmatch(r"[|\-:\s]+", ln)]
        if len(rows) < 2:
            continue
        body = rows[1:]
        for r in body:
            for c in r[1:]:
                merged = MERGED.match(c)
                if merged and not YEAR_WORD.fullmatch(c.split()[-1]):
                    found += merged.group(1)[0].isdigit()
                elif not SPACE_THOUSANDS.match(c) and TWO.match(c) and not re.search(r"\(\d{1,2}\)$", c):
                    found += 1
        num_first = [r for r in body if r[0] and re.search(r"\d", r[0]) and not re.search(r"[A-Za-z]{2}", r[0])]
        if len(body) >= 4 and len(num_first) >= 0.8 * len(body):
            before = [ln for ln in lines[max(0, top - 80):top] if ln.strip() and not ln.startswith("|")]
            if len([ln for ln in before if len(ln.split()) <= 6 and not re.search(r"\d{3}", ln)]) >= 4:
                found += 1
    return found


def misread_tables(page: "fitz.Page", text: str) -> bool:
    total, wrong = wrong_rows(page, text)
    return bool(total) and wrong >= FLAG_MIN_WRONG and wrong / total >= FLAG_MIN_SHARE and table_defects(text) > 0
