"""What the conversation is about (`notebooks.focus_state`) and how a short follow-up is completed from it. Pure rules: no model, no database.

The state keeps {document_ids, fiscal_years, metric}. Company names are read from the catalog when the state is used, so editing a catalog cannot
leave them stale, and a document that is no longer selected simply stops counting: the system never widens the scope by itself.
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from app.modules.query_router.catalog_route import STOP, company_matches, question_years, words

# key: (Vietnamese label, English label, how a question writes it). The first match wins, so specific items come before the general ones.
METRICS: Dict[str, tuple] = {
    "cost_of_revenue": ("giá vốn hàng bán", "cost of revenue", r"cost of (?:revenues?|sales|goods sold)|giá vốn"),
    "gross_margin": ("biên lợi nhuận gộp", "gross margin", r"gross (?:profit )?margin|biên (?:lợi nhuận |lãi )?gộp"),
    "operating_margin": ("biên lợi nhuận hoạt động", "operating margin", r"operating margin|biên lợi nhuận hoạt động"),
    "net_margin": ("biên lợi nhuận ròng", "net margin", r"net (?:profit )?margin|biên lợi nhuận ròng"),
    "gross_profit": ("lợi nhuận gộp", "gross profit", r"gross profit|lợi nhuận gộp|lãi gộp"),
    "operating_income": ("lợi nhuận hoạt động", "operating income", r"operating (?:income|profit)|income from operations|lợi nhuận (?:từ )?hoạt động"),
    "net_interest_income": ("thu nhập lãi thuần", "net interest income", r"net interest income|thu nhập lãi thuần"),
    "net_income": ("lợi nhuận ròng", "net income", r"net (?:income|earnings|profit)|lợi nhuận (?:ròng|sau thuế)|lãi ròng"),
    "eps": ("EPS", "EPS", r"\beps\b|earnings per share|lợi nhuận trên (?:mỗi )?cổ phiếu"),
    "ebitda": ("EBITDA", "EBITDA", r"\bebitda\b"),
    "sga": ("chi phí bán hàng và quản lý", "selling, general and administrative expenses", r"selling, general and administrative|\bsg&a\b|chi phí bán hàng và quản lý"),
    "research_and_development": ("chi phí nghiên cứu và phát triển", "research and development expenses", r"research and development|\br&d\b|chi phí nghiên cứu"),
    "interest_expense": ("chi phí lãi vay", "interest expense", r"interest expenses?|chi phí lãi vay"),
    "income_tax": ("thuế thu nhập", "income tax expense", r"income tax(?:es)?|thuế thu nhập"),
    "revenue": ("doanh thu", "revenue", r"\brevenues?\b|\bnet sales\b|\btotal sales\b|\bsales\b|doanh thu"),
    "current_assets": ("tài sản ngắn hạn", "current assets", r"current assets|tài sản ngắn hạn"),
    "total_assets": ("tổng tài sản", "total assets", r"total assets|tổng tài sản"),
    "current_liabilities": ("nợ ngắn hạn", "current liabilities", r"current liabilities|nợ ngắn hạn"),
    "total_liabilities": ("nợ phải trả", "total liabilities", r"total liabilities|nợ phải trả|tổng nợ"),
    "long_term_debt": ("nợ dài hạn", "long-term debt", r"long[- ]term debt|nợ dài hạn"),
    "total_equity": ("vốn chủ sở hữu", "total equity", r"(?:shareholders|stockholders)['’]? equity|total equity|vốn chủ sở hữu"),
    "cash": ("tiền và tương đương tiền", "cash and cash equivalents", r"cash and (?:cash )?equivalents|tiền và tương đương tiền"),
    "inventory": ("hàng tồn kho", "inventory", r"\binventor(?:y|ies)\b|hàng tồn kho"),
    "accounts_receivable": ("các khoản phải thu", "accounts receivable", r"(?:accounts|trade) receivables?|khoản phải thu"),
    "accounts_payable": ("các khoản phải trả", "accounts payable", r"(?:accounts|trade) payables?|khoản phải trả"),
    "goodwill": ("lợi thế thương mại", "goodwill", r"\bgoodwill\b|lợi thế thương mại"),
    "capex": ("chi đầu tư", "capital expenditure", r"capital expenditures?|\bcapex\b|chi (?:phí )?đầu tư"),
    "free_cash_flow": ("dòng tiền tự do", "free cash flow", r"free cash flow|\bfcf\b|dòng tiền tự do"),
    "operating_cash_flow": ("dòng tiền hoạt động", "operating cash flow", r"operating cash flow|cash (?:flow )?(?:provided by |from )operat\w+|dòng tiền (?:từ )?hoạt động"),
    "dividends": ("cổ tức", "dividends", r"\bdividends?\b|cổ tức"),
    "roe": ("ROE", "ROE", r"\broe\b|return on equity"),
    "roa": ("ROA", "ROA", r"\broa\b|return on assets"),
}
_METRIC = {key: re.compile(item[2], re.I) for key, item in METRICS.items()}
_QUARTER = re.compile(r"\bQ[1-4]\b|\bquarter\b|\bquý\b", re.I)
_PREVIOUS = re.compile(r"\b(?:the )?(?:year before|previous year|prior year|last year)\b|\ba year earlier\b|năm trước|năm ngoái|kỳ trước", re.I)
_COMPARE = re.compile(r"so với|compared|versus|\bvs\b", re.I)
_ANY_METRIC = re.compile("|".join(item[2] for item in METRICS.values()), re.I)
_YEAR_WRITTEN = re.compile(r"(?<![\d.,$])(?:fy\s?)?(?:19|20)\d{2}(?!\d)", re.I)
# What a bare follow-up may contain besides the item, company and period: anything else ("who audited it", "why did it fall") is a question of its own
_FILLER = frozenset("""
what was were is are the a an of for in about how much many and also but then so its their it please compared with to versus vs year before previous prior last fiscal
còn thế vậy và thì sao của năm là bao nhiêu về so với trước ngoái kỳ nó họ ạ nhé
""".split())


@dataclass
class Focus:
    companies: List[str]
    years: List[int]
    metric: Optional[str] = None


def metric_in(text: str) -> Optional[str]:
    return next((key for key, rx in _METRIC.items() if rx.search(text or "")), None)


def short_name(company: str) -> str:
    """The name as a person writes it: "PepsiCo, Inc." -> "PepsiCo", "The Coca-Cola Company" -> "Coca-Cola"."""
    parts = company.split()
    while len(parts) > 1 and parts[-1].strip(",.").lower() in STOP:
        parts.pop()
    while len(parts) > 1 and parts[0].lower() in STOP:
        parts.pop(0)
    return " ".join(parts).rstrip(",.")


def focus_view(state: Optional[Dict[str, Any]], document_ids: Sequence[str], sources: Sequence[Any]) -> Optional[Focus]:
    """The focus restricted to the documents selected now; None when none of its documents is still selected."""
    wanted = set((state or {}).get("document_ids") or [])
    companies = [s.company for d, s in zip(document_ids, sources) if d in wanted and s.company]
    if not companies:
        return None
    return Focus(list(dict.fromkeys(companies)), list(state.get("fiscal_years") or []), state.get("metric"))


def build_focus(question: str, document_ids: Sequence[str], fiscal_years: Dict[str, Optional[int]], previous: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The state after a searched question: what it does not say is kept from before."""
    ids = list(dict.fromkeys(document_ids))
    if not ids:
        return None
    years = sorted(question_years(question, ranges=True), reverse=True) or sorted({y for d in ids if (y := fiscal_years.get(d))}, reverse=True)
    return {"document_ids": ids, "fiscal_years": years, "metric": metric_in(question) or (previous or {}).get("metric")}


