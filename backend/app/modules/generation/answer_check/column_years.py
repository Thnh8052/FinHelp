"""TC-1: the year an answer gives a figure must be the year of the table column the figure is printed in. Code only, no model.

Why it is needed: the number check only asks "is this figure printed in some excerpt", and the citation check compares a year with the years the whole
report covers (a FY2019 report covers 2017-2019, so no year of it is ever "wrong"). A figure read from the FY2017 column and stated for FY2019 passes both.

For each figure a sentence (or an answer table cell) states for a year, and cites to excerpt [n]:
  - the year is the one the sentence ties to the figure ("... 16.7 % in FY2019 ...", or the only year of a sentence that compares nothing);
    a year inside a date ("ended December 31, 2017") is not a year given to a figure; when the tie is not clear, nothing is checked
  - the figure is looked for in the cells of the Markdown tables of excerpt [n]; its column's header year is read (the header may sit one row down,
    under a title row); a header cell that is a date ("January 28, 2023") also accepts the fiscal year before it (a year that ends in January 2023 is fiscal 2022)
  - reported only when the figure is printed ONLY in tables, ONLY in columns whose year is known, and none of them is the year the answer gave
Anything the check cannot read is left alone: a figure that no table prints (derived, or in the text), a figure that is also in the excerpt's text, a table
whose header does not line up with its rows, a column with no single year. The aim is no false alarm: it only reports what the excerpt itself contradicts.
"""
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.modules.generation.answer_check.amounts import Amount, find_amounts
from app.modules.generation.answer_check.citations import CITE, SENTENCE

YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")  # also inside "FY2018"
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATE = re.compile(rf"\b{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+((?:19|20)\d{{2}})\b", re.I)  # "December 31, 2017": its year is a date, not a fiscal year
MONTH_NAME = re.compile(rf"\b{MONTH}", re.I)
DAY = re.compile(rf"\b{MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", re.I)  # "January 28": the 28 is a day, not a figure
BIG_SCALE = re.compile(r"\s*(?:billion|bn|trillion)\b", re.I)  # "$1.2 billion" says nothing about a table cell printed "1.2": the units differ
YEAR_LIST = re.compile(r"(?:19|20)\d{2}(?:\s*(?:/|,|&|-|–|and|to|vs\.?)\s*(?:19|20)\d{2})+", re.I)  # "for 2019/2018/2017": years in the order of a list of figures
SMALL = 12  # plain integers up to this are counts or list markers, as in numbers.py
TIES = re.compile(r"\b(?:in|for|of|during|at|fy|fiscal|year)\s*(?:fiscal\s*|fy\s*|year\s*)*$", re.I)  # what may stand between a figure and "its" year
COMPARES = re.compile(r"\b(?:compared|versus|vs|prior|previous|previously|earlier|before|from|than|last year|year-ago|year ago|down|up)\b", re.I)
TIE_REACH = 45  # characters between a figure and the year that follows it


def _figures(segment: str) -> List[Amount]:
    days = [m.span(1) for m in DAY.finditer(segment)]
    out = []
    for a in find_amounts(segment, space_groups=True):
        if a.is_year or a.is_reference or a.value is None or (a.is_plain_integer and abs(a.value) <= SMALL):
            continue
        if any(s <= a.start < e for s, e in days) or BIG_SCALE.match(segment, a.end):
            continue
        if not a.is_percent and abs(a.value) < 10:  # "1.2", "5.5": too small to tell from some other cell of a table
            continue
        if segment[a.start - 1:a.start] == "[" and segment[a.end:a.end + 1] == "]":
            continue  # a citation marker
        out.append(a)
    return out


def _years(segment: str) -> List[Tuple[int, int]]:
    """[(position, year)] of the years the sentence writes, without the years of dates."""
    dates = [m.span(1) for m in DATE.finditer(segment)]
    return [(m.start(), int(m.group())) for m in YEAR.finditer(segment) if not any(s <= m.start() < e for s, e in dates)]


def _year_of(figure: Amount, others: Sequence[Amount], years: Sequence[Tuple[int, int]], segment: str) -> Optional[int]:
    """The year the sentence gives to `figure`, or None when it does not clearly give one."""
    between = lambda lo, hi: any(g is not figure and g.start >= lo and g.end <= hi for g in others)
    for pos, year in years:  # "... 16.7 % in FY2019": the year that follows the figure, introduced by in / for / of, with no other figure between
        gap = segment[figure.end:pos]
        if pos >= figure.end and len(gap) <= TIE_REACH and TIES.search(gap) and not between(figure.end, pos):
            return None if any(m.start() <= pos < m.end() for m in YEAR_LIST.finditer(segment)) else year  # a list of years for a list of figures: which is which is not said
    distinct = {int(y) for y in YEAR.findall(segment)}  # every year written, also those of dates: "FY2018 ... November 30, 2018 and ... December 1, 2017" has two
    if len(distinct) == 1 and not COMPARES.search(segment):  # one year in a sentence that compares nothing: every figure of it is that year's
        return next(iter(distinct))
    return None


