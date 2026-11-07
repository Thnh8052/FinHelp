"""Document header "company | form | fiscal period", read from the filing text only.

Copy of the research extractor (experiments/chunking/studies/auto_header/header_extract.py, measured on
89 Docling documents: company/form 89/89, period 86/89; on 276 unseen PDFs: company 96.7%, form 98.2%).
No file name and no assumption that page 1 is the cover: every field is a vote over all pages.
The multi-document planner needs it to tell the filings of one notebook apart.
"""
import collections
import datetime
import re
from typing import Any, Dict, List, Optional, Tuple

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MON = "(" + "|".join(MONTHS) + ")"
DATE = MON + r"\s+(\d{1,2})\s*,?\s*(\d{4})"
SUFFIX = r"(?:Inc\.?|Incorporated|Corporation|Corp\.|Company|Co\.|plc|PLC|N\.V\.|Ltd\.?|Limited|S\.A\.)"
LEGAL = re.compile(r"\b((?:The\s+)?[A-Z0-9][\w&.'\-]*(?:\s+(?:[A-Z0-9&][\w&.'\-]*|of|and)){0,4}),?\s+" + SUFFIX + r"(?![\w])")
STOPKEY = {"the", "inc", "incorporated", "corporation", "corp", "company", "co", "plc", "nv", "ltd", "limited", "sa", "and", "subsidiaries", "its"}
BAD = re.compile(r"\b(Exchange|Commission|Securities|Trust|Bank of New York|Depository|Investors Service|Ratings|Standard|Moody|Fitch|Ernst|Deloitte|KPMG|Pricewaterhouse|Nasdaq|Stock Market|Federal|Reserve|Act|Item|Form|Notes?|Exhibit|Consolidated|Balance|Statements?|Period|Parent)\b", re.I)
QW = ["first", "second", "third", "fourth"]


def _key(name: str) -> str:
    return " ".join(w for w in re.findall(r"[a-z0-9&]+", name.lower()) if w not in STOPKEY)


def _company(full: str) -> Tuple[Optional[str], Dict[str, int], Dict[str, str]]:
    votes: collections.Counter = collections.Counter()
    surface: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

    def add(n: str, w: int) -> bool:
        n = re.sub(r"\s+", " ", n).strip(" ,.;:-")
        m = re.search(r"^(.*?" + SUFFIX + r")(?=[\s,]|$)", n)  # cut trailing city/state after the legal suffix
        if m:
            n = m.group(1)
        k = _key(n)
        if len(k) < 2 or len(n) > 70 or re.search(r"\d{4}", n) or BAD.search(n):
            return False
        votes[k] += w
        surface[k][n] += w
        return True

    lines = [ln.strip() for ln in full.split("\n") if ln.strip()]
    skip = re.compile(r"commission|file number|fiscal|quarter|annual|form\b|\bOR\b|state of|ended|period|mark one|check|transition|\(|registrant", re.I)
    for i, ln in enumerate(lines):
        if re.search(r"exact name of registrant", ln, re.I):  # SEC cover anchor, wherever it is
            for j in range(i - 1, max(-1, i - 4), -1):
                if not skip.search(lines[j]) and re.search(r"[A-Za-z]{2}", lines[j]):
                    add(lines[j], 30)
                    break
        m = re.match(r"(.{2,60}?)\s*\(Registrant\)", ln)  # signature block
        if m:
            add(m.group(1), 10)
    for m in re.finditer(r"([A-Z][\w&.,' \-]{1,60}?)\s*\((?:NYSE|NASDAQ|Nasdaq|NYSE American|ASX)\s*:\s*[A-Z.]{1,6}\)", full):
        add(re.sub(r"^.*\)\s*[-–—]\s*", "", m.group(1)), 10)  # press-release dateline
    for m in re.finditer(r"To the (?:Shareholders|Stockholders|Shareowners|Board of Directors|Members)(?:[\w ,]{0,60}?Directors)?\s+of\s+([A-Z][^\n:]{1,70}?)\s*(?:\n|:|$|Opinion)", full):
        add(m.group(1), 15)  # auditor's report addressee
    for m in re.finditer(r"([A-Z][\w&.,' \-]{1,60}?)\s+(?:AND|and)\s+(?:CONSOLIDATED\s+|Consolidated\s+)?(?:SUBSIDIARIES|Subsidiaries)\b", full):
        add(m.group(1), 10)  # statement banner
    legal: collections.Counter = collections.Counter()
    for m in LEGAL.finditer(full):  # legal-entity mentions, capped per name so a subsidiary or counterparty list cannot win
        k = _key(m.group(0))
        if legal[k] < 20 and add(m.group(0), 1):
            legal[k] += 1
    if not votes:
        return None, {}, {}
    top = dict(votes.most_common(5))
    printed = {k: surface[k].most_common(1)[0][0] for k in top}
    return printed[next(iter(top))], top, printed