def _together(names: Sequence[str], vi: bool) -> str:
    return (" và " if vi else " and ").join(names)


def _only_slots(question: str, cards: Sequence[Dict[str, Any]], matches: Dict[int, int]) -> bool:
    """The question says nothing but an item, a company, a period and connecting words."""
    words_left = re.findall(r"[^\W_]+", _YEAR_WRITTEN.sub(" ", _ANY_METRIC.sub(" ", re.sub(r"['’]s\b", "", question))))
    named_words = {w for i in matches for w in words(cards[i].get("entity"))}  # "Coca" and "Cola" of Coca-Cola
    return all(w.lower() in _FILLER or w.lower() in named_words or set(company_matches(re.sub(rf"(?<!\w){re.escape(w)}(?!\w)", " ", question), cards)) != set(matches) for w in words_left)


def fill_from_focus(question: str, focus: Optional[Focus], sources: Sequence[Any], lang: str) -> Optional[str]:
    """A complete question from a short follow-up and the focus, in the question's language; None when the slots do not settle it (the model then rewrites it)."""
    if not focus or _QUARTER.search(question):
        return None
    vi = lang == "vi"
    cards = [{"entity": s.company or s.file_name, "aliases": s.aliases, "ticker": s.ticker} for s in sources]
    matches = company_matches(question, cards)
    if not _only_slots(question, cards, matches) or not (metric_in(question) or matches or question_years(question) or _PREVIOUS.search(question)):
        return None
    named = list(dict.fromkeys(sources[i].company for i in sorted(matches) if sources[i].company))
    companies = [short_name(c) for c in (named or focus.companies)]
    metric = metric_in(question) or focus.metric
    years = sorted(question_years(question), reverse=True) or focus.years
    if not metric or not companies or len(years) != 1:
        return None
    year, label = years[0], METRICS[metric][0 if vi else 1]
    if _PREVIOUS.search(question):
        if _COMPARE.search(question):
            return (f"So sánh {label} của {_together(companies, vi)} năm {year} với năm {year - 1}" if vi
                    else f"Compare the {label} of {_together(companies, vi)} in {year} with {year - 1}")
        year -= 1
    if len(companies) > 1:
        return f"So sánh {label} của {_together(companies, vi)} năm {year}" if vi else f"Compare the {label} of {_together(companies, vi)} in {year}"
    return f"{label[0].upper() + label[1:]} của {companies[0]} năm {year} là bao nhiêu?" if vi else f"What was the {label} of {companies[0]} in {year}?"