def claims(answer: str) -> List[Dict[str, Any]]:
    """[{"n", "year", "figure": Amount, "sentence"}]: every figure the answer gives to a year, with the excerpt it cites."""
    out: List[Dict[str, Any]] = []
    header: List[Optional[int]] = []  # years of the answer's own table header, by column
    for line in answer.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            if _is_header(cells):
                header = [_single_year(c) for c in cells]
                continue
            row_cites = {int(x) for m in CITE.finditer(line) for x in re.split(r"\s*[,;]\s*", m.group(1))}
            for j, cell in enumerate(cells[1:], 1):
                year = header[j] if j < len(header) and len(header) == len(cells) else None
                cites = {int(x) for m in CITE.finditer(cell) for x in re.split(r"\s*[,;]\s*", m.group(1))} or (row_cites if len(row_cites) == 1 else set())
                if year is None or not cites:
                    continue
                for f in _figures(CITE.sub(" ", cell)):
                    out += [{"n": n, "year": year, "figure": f, "sentence": line.strip()[:160]} for n in cites]
            continue
        header = []
        for sentence in SENTENCE.split(line):
            start = 0
            for m in CITE.finditer(sentence):  # as check_citations: each [n] is checked against the text it closes
                segment = sentence[start:m.start()]
                start = m.end()
                if not segment.strip():
                    continue
                figures, years = _figures(segment), _years(segment)
                for f in figures:
                    year = _year_of(f, figures, years, segment)
                    if year is not None:
                        out += [{"n": int(x), "year": year, "figure": f, "sentence": segment.strip()[:160]} for x in re.split(r"\s*[,;]\s*", m.group(1))]
    return out


def _single_year(cell: str) -> Optional[int]:
    found = {int(y) for y in YEAR.findall(cell)}
    return next(iter(found)) if len(found) == 1 else None


def _is_header(cells: Sequence[str]) -> bool:
    """A row of years (and empty cells) after a label cell: no figure but the years."""
    body = cells[1:]
    return any(YEAR.search(c) for c in body) and all(not c or YEAR.search(c) or not re.search(r"\d", c) for c in body)


# ---------------------------------------------------------------- the excerpt's tables
Column = Optional[Tuple[int, bool]]  # (the column's year, whether its header is a date): None when the column has no single year


def _tables(content: str) -> List[Tuple[List[Column], List[List[str]]]]:
    """[(year of each column, data rows as cells)] of every Markdown table whose header (one of its first three rows) holds years."""
    out, rows = [], []
    for line in content.splitlines() + [""]:
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                rows.append(cells)
            continue
        if rows:
            at = next((k for k, cells in enumerate(rows[:3]) if _is_header(cells)), None)
            if at is not None:
                head = [None if (y := _single_year(c)) is None else (y, bool(MONTH_NAME.search(c))) for c in rows[at]]
                out.append((head, rows[at + 1:]))
        rows = []
    return out


def _text_lines(content: str) -> str:
    return "\n".join(line for line in content.splitlines() if not line.strip().startswith("|"))


def _prints(text: str, value: Decimal) -> bool:
    return any(a.value is not None and abs(a.value) == value for a in find_amounts(text, space_groups=True)) or \
        any(a.value is not None and abs(a.value) == value for a in find_amounts(text))


def columns_of(content: str, value: Decimal) -> Optional[List[Tuple[int, bool]]]:
    """The (year, date-header) of every column that prints `value`, or None when this cannot be told: the figure is in no table, is also in the
    text, or sits in a column whose year is unknown or whose table does not line up with its header."""
    if _prints(_text_lines(content), value):
        return None
    found: List[Tuple[int, bool]] = []
    for head, rows in _tables(content):
        for cells in rows:
            for j, cell in enumerate(cells[1:], 1):
                if not _prints(cell, value):
                    continue
                if len(head) != len(cells) or head[j] is None:
                    return None
                found.append(head[j])  # type: ignore[arg-type]
    return found or None


def check_columns(answer: str, chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[{"n", "year", "figure", "columns": [years], "problem"}] for the figures printed only under other years than the one the answer gave."""
    text = answer.split("<answer_meta>")[0]
    out: List[Dict[str, Any]] = []
    seen = set()
    for c in claims(text):
        n, year, figure = c["n"], c["year"], c["figure"]
        if not 1 <= n <= len(chunks) or (n, year, figure.raw) in seen:
            continue
        seen.add((n, year, figure.raw))
        printed = columns_of(chunks[n - 1].get("content", ""), abs(figure.value))  # type: ignore[arg-type]
        if not printed or any(y == year or (is_date and y == year + 1) for y, is_date in printed):
            continue
        years = sorted({y for y, _ in printed})
        out.append({"n": n, "year": year, "figure": figure.raw, "columns": years,
                    "problem": f"excerpt [{n}] prints {figure.raw} only in the {', '.join(map(str, years))} column of its table, not {year}: \"{c['sentence']}\""})
    return out
