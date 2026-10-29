import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from app.core.config import settings
from app.core.logging import logger
from app.services.llm.llm_client import LLMUnavailableError, chat_completion


def clean_label(text: str, limit: int = 120) -> str:
    """A catalog value as prompt data: one line, no field separator or control characters, bounded length. The values come from a
    model reading the document or from the user, so a name can never break the catalog line or add lines of its own."""
    return re.sub(r"\s+", " ", re.sub(r"[|\x00-\x1f\x7f]", " ", text or "")).strip()[:limit]


@dataclass
class CatalogEntry:
    """One filing of the notebook as the planner sees it."""

    document_id: str
    company: str = ""
    report_type: str = ""
    period: str = ""
    file_name: str = ""

    def line(self) -> str:
        parts = [clean_label(p) for p in (self.company or self.file_name, self.report_type, self.period)]
        return f"{self.document_id} | " + " | ".join(p for p in parts if p)


@dataclass
class PlanItem:
    """One search to run: English keywords, and the filings it must be searched in (empty = every filing)."""

    query: str
    document_ids: List[str] = field(default_factory=list)


SYSTEM = "You plan retrieval over a set of company financial reports. Output strictly valid JSON."
# Prompt of the research (eval3.py, 85 synthetic multi-filing questions in English, English without company names and Vietnamese).
PROMPT = """You plan retrieval over a set of company financial reports. Each report is one catalog line: doc_id | company | document type | fiscal period.

CATALOG
{catalog}

The user question may be in any language and may not name the companies. Produce the minimal list of search queries, ONE per (report, item to look up).
For each query give:
- "query": English keywords as the item is labelled in financial statements (for example "consolidated statements of income net sales total revenues", "consolidated balance sheets total assets"); no company name needed.
- "doc_ids": the catalog doc_id(s) this query must be searched in. Choose them from the catalog by matching company names and fiscal years in the question; if the question names no company, use the fiscal years and the catalog to pick the reports the question most plausibly refers to (all of them when it is unclear); never invent ids.
At most {max_items} queries. Output ONLY JSON: {{"plan": [{{"query": "...", "doc_ids": ["..."]}}]}}

Question: {q}"""

def expand_plan(plan: Sequence[PlanItem], scope_ids: Sequence[str], limit: int) -> List[PlanItem]:
    """One search per (item, document), so every selected document keeps its own slots even when the planner put several
    documents into one query (an item naming none means every selected document). If that would exceed `limit` searches
    the plan is kept as planned (equal slots per item). Measured on 90 questions: never worse, and it fixes plans that
    pooled 3-4 documents into one query (one document then got no chunk at all)."""
    expanded = [PlanItem(item.query, [doc]) for item in plan for doc in (item.document_ids or list(scope_ids))]
    return expanded if len(expanded) <= limit else list(plan)


_cache: Dict[str, List[PlanItem]] = {}
_CACHE_MAX = 256


def parse_plan(raw: str, valid_ids: Sequence[str], max_items: int) -> List[PlanItem]:
    """Validated plan: unknown document ids are dropped (never searched), blank queries are skipped."""
    valid = set(valid_ids)
    try:
        items = json.loads(raw).get("plan", [])
    except (ValueError, AttributeError):
        match = re.search(r"\{.*\}", raw or "", re.S)  # tolerate prose around the JSON
        try:
            items = json.loads(match.group(0)).get("plan", []) if match else []
        except (ValueError, AttributeError):
            return []
    plan: List[PlanItem] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("query"), str) or not item["query"].strip():
            continue
        ids = [d for d in item.get("doc_ids", []) if isinstance(d, str) and d in valid] if isinstance(item.get("doc_ids"), list) else []
        plan.append(PlanItem(item["query"].strip(), list(dict.fromkeys(ids))))
    return plan[:max_items]


async def plan_multi_doc(question: str, catalog: Sequence[CatalogEntry]) -> List[PlanItem]:
    """One search per (filing, item) for a question over several filings. Any failure returns [] and the caller falls
    back to searching the whole notebook with the question alone."""
    if not catalog:
        return []
    key = question + "\x00" + "\x00".join(sorted(e.line() for e in catalog))
    if key in _cache:
        return _cache[key]
    prompt = PROMPT.format(catalog="\n".join(e.line() for e in catalog), q=question, max_items=settings.MULTIDOC_MAX_SUBQUERIES)
    try:
        raw = await chat_completion(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}], max_tokens=1500, json_mode=True
        )
    except LLMUnavailableError as exc:
        logger.warning(f"Multi-document planning skipped: {type(exc).__name__}")
        return []
    plan = parse_plan(raw, [e.document_id for e in catalog], settings.MULTIDOC_MAX_SUBQUERIES)
    if plan:
        if len(_cache) >= _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[key] = plan
    return plan


