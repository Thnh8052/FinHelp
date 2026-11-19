"""A4 number check: every figure an answer states must be printed in its excerpts (any scale: "$20.6 billion" for "20,604"
millions), or follow from two figures the answer itself states and that check (sum, difference, average, ratio, percent,
growth, a percent of an amount), or come out of a calculation the answer writes out whose numbers all check (rule B, plan v2 H1:
"1,185 + 0 + 454 + 33 = 1,672", "365 × 43,762.5 ÷ 374,133 = 42.69", with the standard constants 365, 360, 100, 52, 53). Code only, no
model. Derivations from any two excerpt numbers are not accepted: a table holds hundreds of numbers whose sums and ratios cover almost any
value (that version caught 18-20% of planted wrong figures); rule B searches nothing, it only evaluates what the answer writes.
A written calculation whose result is wrong is not rewritten by code (removed 14/11, see calculations.py): its result is simply not accepted, so the figure is
reported as unverified and goes to the one repair.

The report goes into the trace; verification.verify turns each unverified figure into a problem for the one rewrite, and what stays unverified is flagged under the answer.
"""
import re
from typing import Any, Dict, List, Sequence, Set, Tuple

import numpy as np

from app.modules.generation.answer_check.amounts import DAY, UNIT_WORD, Amount, find_amounts
from app.modules.generation.answer_check.calculations import CONSTANTS, NUMTOK, SINGLE, exact, is_calc, readings_of, steps, value_of, written_results

META = "<answer_meta>"  # generator v3 appends a machine block; only the text before it is the answer
SMALL = 12  # plain integers up to this are list markers, months, quarters or counts ("3 segments"): not checked; the day of a date is skipped by DAY
SCALES = (1.0, 1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9)  # "$20.6 billion" against "20,604" (millions)
PERCENT_SCALES = (1e-2, 1e2)  # "25%" against "0.25"
# a page, note or item number, an accounting standard and a short fiscal year are references, not figures: "(Note 21, page 113)", "page 68/92",
# "pages 108-109", "trang 113", "ASC 606", "FY22"
# (18/11: 19 figure findings of 923 stored answers, 16 of them on answers graded correct)
REFERENCE_BEFORE = re.compile(r"(?:\b(?:pages?|pp?\.|trang|notes?|items?|thuyết minh|mục|asc|asu|topic)\s*(?:\d+\s*(?:[-–/,&]|and|và|to|đến)\s*)*|\bFY\s*'?|\bQ)$", re.I)
YEAR_PERCENT = re.compile(r"(?:19|20)\d\d\s+%")  # "Full Year 2022 % change": a year heading a column of changes


def _year(a: Amount, text: str) -> bool:
    """A year, unless a scale or currency word follows it: "1999 million" is an amount (19/11)."""
    return a.is_year and not UNIT_WORD.match(text[a.end:].lstrip())


def _figures(answer: str) -> List[Amount]:
    text = answer.split(META)[0]
    days = [m.span(m.lastindex) for m in DAY.finditer(text)]  # "June 30", "30/06/2021", "2021-06-30", "ngày 30": the day of a date is not a figure
    out = []
    for a in find_amounts(text, space_groups=True):  # "89 913" is one figure
        if _year(a, text) or a.is_reference or a.value is None or any(s <= a.start < e for s, e in days):
            continue
        if REFERENCE_BEFORE.search(text[max(0, a.start - 40):a.start]) or YEAR_PERCENT.fullmatch(a.raw):
            continue
        if text[a.start - 1:a.start] == "[" and text[a.end:a.end + 1] == "]":
            continue  # citation marker [3]
        if a.is_plain_integer and abs(a.value) <= SMALL:
            continue
        out.append(a)
    return out


def _readings(a: Amount) -> List[Tuple[float, int]]:
    """(value, decimals) ways to read a printed number. "89.913" is 89.913 in English and 89,913 in Vietnamese (VAS); "25,785" the other
    way round: a single mark followed by exactly three digits can be either, so both readings are tried, for the answer and the excerpts."""
    decimals = len(a.normalized.split(".")[1]) if "." in a.normalized else 0
    out = [(abs(float(a.value)), decimals)]
    marks = [ch for ch in a.digits if ch in ",."]
    if len(marks) == 1:
        integer, fraction = a.digits.split(marks[0])
        if len(fraction) == 3 and 1 <= len(integer) <= 3 and integer != "0":
            out.append((float(f"{integer}.{fraction}"), 3) if a.has_grouping else (float(integer + fraction), 0))
    return out


def _excerpt_numbers(chunks: Sequence[Dict[str, Any]]) -> List[float]:
    """Every number the excerpts print: each way to read it, and a space-grouped "89 913" both as 89913 and as the two numbers a reader
    of a flattened table row could also see (the columns "3 650 3 484" must not hide 3 650)."""
    amounts = [(a, c.get("content", "")) for c in chunks for grouped in (False, True) for a in find_amounts(c.get("content", ""), space_groups=grouped)]
    return [v for a, text in amounts if a.value is not None and not _year(a, text) and a.value != 0 for v, _ in _readings(a)]


