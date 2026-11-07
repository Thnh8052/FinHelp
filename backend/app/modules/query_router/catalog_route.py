"""File routing by code, no LLM: the R5 rules and the "the selected documents do not have it" router, on catalog lines
(make_card.py --fields=slim: entity, aliases, doc_type, period, period_end, years_covered, fiscal_year, fiscal_quarter) or on the parsed
text. Rules as measured on the SEC multidoc set (fallback_eval.py `r5c_fix`, `r5text`; router_eval.py); reads only the question text.
"""
import re

STOP = {"inc", "corp", "corporation", "company", "co", "ltd", "limited", "plc", "the", "holdings", "group", "and", "&", "of", "international", "incorporated"}
COMMON = {"fy", "usd", "true", "false", "q1", "q2", "q3", "q4", "gaap", "eps", "ebitda", "capex", "sec", "ceo", "cfo"}
YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")  # not \b: "FY2015" has no word boundary before the year
QPAIR = re.compile(r"(q[1-4]|first|second|third|fourth)\s*(?:quarter)?\s*(?:of\s*)?(?:fiscal\s*(?:year\s*)?)?(?:fy)?\s*((?:19|20)\d{2})")
QNUM = {"q1": 1, "q2": 2, "q3": 3, "q4": 4, "first": 1, "second": 2, "third": 3, "fourth": 4}


def words(s):
    """Lower-case words, plus every run of single letters written together: "A.R.G.C. Limited" -> a, r, g, c, argc, limited."""
    s = re.sub(r"['’]s\b", "", (s or "").lower())  # possessive: "A.R.G.C.'s" -> "A.R.G.C."
    ws = re.findall(r"[a-z0-9&]+", s)
    runs = re.findall(r"(?:\b[a-z]\b[^a-z0-9&]*){2,}", s)
    return ws + ["".join(re.findall(r"[a-z]", r)) for r in runs]


def joined(ws):
    """Words plus every two neighbours written together: "WAL-MART STORES" -> wal, mart, walmart, ..."""
    return set(ws) | {a + b for a, b in zip(ws, ws[1:])}


def name_tokens(entity):
    return {w for w in joined(words(entity)) if w not in STOP and len(w) >= 3}


def names(card):
    """Name tokens of a catalog line: entity + aliases (+ joined neighbours) + the initials of a multi-word entity (amd) + the ticker
    the user confirmed. The one place a company name is normalised for matching (questions go through words())."""
    toks = name_tokens(card.get("entity")).union(*[name_tokens(a) for a in card.get("aliases") or []])
    initials = "".join(w[0] for w in words(card.get("entity")) if w not in STOP and len(w) >= 3)
    ticker = (card.get("ticker") or "").lower()
    return toks | ({initials} if len(initials) >= 3 else set()) | ({ticker} if len(ticker) >= 2 else set())


def years_of(card):
    """The year the period ends and the fiscal year the filing prints, when known."""
    m = YEAR.search(card.get("period") or "")
    return ({int(m[0])} if m else set()) | ({card["fiscal_year"]} if card.get("fiscal_year") else set())


YRANGE = re.compile(r"((?:19|20)\d{2})\s*(?:to|through|until|-|–|—)\s*(?:fy\s*|fiscal\s+(?:year\s+)?)?((?:19|20)\d{2})(?!\d)")


def question_years(question, ranges=False):
    """Years the question names; ranges: also the years inside "2023 to 2025" / "2023-2025" (a three-year trend needs 2024)."""
    ys = {int(y) for y in YEAR.findall(question)}
    if ranges:
        for a, b in YRANGE.findall(question.lower()):
            if 0 < int(b) - int(a) <= 10:
                ys |= set(range(int(a), int(b) + 1))
    return ys


def r5(question, ws, cards):
    """Filings the question names (name token in the question) and of the year it asks; a question naming no company but a year takes
    every filing of that year; a filing with no period is never dropped by the year. None: nothing named (caller falls back)."""
    ql, qy = set(words(question)), question_years(question, ranges=True)
    named = [d for d in ws if names(cards.get(d, {})) & ql]
    if not named:
        return [d for d in ws if years_of(cards.get(d, {})) & qy] or None
    if any(years_of(cards.get(d, {})) & qy for d in named):
        return [d for d in named if years_of(cards.get(d, {})) & qy or not years_of(cards.get(d, {}))]
    return named


def r5_text(question, ws, first_words, text_year):
    """R5 on the filing text, no catalog: capitalised question words (not the first word) found on the first two pages of at least
    one and at most a third of the filings, then the latest year heading the filing's tables. None: nothing found."""
    caps = re.findall(r"[A-Za-z&]*[A-Z][A-Za-z&]*", question)[1:]
    qwords = {w.lower() for w in caps if len(w) >= 3 and w.lower() not in COMMON}
    distinct = {w for w in qwords if 0 < sum(w in first_words.get(d, ()) for d in ws) <= max(1, len(ws) // 3)}
    named = [d for d in ws if distinct & first_words.get(d, set())]
    qy = question_years(question)
    yf = [d for d in ws if text_year.get(d) in qy]
    if not named:
        return yf or None
    return [d for d in named if d in yf] or named


def coverage(card):
    """Years with figures (table headers, period year, printed fiscal year); None = unknown, never used to refuse: no period (8-K), or
    no year read from the table headers (a scan whose columns read "30 4 09")."""
    m = YEAR.search(card.get("period") or "")
    if not m or not card.get("years_covered"):
        return None
    return set(card.get("years_covered") or []) | years_of(card)


def year_rule(question, ws, cards):
    """Missing years, then missing (quarter, fiscal year) pairs, among the filings of the companies the question names. A quarter is
    covered by that quarter's report or the annual report of that fiscal year; an unknown coverage or fiscal label never refuses."""
    ql, qy = set(words(question)), question_years(question)
    named = [d for d in ws if names(cards.get(d, {})) & ql]
    if not named or not qy:
        return []
    cov = [coverage(cards.get(d, {})) for d in named]
    if any(c is None for c in cov):
        return []
    missing = [y for y in sorted(qy) if not any(y in c for c in cov)]
    for qn, y in QPAIR.findall(question.lower()):
        cs = [cards.get(d, {}) for d in named]
        has = any(c.get("fiscal_year") == int(y) and c.get("fiscal_quarter") in (QNUM[qn], None) for c in cs)
        if not has and all(c.get("fiscal_year") for c in cs):
            missing.append(f"Q{QNUM[qn]} FY{y}")
    return missing


def company_rule(question, ws, texts):
    """Capitalised question words (not the first word) that appear nowhere in the text of the selected filings."""
    caps = re.findall(r"[A-Za-z&]*[A-Z][A-Za-z&]*", question)[1:]
    qwords = {w.lower() for w in caps if len(w) >= 3 and w.lower() not in COMMON}
    return sorted(w for w in qwords if not any(w in texts.get(d, ()) for d in ws))
