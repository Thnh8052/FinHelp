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
import html
import re

import fitz  # PyMuPDF

from app.modules.ingestion.postprocess.constants import (
    GLUED_MARK_GAP,
    PHRASE_GAP,
    SUPERSCRIPT_GAP,
    SUPERSCRIPT_RAISE,
    SUPERSCRIPT_RATIO,
    VALUE_GAP_TOLERANCE,
)
from app.modules.ingestion.postprocess.evidence import is_footnote_ref, split_glued_marks
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
SPACE_GROUP_NUM = re.compile(r"(?<!\d)(\d{1,3}(?:[ \u00a0\u2008\u2009\u202f]\d{3})+(?:\.\d+)?)(?!\d)")
THIN_SPACES = re.compile(r"[\u00a0\u2008\u2009\u202f]+")
MD_FOOTNOTE_LINK = re.compile(r"\[(\(\d{1,2}\))\]")


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


def _strip_trailing_currency(token: str) -> str:
    """PDF columns with tight '$ -' spacing often glue '$' to the end of the previous value (e.g. '$(4.9)$')."""
    if len(token) > 1 and token[-1] in CURRENCY and number(token[:-1]):
        return token[:-1]
    return token


def _norm_space_numbers(text: str) -> str:
    return SPACE_GROUP_NUM.sub(lambda m: re.sub(r"[ \u00a0\u2008\u2009\u202f]", "", m.group(1)), text)


def _segments(phrases, fair_marks: bool = False):
    """phrases -> [(value units, raw number tokens)] per segment; prose (a segment touching a label at a word gap) is left out."""
    segs, cur, prose, prev, col_break = [], [], False, None, False
    for tokens, gap in phrases:
        clean_tokens = [_strip_trailing_currency(t) for t in tokens]
        kind, val = _unit(clean_tokens)
        close = gap <= PHRASE_GAP
        if kind == "text":
            if cur:
                segs.append((cur, prose or (close and prev == "value")))
                cur = []
            prev, col_break = "text", False
        elif kind == "value":
            nums, marks = val
            raw = [t for t in clean_tokens if number(t)]
            if fair_marks:
                # A negative "(12)" across a column gap, after "$" / standalone symbol column, or alone in a pipe cell is an amount, never a footnote mark.
                is_md = gap == float("inf")
                standalone_cell = is_md and len(nums) == 1
                col_amount = not is_md and (col_break or gap > SUPERSCRIPT_GAP or clean_tokens[0] in CURRENCY)
                if standalone_cell or col_amount:
                    marks = False
            if not cur:
                prose = close and prev == "text"
            if cur and marks:
                cur[-1][0] += nums
                cur[-1][2] += raw
            else:
                cur.append([list(nums), marks, raw])
            prev, col_break = "value", False
        else:
            if gap > SUPERSCRIPT_GAP or any(t in CURRENCY for t in clean_tokens):
                col_break = True
            if not close:
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


def _rotated_words(page: "fitz.Page") -> list:
    """Words in visual reading coordinates, handling rotated landscape pages and glued superscript marks."""
    raw_words = page.get_text("words")
    if not page.rotation:
        return split_glued_marks(page, raw_words)
    m = page.rotation_matrix
    cuts = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for host, mark in zip(line["spans"], line["spans"][1:]):
                tail = mark["text"].strip()
                if (host["text"][-1:].isdigit() and tail[:1].isdigit() and is_footnote_ref(tail)
                        and mark["size"] <= SUPERSCRIPT_RATIO * host["size"]
                        and host["origin"][1] - mark["origin"][1] >= SUPERSCRIPT_RAISE
                        and mark["bbox"][0] - host["bbox"][2] < GLUED_MARK_GAP):
                    hb, mb = fitz.Rect(host["bbox"]) * m, fitz.Rect(mark["bbox"]) * m
                    cuts.append(((hb.x0, hb.y0, hb.x1, hb.y1), (mb.x0, mb.y0, mb.x1, mb.y1), tail))
    rw = [(*((fitz.Rect(w[:4]) * m)[:4]), w[4], *w[5:]) for w in raw_words]
    if not cuts:
        return rw
    out = []
    for word in rw:
        cut = next((c for c in cuts if word[0] < c[0][2] < word[2] and c[1][2] <= word[2] + 0.5
                    and word[4].endswith(c[2]) and len(word[4]) > len(c[2])
                    and c[0][1] < word[3] and c[0][3] > word[1]), None)
        if cut is None:
            out.append(word)
        else:
            (_, hy0, hx1, hy1), (mx0, my0, mx1, my1), tail = cut
            out += [(word[0], hy0, hx1, hy1, word[4][:-len(tail)], *word[5:]), (mx0, my0, mx1, my1, tail, *word[5:])]
    return out


