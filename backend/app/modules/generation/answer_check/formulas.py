"""TC-4: is the formula of a written calculation the right one? The arithmetic check (calculations.py) only re-computes what the answer writes, so a
step whose division is right but whose formula is wrong passes it. Code only, no model; it reports only what it is sure of and leaves the rest alone.

Slice 1 (14/11): the base of a growth rate. A change between two periods is divided by the EARLIER period's value: "(10,000 − 8,000) ÷ 8,000",
or "10,000 ÷ 8,000 − 1". "(10,000 − 8,000) ÷ 10,000 = 20.0%" is right arithmetic on the wrong base (P0 case E03w). A step is judged only when
  - it has one of those two shapes, and its base is one of the two figures it compares
  - its line (or the line before it) speaks of growth or change, in English or Vietnamese
  - the period of both figures is known and they differ: the year of the excerpt table column that prints the figure (column_years.columns_of), a year
    written right next to it in an excerpt ("FY2014 8,000", "8,000 in 2014", "năm 2014: 8.000"), or the year the answer's own cited sentence gives it
    (column_years.claims); a figure with no year or with two years is unknown, and the step is left alone
So a margin of one year ("(revenue − cost) ÷ revenue") is never judged, and a decline written from the old value ("(10,000 − 8,000) ÷ 10,000" when
10,000 is the earlier year) passes.

Also (found 14/11 with the P0 cases E01 and E03): a written step whose printed result is wrong in every reading of the answer's numbers is reported as
"arithmetic". Since the rewrite was removed (calculations.py), such a result was only not accepted by rule B, and the number check could still accept the
figure through another derivation: "(10,000 − 8,000) ÷ 8,000 = 20.0%" passed as the 20 % decline from 10,000 to 8,000. The answer states a false
equation, so it goes to the one repair whatever else the figure matches. A step either side of which cannot be read is never reported.
"""
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Set

from app.modules.generation.answer_check.amounts import find_amounts
from app.modules.generation.answer_check.calculations import NUM, NUMTOK, SINGLE, evaluate, holds, is_calc, readings_of, steps, value_of
from app.modules.generation.answer_check.column_years import claims, columns_of
from app.modules.generation.answer_check.numbers import META, _readings

GROWTH = re.compile(rf"^\(*\s*({NUM})\s*[−–-]\s*({NUM})\s*\)*\s*[÷/]\s*({NUM})(?:\s*[×x*]\s*100)?\s*$")  # (a − b) ÷ base
RATIO_MINUS_ONE = re.compile(rf"^\(*\s*({NUM})\s*[÷/]\s*({NUM})\s*\)*\s*[−–-]\s*1\s*\)*(?:\s*[×x*]\s*100)?\s*$")  # a ÷ base − 1
CHANGE = re.compile(r"\b(?:growth|grow|grew|grown|growing|increase[sd]?|increasing|decrease[sd]?|decreasing|decline[sd]?|declining|change[sd]?|changing|yoy"
                    r"|year[- ]over[- ]year|rose|rise[sn]?|fell|fall[s]?|drop(?:ped|s)?|tăng trưởng|tăng|giảm|thay đổi|biến động)\b", re.I)
REACH = 24  # characters before or after a figure in an excerpt within which a year names its period
YEAR_BEFORE = re.compile(r"((?:19|20)\d{2})\s*[:=]?\s*\$?\s*$")  # "FY2014 8,000", "năm 2014: 8.000"
YEAR_AFTER = re.compile(r"^\s*(?:in|for|trong|năm)\s+(?:(?:fy|fiscal\s+year|fiscal|năm(?:\s+tài\s+chính)?)\s*)?((?:19|20)\d{2})(?!\d)", re.I)  # "8,000 in 2014"


def _is(amount, value: float) -> bool:
    return any(abs(reading - value) < 1e-9 for reading, _ in _readings(amount))