def _trusted(chunks: Sequence[Dict[str, Any]]) -> set:
    """The excerpt numbers at every scale a printed figure may use ("$20.6 billion" for 20,604 millions)."""
    return {round(v * s, 6) for v in _excerpt_numbers(chunks) for s in (1.0, 1e3, 1e6, 1e9, 1e-3, 1e-6)}


def _tolerance(decimals: int) -> float:
    """Half a unit of the last digit the answer printed: 5.6 covers 5.55-5.65, 2,197 covers 2,196.5-2,197.5."""
    return 0.5 * 10.0 ** -decimals + 1e-9


def _derived_tolerance(decimals: int, primary: bool = True) -> float:
    """The tolerance for a figure that is a sum, difference, average or product of two figures: when the answer prints two or more decimals, its
    operands are rounded numbers too (margins, ratios, per-share amounts), and the result of the printed operands can be one unit of the last digit
    away from the result of the unrounded ones (3.3299 - 3.1883 = 0.1416 printed, 0.1417 unrounded). Half a unit otherwise: a whole number in
    millions is an exact table value; at one decimal a whole unit (0.1) is so wide that figures matched other derived values by chance (replay of
    923 stored answers, 18/11: planted wrong figures 13.5, 25.3, 56.9 got through); and the second reading of "36,701" as 36.701 is not a decimal."""
    return 2 * _tolerance(decimals) - 1e-9 if decimals >= 2 and primary else _tolerance(decimals)


def _near(sorted_values: np.ndarray, value: float, tol: float) -> bool:
    i = int(np.searchsorted(sorted_values, value))
    return any(0 <= j < len(sorted_values) and abs(sorted_values[j] - value) <= tol for j in (i - 1, i))


def _derived(pool: np.ndarray):
    """(additive results, which may be rescaled like a printed number; ratio results, which may not), both sorted."""
    x, y = pool[:, None], pool[None, :]
    additive = np.concatenate([(x + y).ravel(), np.abs(x - y).ravel(), ((x + y) / 2).ravel(), (x * y).ravel(), (x * y / 100).ravel()])
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (x / y).ravel()
    ratio = np.concatenate([r, r * 100, np.abs(r - 1) * 100])
    return np.sort(additive), np.sort(ratio[np.isfinite(ratio)])


def _printed(chunks: Sequence[Dict[str, Any]]) -> np.ndarray:
    return np.unique(np.array(_excerpt_numbers(chunks), dtype=float))


def _match(f: Amount, printed: np.ndarray):
    """The reading of `f` that `printed` (excerpt numbers) holds, at any scale a figure may use, or None."""
    scales = SCALES + (PERCENT_SCALES if f.is_percent else ())
    return next((v for v, decimals in _readings(f) if len(printed) and any(_near(printed, v * s, _tolerance(decimals) * s) for s in scales)), None)


def check_numbers(answer: str, chunks: Sequence[Dict[str, Any]], passes: int = 3) -> Dict[str, Any]:
    """{"checked", "verified", "derived", "written", "unverified": [figure as printed], "figures": [{"text", "status"}]}."""
    figures, status, _ = _statuses(answer, chunks, passes)
    return {
        "checked": len(figures),
        "verified": status.count("verified"),
        "derived": status.count("derived"),
        "written": status.count("written"),
        "unverified": [f.raw for f, s in zip(figures, status) if s == "unverified"],
        "figures": [{"text": f.raw, "status": s} for f, s in zip(figures, status)],
    }


def _statuses(answer: str, chunks: Sequence[Dict[str, Any]], passes: int = 3) -> Tuple[List[Amount], List[str], List[float]]:
    """(figures, the status of each: verified | derived | written | unverified, the value each was checked with)."""
    figures = _figures(answer)
    readings = [_readings(f) for f in figures]
    status = ["unverified"] * len(figures)
    used = [r[0][0] for r in readings]  # the reading that matched (the printed one until one does): it feeds the derived figures
    printed = _printed(chunks)
    for k, f in enumerate(figures):
        v = _match(f, printed)
        if v is not None:
            status[k], used[k] = "verified", v
    for _ in range(passes):  # a derived figure may feed the next one: average assets, then ROA from it
        pool = np.unique(np.array([u for u, s in zip(used, status) if s != "unverified"], dtype=float))
        if len(pool) < 1:
            break
        additive, ratio = _derived(pool)
        changed = False
        for k in range(len(figures)):
            if status[k] == "unverified":
                for n, (v, decimals) in enumerate(readings[k]):
                    tol, tol_add = _tolerance(decimals), _derived_tolerance(decimals, primary=n == 0)
                    if any(_near(additive, v * s, tol_add * s) for s in SCALES) or _near(ratio, v, tol):
                        status[k], used[k], changed = "derived", v, True
                        break
        if not changed:
            break
    if "unverified" in status:  # rule B: a figure the answer's own written, correct calculation of checked numbers produces, within the figure's own rounding
        base = {abs(u) for u, s in zip(used, status) if s != "unverified"} | _trusted(chunks) | CONSTANTS
        written = written_results(answer, base)
        ok = np.unique(np.array(sorted(written), dtype=float))
        # a percent of a ratio the answer computed ("= 0.00447 = 0.4%"); only the computed numbers, not every excerpt number x 100
        pct = np.unique(np.array(sorted(x * 100 for x in written - base), dtype=float))
        for k in range(len(figures)):
            if status[k] == "unverified" and any(_near(ok, v, _tolerance(d)) or (figures[k].is_percent and _near(pct, v, _tolerance(d))) for v, d in readings[k]):
                status[k] = "written"
    return figures, status, used