def _merge_spaced_thousands(line: list) -> list:
    """Merge 3-digit grouped thousands (e.g. '1 000') printed left-to-right as separate PDF words within tight spacing."""
    ordered = sorted(line, key=lambda w: w[0])
    merged, k = [], 0
    while k < len(ordered):
        wk = ordered[k]
        if re.fullmatch(r"\(?\d{1,3}", wk[4]):
            acc, x1, j = wk[4], wk[2], k + 1
            while j < len(ordered) and -0.5 <= (ordered[j][0] - x1) <= VALUE_GAP_TOLERANCE:
                nxt = ordered[j][4]
                if re.fullmatch(r"\d{3}\)?", nxt):
                    acc += nxt
                    x1 = max(x1, ordered[j][2])
                    j += 1
                    if nxt.endswith(")"):
                        break
                elif re.fullmatch(r"\d{3}\.\d+\)?", nxt):
                    acc += nxt
                    x1 = max(x1, ordered[j][2])
                    j += 1
                    break
                else:
                    break
            if j > k + 1:
                merged.append((wk[0], wk[1], x1, max(x[3] for x in ordered[k:j]), acc, *wk[5:]))
                k = j
                continue
        merged.append(wk)
        k += 1
    return merged


def _printed_rows_with_marks(page: "fitz.Page", labelled: bool = True, fair_marks: bool = False):
    words = []
    for w in _rotated_words(page):
        t = _norm_space_numbers(w[4])
        if THIN_SPACES.search(t):
            t = THIN_SPACES.sub(" ", t).strip()
        words.append((*w[:4], t, *w[5:]))
    rows, had_dropped_marks = [], False
    for line in _page_lines(words):
        line = [(*w[:4], w[4][0].translate(DASH) + w[4][1:] if w[4][1:2].isdigit() else w[4], *w[5:]) for w in line]
        merged = _merge_spaced_thousands(line)
        kept = _drop_marks(merged)
        if len(kept) < len(merged):
            had_dropped_marks = True
        phrases = phrases_of(kept)
        if not phrases or (labelled and _unit(phrases[0][0])[0] != "text"):
            continue
        for units, raw in _segments(phrases, fair_marks=fair_marks):
            units = _undated(units, raw)
            if len(units) >= 2 and not all(YEAR.fullmatch(t.strip("(),.;:$")) or YEAR_TAIL.fullmatch(t) for t in raw):
                rows.append(units)
    return rows, had_dropped_marks


def printed_rows(page: "fitz.Page", labelled: bool = True) -> list:
    """The table rows of a PDF page: [value units] per row segment. `labelled`: only rows that start with a label (the table check); False also keeps
    rows that start with a number (the Fed Z.1 line numbers; the re-read reason "defect", page_quality.py)."""
    return _printed_rows_with_marks(page, labelled=labelled, fair_marks=False)[0]


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


def _norm_md_cell(cell: str) -> str:
    cleaned = html.unescape(MD_FOOTNOTE_LINK.sub(r"\1", _norm_space_numbers(cell)))
    return " ".join(_strip_trailing_currency(t) for t in cleaned.replace("\n", " ").split())


def _md_rows(text: str) -> list:
    return [[_norm_md_cell(c.strip()) for c in line.strip().strip("|").split("|")] for line in text.splitlines()
            if line.startswith("|") and not re.fullmatch(r"[|\-:\s]+", line)]


def _held_units(text: str, fair_marks: bool = False, allow_trailing_footnote: bool = False) -> set:
    held = set()
    for r in _md_rows(text):
        for units, _ in _segments([(c.split(), float("inf")) for c in r], fair_marks=fair_marks):
            if not units:
                continue
            held.add(tuple(units))
            if allow_trailing_footnote and len(units) >= 3 and len(units[-1]) == 1 and re.fullmatch(r"\d{1,3}", units[-1][0]):
                held.add(tuple(units[:-1]))
    return held


def wrong_rows(page: "fitz.Page", text: str, labelled: bool = True):
    """(printed rows (labelled ones by default), how many of them no Markdown row of `text` holds exactly)."""
    truth = printed_rows(page, labelled)
    held = _held_units(text, fair_marks=False, allow_trailing_footnote=False)
    return len(truth), sum(1 for t in truth if tuple(t) not in held)


def wrong_rows_pair(page: "fitz.Page", old_text: str, new_text: str, labelled: bool = True) -> tuple:
    """Symmetrical comparison of Docling (`old_text`) vs OCR (`new_text`) against PDF rows without penalizing standalone negative cells or separated footnote columns."""
    truth, had_dropped_marks = _printed_rows_with_marks(page, labelled=labelled, fair_marks=True)
    held_old = _held_units(old_text, fair_marks=True, allow_trailing_footnote=had_dropped_marks)
    held_new = _held_units(new_text, fair_marks=True, allow_trailing_footnote=had_dropped_marks)
    return sum(1 for t in truth if tuple(t) not in held_old), sum(1 for t in truth if tuple(t) not in held_new)


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