def _form(full: str) -> Optional[str]:
    c = {"10-K": len(re.findall(r"this\s+(?:Annual\s+)?Report\s+on\s+Form\s+10-K|this\s+Form\s+10-K|ANNUAL REPORT PURSUANT", full, re.I)),
         "10-Q": len(re.findall(r"this\s+(?:Quarterly\s+)?Report\s+on\s+Form\s+10-Q|this\s+Form\s+10-Q|QUARTERLY REPORT PURSUANT", full, re.I)),
         "8-K": len(re.findall(r"CURRENT REPORT PURSUANT|this\s+(?:Current\s+)?Report\s+on\s+Form\s+8-K|Date of earliest event reported", full, re.I))}
    press = len(re.findall(r"\((?:NYSE|NASDAQ|Nasdaq|ASX)\s*:\s*[A-Z.]{1,6}\)|today (?:reported|announced)|press release|\breports?\b[^\n]{0,60}\bresults\b", full, re.I))
    if c["10-K"] + c["10-Q"] == 0 and not re.search(r"CURRENT REPORT PURSUANT|Date of earliest event", full, re.I):
        return "earnings release" if press else None
    return max(c, key=lambda k: c[k])


def _todate(m, i: int = 1) -> Tuple[int, int, int]:
    return (int(m.group(i + 2)), MONTHS.index(m.group(i).title()) + 1, int(m.group(i + 1)))


def _period(full: str, f: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[Tuple[int, int, int]], Optional[Tuple[int, int, int]]]:
    """(fiscal year as the company names it, quarter or None, period end or None, previous period end or None).
    Period end = the most cited "ended <date>" (statement columns repeat it), reported only when cited twice or more or read from
    the 8-K "Date of Report"; previous end = the most cited "ended" date 51-53 weeks
    earlier (the comparative column), from which the period start follows."""
    ends = collections.Counter(_todate(m) for m in re.finditer(r"ended[\s:\-–—]*" + DATE, full, re.I) if 1990 <= int(m.group(3)) <= 2030)
    m = re.search(r"Date of Report[\s\S]{0,80}?" + DATE, full, re.I) if f == "8-K" else None  # the date may sit on the next line
    # an end date cited once is a stray comparative (J&J earnings releases print "Fourth Quarter - 2022", never the date)
    if m:
        end, sure = _todate(m), True
    elif ends and f != "8-K":  # ties (current vs prior columns): latest
        top = ends.most_common(1)[0][1]
        end = max(d for d, n in ends.items() if n >= .8 * top)
        sure = ends[end] >= 2
    else:
        alld = collections.Counter(_todate(m) for m in re.finditer(DATE, full))
        if not alld:
            return None, None, None, None
        end = alld.most_common(1)[0][0]
        sure = alld[end] >= 2
    prior = [(n, d) for d, n in ends.items() if 357 <= (_day(end) - _day(d)) <= 371]
    prev_end = max(prior)[1] if prior and f == "10-K" else None
    # fiscal label the company itself attaches to that end date ("fiscal 2022, which ended January 28, 2023"), else the end year
    ed = rf"{MONTHS[end[1] - 1]}\s+{end[2]}\s*,?\s*{end[0]}"
    fl = r"[Ff]iscal(?:\s+[Yy]ear)?\s+(20\d\d)"
    linked = collections.Counter(int(m.group(1)) for m in re.finditer(fl + r"[^.\n]{0,40}?\bended\s+(?:on\s+)?" + ed, full, re.I))
    linked += collections.Counter(int(m.group(1)) for m in re.finditer(ed + r"\s*\(\W{0,3}" + fl, full, re.I))
    linked = collections.Counter({y: n for y, n in linked.items() if abs(y - end[0]) <= 1})
    fy = linked.most_common(1)[0][0] if linked and f != "8-K" else end[0]
    if not linked and f != "8-K" and end[1] == 1 and end[2] <= 7:
        fy = end[0] - 1  # 52/53-week year ending around January 1
    qp: collections.Counter = collections.Counter()
    for m in re.finditer(r"\b(first|second|third|fourth)[\s-]+(?:fiscal\s+)?quarter\s+(?:of\s+)?(?:fiscal\s+)?(?:year\s+)?(20\d\d)\b", full, re.I):
        qp[(int(m.group(2)), QW.index(m.group(1).lower()) + 1)] += 1
    for m in re.finditer(r"\b(20\d\d)\s+(first|second|third|fourth)[\s-]+quarter", full, re.I):
        qp[(int(m.group(1)), QW.index(m.group(2).lower()) + 1)] += 1
    qp = collections.Counter({k: n for k, n in qp.items() if abs(k[0] - end[0]) <= 1})
    q = None
    if f == "10-Q":
        n3, n6, n9 = (len(re.findall(w + r"\s+months\s+ended[\s:\-–—]*" + ed, full, re.I)) for w in ("three", "six", "nine"))
        q = 3 if n9 >= max(1, .2 * n3, n6) else 2 if n6 >= max(1, .2 * n3) else 1  # .2 tolerates copy-paste slips
        same = [(k[0], n) for k, n in qp.items() if k[1] == q]
        if same:
            fy = max(same, key=lambda x: x[1])[0]
    elif f == "earnings release" and qp:
        fy, q = qp.most_common(1)[0][0]
    return fy, q, end if sure else None, prev_end


