"""Deterministic lookup of the filings a question targets, from structured targets (company, year, quarter) and the upload metadata.
The language model only has to say WHAT is asked (company as written in the catalog, year, whether the user named a fiscal year);
this module decides WHICH filing, so a year is never matched loosely. Not wired into the orchestrator yet (needs the planner to emit
targets, which has to be measured with API calls).

Year rules (the same 12 months carry different names: Ulta 'fiscal 2022' and Best Buy 'fiscal 2023' both end 2023-01-28):
- basis "fiscal"  (the user wrote FY2022 / fiscal 2022 / năm tài chính 2022): the company's own name of the year;
- basis "calendar" (calendar 2022 / năm dương lịch 2022): comparable_year (fiscal year ending Jan-May -> previous calendar year);
- basis "unspecified" (plain "2022"): the company's own name, except in a comparison of companies whose fiscal years end in different
  halves of the calendar, where every company is aligned on comparable_year so the figures cover the same months.
A fiscal-year name the company never used falls back to the year the period ends in (Ulta calls the year ending 2023-01-28
'fiscal 2022'; FinanceBench and the file name call it FY2023), with the rule saying so.
No year: the latest annual filing. Annual questions prefer the 10-K over 8-Ks / earnings releases of the same year.
An aligned comparison is disclosed with the answer (alignment_note): which fiscal year of each company stands for the year asked."""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

ANNUAL_FORMS = ("10-K",)


@dataclass
class Filing:
    document_id: str
    company: str
    form: str = ""
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    comparable_year: Optional[int] = None
    period_end: Optional[str] = None  # ISO date


@dataclass
class Target:
    company: str
    year: Optional[int] = None
    basis: str = "unspecified"  # fiscal | calendar | unspecified
    quarter: Optional[int] = None


@dataclass
class Resolution:
    target: Target
    document_ids: List[str] = field(default_factory=list)
    rule: str = ""
    problem: str = ""  # 'company not in sources' | 'period not in sources' | 'several filings match'


def _key(name: str) -> str:
    stop = {"the", "inc", "incorporated", "corporation", "corp", "company", "co", "plc", "ltd", "limited", "and"}
    return " ".join(w for w in re.findall(r"[a-z0-9&]+", name.lower()) if w not in stop)


def _same_company(a: str, b: str) -> bool:
    ka, kb = _key(a), _key(b)
    return bool(ka and kb) and (ka == kb or ka.startswith(kb + " ") or kb.startswith(ka + " "))


def _offset(f: Filing) -> bool:
    """fiscal year mostly in the previous calendar year (ends January-May)"""
    return f.comparable_year is not None and f.fiscal_year is not None and f.comparable_year != f.fiscal_year


def resolve(targets: Sequence[Target], filings: Sequence[Filing]) -> List[Resolution]:
    mine = [[f for f in filings if _same_company(t.company, f.company)] for t in targets]
    annual = [[f for f in fs if f.form in ANNUAL_FORMS] for fs in mine]
    # a comparison across companies whose fiscal calendars differ is aligned on the calendar year
    companies = {_key(f.company) for fs in annual for f in fs}
    align = len(companies) > 1 and len({_offset(f) for fs in annual for f in fs}) > 1
    out = []
    for t, fs, an in zip(targets, mine, annual):
        r = Resolution(t)
        if not fs:
            r.problem = "company not in sources"
        elif t.quarter:
            r.document_ids = [f.document_id for f in fs if f.fiscal_quarter == t.quarter and f.fiscal_year == t.year]
            r.rule = "fiscal quarter"
        elif t.year is None:
            latest = max(an or fs, key=lambda f: (f.fiscal_year or 0, f.fiscal_quarter or 5))
            r.document_ids, r.rule = [latest.document_id], "no year: latest filing"
        else:
            calendar = t.basis == "calendar" or (t.basis == "unspecified" and align)
            pick = [f for f in an if (f.comparable_year if calendar and f.comparable_year is not None else f.fiscal_year) == t.year]
            r.rule = "calendar year (comparable_year)" if calendar else "company's fiscal year name"
            if not pick and not calendar:
                pick = [f for f in an if f.period_end and int(f.period_end[:4]) == t.year]
                r.rule = "year the period ends in (the company names it FY%s)" % (pick[0].fiscal_year if pick else "?")
            if not pick:  # no 10-K of that year: any annual-period document of that year (8-K / earnings release)
                pick = [f for f in fs if f.fiscal_quarter is None and f.fiscal_year == t.year]
            r.document_ids = [f.document_id for f in pick]
        if not r.problem and not r.document_ids:
            r.problem = "period not in sources"
        elif len(r.document_ids) > 1:
            r.problem = "several filings match"
        out.append(r)
    return out


def alignment_note(resolutions: Sequence[Resolution], filings: Sequence[Filing], vi: bool = True) -> str:
    """One line shown with the answer when a plain-year comparison was aligned on the calendar year, e.g.
    "So sánh năm 2022: Coca-Cola tính theo FY2022 (kết thúc 12/2022); Walmart tính theo FY2023 (kết thúc 01/2023, đại diện cho năm lịch 2022)."
    Empty when nothing was aligned."""
    rs = [r for r in resolutions if r.rule.startswith("calendar") and r.target.basis == "unspecified" and len(r.document_ids) == 1]
    if len(rs) < 2:
        return ""
    by_id = {f.document_id: f for f in filings}
    parts = []
    for r in rs:
        f, y = by_id[r.document_ids[0]], r.target.year
        detail = [("kết thúc " if vi else "ended ") + f"{f.period_end[5:7]}/{f.period_end[:4]}"] if f.period_end else []
        if f.fiscal_year != y:
            detail.append(f"đại diện cho năm lịch {y}" if vi else f"standing for calendar {y}")
        parts.append(f"{r.target.company} " + ("tính theo" if vi else "uses") + f" FY{f.fiscal_year}" + (f" ({', '.join(detail)})" if detail else ""))
    years = ", ".join(str(y) for y in sorted({r.target.year for r in rs}))
    return ("So sánh năm " if vi else "Comparing ") + years + ": " + "; ".join(parts) + "."
