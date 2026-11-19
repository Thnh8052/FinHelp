"""Two reports that print different figures for the same line item and year: a later annual report restating or reclassifying an earlier year (Amazon's
2017 operating cash flow is 18,434 in its FY2017 10-K and 18,365 in its FY2019 10-K). Owner 19/11: the user must be told. The system prompt already
asked for it; nothing made sure the model saw the difference. Code finds it in the excerpts BEFORE the answer is written and adds the owner-approved
note; it never changes a figure.

Only what a restatement can be: annual reports of one company, a year both reports have closed (a schedule of future payments changes every year,
a 10-Q column may be six months), the same table title and a row name that says what it is ("Other, net" and untitled tables matched by chance).
Measured 19/11 on the FinanceBench annual reports (experiments/scripts/system_test_18_11/figure_conflicts.py): 93 conflicts in 4,262 cells two reports
print; about 18-19 of a sample of 20 were real restatements or reclassifications."""
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.modules.generation.answer_check.amounts import find_amounts

YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
ANNUAL_FORMS = {"10-k", "20-f", "40-f", "annual report"}
GENERIC = {"other", "other net", "net", "total", "euro", "yen", "pound", "average price per share", "other assets", "other liabilities", "other income"}
SCALES = (1.0, 1e3, 1e-3, 1e6, 1e-6)  # the same figure in thousands in one report and in millions in the other
LIMIT = 3  # notes per answer: a long table restated line by line must not crowd the prompt
NOTE = ('Excerpts [{a}] and [{b}] print different figures for "{label}" in {year}: {x} in [{a}] ({report_a}) and {y} in [{b}] ({report_b}); '
        "the later report has probably restated it. If your answer uses this figure, tell the user both figures with their reports and say which one "
        "you used (the later report's).")  # wording approved by the owner 19/11


@dataclass(frozen=True)
class Report:
    company: str  # catalog_route.company_key of the company name
    annual: bool
    fiscal_year: Optional[int]
    label: str  # as the excerpt headers name the report


Row = Tuple[str, str, int, float, int, str]  # (row key, row name as printed, year, value, decimals, value as printed)


def _rows(content: str) -> List[Row]:
    """The rows of the markdown tables of an excerpt: a header row gives the year of each column, the first cell of a data row its name."""
    out: List[Row] = []
    years: Optional[List[Optional[str]]] = None
    for line in content.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        found = [YEAR.findall(c) for c in cells]
        numbers = [c for c in cells[1:] if not YEAR.search(c) and find_amounts(c)]
        if years is None or (sum(1 for f in found[1:] if len(f) == 1) >= 2 and not numbers):
            years = [f[0] if len(f) == 1 else None for f in found]  # a header row
            continue
        name = cells[0].replace("**", "").strip()
        key = re.sub(r"[^a-z ]", "", re.sub(r"\([a-z0-9]\)", " ", name.lower())).strip()  # "Other, net (b)": a footnote mark says nothing
        key = " ".join(key.split())
        if key in GENERIC or len(key.split()) < 2:
            continue
        for k, cell in enumerate(cells[1:], 1):
            year = years[k] if k < len(years) else None
            amounts = [a for a in find_amounts(cell) if a.value is not None and not a.is_year]
            if year and amounts:
                a = amounts[0]
                decimals = len(a.normalized.partition(".")[2])
                out.append((key, name, int(year), float(a.value), decimals, a.raw.strip()))
    return out


def _same(x: Tuple[float, int], y: Tuple[float, int]) -> bool:
    tol = 0.5 * 10 ** -min(x[1], y[1])
    return any(abs(x[0] - y[0] * s) <= tol * max(1.0, s) for s in SCALES)


def conflict_notes(chunks: Sequence[Dict[str, Any]], reports: Mapping[str, Report], limit: int = LIMIT) -> List[str]:
    """The approved note for each line item and year that two annual reports of one company print with different figures, excerpts numbered [1].. in
    the order given; [] when there is none."""
    seen: Dict[Tuple[str, str, str, int], Dict[str, Any]] = {}  # (company, table, row, year) -> document -> (n, name, value, decimals, printed) | None
    for n, c in enumerate(chunks, 1):
        doc = c.get("document_id")
        report, title = reports.get(doc), (c.get("table_title") or "").strip().lower()
        if not report or not report.annual or not report.fiscal_year or not title:
            continue
        for key, name, year, value, decimals, printed in _rows(c.get("content") or ""):
            if year > report.fiscal_year:  # not a closed year of this report
                continue
            slot = seen.setdefault((report.company, title, key, year), {})
            if doc in slot:
                if slot[doc] is not None and not _same((slot[doc][2], slot[doc][3]), (value, decimals)):
                    slot[doc] = None  # one report, two values: two tables matched by name, never a restatement
                continue
            slot[doc] = (n, name, value, decimals, printed)
    notes: List[str] = []
    for (_, _, _, year), slot in seen.items():
        if len(slot) < 2 or None in slot.values():
            continue
        entries = sorted(slot.items(), key=lambda item: reports[item[0]].fiscal_year or 0)
        (doc_a, a), (doc_b, b) = entries[0], entries[-1]
        if _same((a[2], a[3]), (b[2], b[3])):
            continue
        notes.append(NOTE.format(a=a[0], b=b[0], label=b[1], year=year, x=a[4], y=b[4], report_a=reports[doc_a].label, report_b=reports[doc_b].label))
        if len(notes) == limit:
            break
    return notes