def _day(d: Tuple[int, int, int]) -> int:
    return datetime.date(*d).toordinal()


def _iso(d: Optional[Tuple[int, int, int]]) -> Optional[str]:
    return datetime.date(*d).isoformat() if d else None


def comparable_year(period_end: Optional[str]) -> Optional[int]:
    """Calendar year an annual period mostly falls in (Compustat 'fyear' convention): a fiscal year ending January-May belongs to
    the previous calendar year, one ending June-December to the year it ends in. Ulta 'fiscal 2022' and Best Buy 'fiscal 2023'
    both end 2023-01-28 -> 2022."""
    if not period_end:
        return None
    y, m = int(period_end[:4]), int(period_end[5:7])
    return y - 1 if m <= 5 else y


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"[#*|\\]", " ", text.replace("<!-- image -->", " ")))


def extract_document_header(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """pages: parser output ({"page_number", "text"}). Returns company_name / report_type / fiscal_year (as the company names it) /
    fiscal_quarter, period_end, period_start (10-K, when the prior year-end is printed) and comparable_year (10-K) (None where the
    text does not say), and the display header "Company | form | FY2022 [Q2]"."""
    full = "\n".join(_clean(page["text"]) for page in sorted(pages, key=lambda p: p["page_number"]))
    company, _, _ = _company(full)
    form = _form(full)
    fy, quarter, end, prev_end = _period(full, form)
    period = f"FY{fy}" + (f" Q{quarter}" if quarter else "") if fy else None
    annual = form == "10-K"
    return {"company_name": company, "report_type": form, "fiscal_year": fy, "fiscal_quarter": quarter,
            "period_end": _iso(end), "period_start": _iso(datetime.date.fromordinal(_day(prev_end) + 1).timetuple()[:3]) if prev_end else None,
            "comparable_year": comparable_year(_iso(end)) if annual else None,
            "header": " | ".join(x for x in (company, form, period) if x)}



def company_candidates(pages: List[Dict[str, Any]], n: int = 5) -> List[Dict[str, Any]]:
    """Legal names the document text shows, best vote first, each with the pages it is printed on (first 5): the choices the
    catalog form offers, so the user picks a name the document itself carries instead of typing one."""
    texts = {int(p["page_number"]): _clean(p.get("text") or "") for p in pages}
    _, votes, printed = _company("\n".join(texts[k] for k in sorted(texts)))
    keyed = {k: _key(t) for k, t in texts.items()}
    keys = []
    for key in votes:  # "directors of advanced micro devices" repeats a better candidate: dropped
        if not any(k in key for k in keys):
            keys.append(key)
    return [{"name": printed[key], "pages": [k for k in sorted(keyed) if key in keyed[k]][:5]} for key in keys[:n]]