# ------------------------------------------------------------------ a figure and the excerpt its citation points at (citations.check_citations)
def _results(answer: str) -> Set[float]:
    """The printed results of the answer's right written steps ("25,785 − 22,680 = 3,105": 3,105)."""
    out: Set[float] = set()
    for left, right, _ in steps(answer):
        if is_calc(left) and SINGLE.fullmatch(right):
            for loc in readings_of(answer):
                if exact(left, right, loc) is not None:
                    out |= {abs(value_of(t, loc)) for t in NUMTOK.findall(right)}
    return out


def _computed(f: Amount, value: float, status: List[str], used: List[float], results: Set[float]) -> bool:
    """Whether the answer computes `f` itself: a standard constant, the result of a right written step, or (a percent or a figure under 1,000) a pair of
    its other checked figures. An amount of 1,000 or more is explained by a written step only: pairs of an answer's figures (a total and its parts)
    cover many amounts by chance."""
    readings = _readings(f)
    if any(abs(v - c) < 1e-9 for v, _ in readings for c in CONSTANTS) or any(abs(v - r) <= _tolerance(d) for v, d in readings for r in results):
        return True
    if not f.is_percent and abs(value) >= 1000:
        return False
    own = {round(v, 9) for v, _ in readings}
    pool = np.unique(np.array([u for u, s in zip(used, status) if s != "unverified" and round(u, 9) not in own], dtype=float))
    if not len(pool):
        return False
    additive, ratio = _derived(pool)
    return any(any(_near(additive, v * s, _derived_tolerance(d) * s) for s in SCALES) or _near(ratio, v, _tolerance(d)) for v, d in readings)


def figures_off_their_citation(answer: str, chunks: Sequence[Dict[str, Any]], runs: Sequence[Tuple[str, List[int], List[int]]]) -> List[Tuple[int, str, str]]:
    """[(n, figure as printed, clause)]: a figure written before a run of citations ("[1]", "[1][2]", "[1, 2]") that belongs to ANOTHER REPORT than the
    ones cited ("Its revenue was $60,922 million [1]" with 60,922 only in NVIDIA's report and [1] an AMD page): the citation points at the wrong source.
    A figure printed in no excerpt is the number check's, and a figure the answer computes (_computed) needs no excerpt of its own.
    Loosened 19/11 (owner: the model rarely cites wrong, report only what is surely wrong): a figure from another page of a cited report is not reported
    (4 of the 5 wrong citations of 770 stored answers: "612.2 ÷ 3,140.5 = 19.5%; reported rate = 19.5% [2]", right figures, right report), the run
    before the clause in the sentence counts too ("the FY2017 report [2] gives 18,434, the FY2019 report [1] ..."), and excerpts that do not say which
    report they are from are never judged."""
    # (clause, the run closing it, the run before it in the sentence): a figure may follow the citation that names its report (live answer 19/11)
    runs = [(clause, [n for n in ns if 1 <= n <= len(chunks)], [n for n in before if 1 <= n <= len(chunks)]) for clause, ns, before in runs]
    runs = [(clause, ns, before) for clause, ns, before in runs if ns and clause.strip()]
    if not runs:
        return []
    _, status, used = _statuses(answer, chunks)
    excerpts, results, out = [_printed([c]) for c in chunks], _results(answer), []
    for clause, ns, before in runs:
        reports = {chunks[n - 1].get("document_id") for n in ns + before}
        if None in reports:
            continue  # an excerpt that does not say which report it is from: nothing can be shown to come from another one
        cited = _printed([c for c in chunks if c.get("document_id") in reports])  # every page of the cited reports
        for f in _figures(clause):
            if _match(f, cited) is not None:
                continue
            value = next((v for k, e in enumerate(excerpts, 1) if chunks[k - 1].get("document_id") not in reports | {None} for v in [_match(f, e)] if v is not None), None)
            if value is not None and not _computed(f, value, status, used, results):
                out.append((ns[0], f.raw, " ".join(clause.split())[-160:]))
    return out