# ---------------------------------------------------------------- companies named in the question but not among the selected sources
# The answer must come from the sources the user selected only. A capitalised name that matches none of the selected companies is a
# candidate; the language model then decides whether it is a company outside the selection (it knows tickers, former names and brands:
# "AMD" for "Advanced Micro Devices", "Block" for "Square"). Questions without a candidate cost no extra call.
_TOKEN = re.compile(r"(?<!\w)(?:[A-Z][A-Za-z0-9&\-]*|\d+[A-Z][A-Za-z0-9&\-]*)(?!\w)")
_COMMON = frozenset("""
how which what who whom whose when where why in on at of for by from to between among using based please compare calculate determine
explain describe give show list tell is are was were did do does can could would should the a an and or as if its their this that these
those over during across per with within without also both each either neither all any some more most less least not no yes
gaap ifrs usd vnd eur sec form eps ebit ebitda roe roa roic fcf cfo ceo cogs sga capex opex yoy qoq ytd fy q1 q2 q3 q4 us uk eu
net total income revenue revenues sales assets liabilities equity cash flow profit margin annual quarterly quarter year years fiscal
company companies corporation inc corp ltd plc group holdings percent percentage absolute change changed growth rate ratio larger
higher lower bigger greater largest highest lowest reported report reports amount share shareholders statement statements balance sheet
january february march april may june july august september october november december
assume answer here round roughly approximately address has have had given consider suppose identify find provide state note estimate
evaluate analyze analyse assess summarize summarise define you your we our i it he she they there then so but however although while
since because after before about above below into out up down than too very much many few other another such like just only even still
operating free fixed gross return earnings debt current working capital interest depreciation amortization inventory accounts long short
average days turnover quick dividend dividends expenses expense cost costs price prices stock stocks segment segments region regions
dpo dso dio ar ap ppne ppe pp&e p&l m&a roce nopat wacc cagr npv irr pe pb ev
doanh loi tong so hay cho theo trong nam quy tai bao cac nhung mot cua nao bao nhieu cong ty hoi tinh
""".split())


def name_candidates(question: str, catalog: Sequence[CatalogEntry]) -> List[str]:
    """Capitalised terms of the question that are not ordinary words and appear in no selected company name or file name."""
    known = " ".join(f"{e.company} {e.file_name}" for e in catalog).lower()
    found: List[str] = []
    for match in _TOKEN.finditer(question):
        term = match.group(0).strip("-&")
        low = term.lower()
        if len(term) < 2 or low in _COMMON or re.fullmatch(r"fy\d*|q\d|\d+", low) or low in known or term in found:
            continue
        found.append(term)
    return found


GUARD_PROMPT = """The user selected these reports as the ONLY sources for answering:
{catalog}

Question: {q}

Capitalised terms found in the question: {terms}
Which of these terms name a company or organisation that is NOT one of the companies of the selected reports? Treat a ticker, a former name, an abbreviation, a brand, a product or a subsidiary of a selected company as that selected company. Ignore terms that are not company names (people, places, metrics, ordinary words).
Output JSON only: {{"unlisted": ["term as written in the question", ...]}}"""

_guard_cache: Dict[str, List[str]] = {}


async def unlisted_companies(question: str, catalog: Sequence[CatalogEntry]) -> List[str]:
    """Companies named in the question that are not among the selected filings ([] = nothing to refuse). Fails open: when the
    language model stays silent after retries (an empty reply happens now and then) the question goes ahead as before."""
    terms = name_candidates(question, catalog)
    if not terms:
        return []
    lines = [" | ".join(p for p in (e.company or e.file_name, e.report_type, e.period) if p) for e in catalog]
    key = question + "\x00" + "\x00".join(sorted(lines))
    if key in _guard_cache:
        return _guard_cache[key]
    prompt = GUARD_PROMPT.format(catalog="\n".join(f"- {line}" for line in lines), q=question, terms=", ".join(terms))
    for _ in range(3):
        try:
            raw = await chat_completion([{"role": "user", "content": prompt}], max_tokens=200, json_mode=True)
        except LLMUnavailableError as exc:
            logger.warning(f"Scope check skipped: {type(exc).__name__}")
            return []
        if not raw:
            continue
        try:
            names = json.loads(raw).get("unlisted", [])
        except (ValueError, AttributeError):
            continue
        asked = question.lower()
        result = [n.strip() for n in names if isinstance(n, str) and n.strip() and n.strip().lower() in asked] if isinstance(names, list) else []
        if len(_guard_cache) >= _CACHE_MAX:
            _guard_cache.pop(next(iter(_guard_cache)))
        _guard_cache[key] = result
        return result
    logger.warning("Scope check skipped: no usable reply")
    return []