def _period(value: float, said: Sequence[Dict[str, Any]], chunks: Sequence[Dict[str, Any]]) -> Optional[int]:
    """The one year the figure belongs to, or None when no year or several years are found."""
    years: Set[int] = {c["year"] for c in said if _is(c["figure"], value)}
    for chunk in chunks:
        content = chunk.get("content", "")
        years |= {y for y, _ in columns_of(content, Decimal(str(value))) or []}
        text = "\n".join(line for line in content.splitlines() if not line.strip().startswith("|"))
        for a in find_amounts(text):
            if a.is_year or a.value is None or not _is(a, value):
                continue
            for m in (YEAR_BEFORE.search(text[max(0, a.start - REACH):a.start]), YEAR_AFTER.match(text[a.end:a.end + REACH + 10])):
                if m:
                    years.add(int(m.group(1)))
    return next(iter(years)) if len(years) == 1 else None


def _shape(left: str):
    """(first figure, second figure, base) as printed, when the step is a change between two figures; else None."""
    m = GROWTH.match(left)
    if m:
        return tuple(NUMTOK.search(g).group(0) for g in m.groups())
    m = RATIO_MINUS_ONE.match(left)
    if m:
        a, b = (NUMTOK.search(g).group(0) for g in m.groups())
        return a, b, b
    return None


HUNDRED = re.compile(r"(?:[×x]|(?<!\*)\*(?!\*))\s*100\b")


def _show(value: float, left: str, right: str) -> str:
    """What a written calculation really gives, written like its printed result (a percent when the result is one and the left is a ratio)."""
    if right.replace("**", "").rstrip("…").rstrip(") ").endswith("%") and "%" not in left and not HUNDRED.search(left):
        return f"{value * 100:,.1f}%"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _wrong_result(left: str, right: str, readings) -> Optional[str]:
    """What the step really gives when its printed result is wrong in every reading of the answer's numbers; None when it is right in one, or when
    either side cannot be read (never reported), or when it is not a calculation with a single printed result."""
    if not is_calc(left) or not SINGLE.fullmatch(right):
        return None
    shown = None
    for locale in readings:
        a, b = evaluate(left, locale), evaluate(right, locale)
        if a is None or b is None or holds(left, right, locale):
            return None
        shown = shown or _show(a[0], left, right)
    return shown


def _context(body: str, at: int) -> str:
    """The step's line and the line before it."""
    start = body.rfind("\n", 0, at) + 1
    end = body.find("\n", at)
    before = body.rfind("\n", 0, max(0, start - 1)) + 1
    return body[before:end if end >= 0 else len(body)]


def check_formulas(answer: str, chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[{"kind": "arithmetic" | "growth_base", "step", "problem"}]: written steps whose printed result is wrong, and growth rates divided by the later
    period's value."""
    body = answer.split(META)[0]
    said = claims(body)
    out: List[Dict[str, Any]] = []
    readings = readings_of(body)
    for left, right, at in steps(body):
        wrong = _wrong_result(left, right, readings)
        if wrong:
            out.append({"kind": "arithmetic", "step": f"{left} = {right}",
                        "problem": f'the written calculation "{left} = {right}" is wrong: {left} gives {wrong}, not {right}: correct the result and every place it is used'})
            continue
        shape = _shape(left)
        if not shape or not CHANGE.search(_context(body, at)):
            continue
        for locale in readings:
            x, y, base = (abs(value_of(t, locale)) for t in shape)
            if base not in (x, y):
                continue
            px, py = _period(x, said, chunks), _period(y, said, chunks)
            if px is None or py is None or px == py:
                continue
            (early, early_year), (late, late_year) = sorted([(shape[0], px), (shape[1], py)], key=lambda f: f[1])
            if abs(base - abs(value_of(late, locale))) < 1e-9:
                out.append({"kind": "growth_base", "step": f"{left} = {right}",
                            "problem": f'the growth rate "{left} = {right}" divides by {late} ({late_year}), the later period\'s value; a growth rate is divided '
                                       f"by the earlier period's value, {early} ({early_year}): correct the result"})
            break
    return out
