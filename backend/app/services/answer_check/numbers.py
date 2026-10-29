"""A4 number check: every figure an answer states must be printed in its excerpts (any scale: "$20.6 billion" for "20,604"
millions), or follow from two figures the answer itself states and that check (sum, difference, average, ratio, percent,
growth, a percent of an amount). Code only, no model. Derivations from any two excerpt numbers are not accepted: a table holds hundreds of numbers whose
sums and ratios cover almost any value (that version caught 18-20% of planted wrong figures).

Log-only for now (Bedrock's advice: watch before blocking): the report goes into the trace, nothing is blocked or regenerated.
"""
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from app.services.answer_check.amounts import Amount, find_amounts

META = "<answer_meta>"  # generator v3 appends a machine block; only the text before it is the answer
SMALL = 12  # plain integers up to this are list markers, months, quarters or counts ("3 segments"): not checked
SCALES = (1.0, 1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9)  # "$20.6 billion" against "20,604" (millions)
PERCENT_SCALES = (1e-2, 1e2)  # "25%" against "0.25"


def _figures(answer: str) -> List[Amount]:
    text = answer.split(META)[0]
    out = []
    for a in find_amounts(text, space_groups=True):  # "89 913" is one figure
        if a.is_year or a.is_reference or a.value is None:
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
    amounts = [a for c in chunks for grouped in (False, True) for a in find_amounts(c.get("content", ""), space_groups=grouped)]
    return [v for a in amounts if a.value is not None and not a.is_year and a.value != 0 for v, _ in _readings(a)]


def _tolerance(decimals: int) -> float:
    """Half a unit of the last digit the answer printed: 5.6 covers 5.55-5.65, 2,197 covers 2,196.5-2,197.5."""
    return 0.5 * 10.0 ** -decimals + 1e-9


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


def check_numbers(answer: str, chunks: Sequence[Dict[str, Any]], passes: int = 3) -> Dict[str, Any]:
    """{"checked", "verified", "derived", "unverified": [figure as printed], "figures": [{"text", "status"}]}."""
    figures = _figures(answer)
    readings = [_readings(f) for f in figures]
    status = ["unverified"] * len(figures)
    used = [r[0][0] for r in readings]  # the reading that matched (the printed one until one does): it feeds the derived figures
    printed = np.unique(np.array(_excerpt_numbers(chunks), dtype=float))
    for k, f in enumerate(figures):
        scales = SCALES + (PERCENT_SCALES if f.is_percent else ())
        for v, decimals in readings[k]:
            tol = _tolerance(decimals)
            if len(printed) and any(_near(printed, v * s, tol * s) for s in scales):
                status[k], used[k] = "verified", v
                break
    for _ in range(passes):  # a derived figure may feed the next one: average assets, then ROA from it
        pool = np.unique(np.array([u for u, s in zip(used, status) if s != "unverified"], dtype=float))
        if len(pool) < 1:
            break
        additive, ratio = _derived(pool)
        changed = False
        for k in range(len(figures)):
            if status[k] == "unverified":
                for v, decimals in readings[k]:
                    tol = _tolerance(decimals)
                    if any(_near(additive, v * s, tol * s) for s in SCALES) or _near(ratio, v, tol):
                        status[k], used[k], changed = "derived", v, True
                        break
        if not changed:
            break
    return {
        "checked": len(figures),
        "verified": status.count("verified"),
        "derived": status.count("derived"),
        "unverified": [f.raw for f, s in zip(figures, status) if s == "unverified"],
        "figures": [{"text": f.raw, "status": s} for f, s in zip(figures, status)],
    }
