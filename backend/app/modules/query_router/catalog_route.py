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
# Ordinary words of a financial question: never a company name on their own
QUESTION_WORDS = frozenset("""
how which what who whom whose when where why in on at of for by from to between among using based please compare calculate determine true false
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
# Words that are part of many company names but say nothing alone: "general and administrative" is not General Motors
ORDINARY = QUESTION_WORDS | frozenset("""
general american america americas national first united states home bank banks financial motor motors air airlines lines canada toronto delta
health care beauty water works foot square materials applied advanced micro devices systems intelligent platform platforms digital solar energy
gas oil power electric technology technologies software communications services solutions industries products global world pacific atlantic
north south east west southwest best buy target block gap visa chase wells mills martin johnson george being depot pdf key cat low fast gold pay bill
consolidated principal public progressive southern northern dollar service business management data supply payment payments instruments trust brands
one two third fifth new york ball news processing machines automatic storage booking parcel street tower apply shall inter
""".split())
PREFIX_MIN_LEN, PREFIX_MIN_COVER = 4, 0.7  # "Pepsi" covers 71 % of "pepsico", "Intel" only 62 % of "intelsat"
TYPO_MIN_LEN = 5  # one wrong letter, never the first (Meilisearch's rule for one typo)


def plain_words(s):
    s = re.sub(r"['’]s\b", "", (s or "").lower())  # possessive: "A.R.G.C.'s" -> "A.R.G.C."
    return re.findall(r"[a-z0-9&]+", s)


def words(s):
    """Lower-case words, plus every run of single letters written together: "A.R.G.C. Limited" -> a, r, g, c, argc, limited."""
    s = re.sub(r"['’]s\b", "", (s or "").lower())
    runs = re.findall(r"(?:\b[a-z]\b[^a-z0-9&]*){2,}", s)
    return plain_words(s) + ["".join(re.findall(r"[a-z]", r)) for r in runs]


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


def _one_edit(a, b):
    """The two different words are one letter apart: one replaced, added, removed, or two neighbours swapped."""
    i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return len(a) != len(b) and (a[i + 1:] == b[i:] or a[i:] == b[i + 1:]) or len(a) == len(b) and (a[i + 1:] == b[i + 1:] or a[i + 1] == b[i] and a[i] == b[i + 1] and a[i + 2:] == b[i + 2:])


def _written(code, question, plain):
    """A ticker or initials: in capitals when the same letters are an ordinary word ("KEY", "ALL"), in any case otherwise ("nvda")."""
    if code in ORDINARY or len(code) < 3:
        return bool(re.search(rf"(?<!\w){re.escape(code.upper())}(?!\w)", question))
    return code in plain


def _capitalised(toks, question):
    """A company whose whole name is ordinary words (Target, General Motors) needs capitals; a one-word name must also be inside the sentence or possessive."""
    name = r"\W+(?:(?:of|and|the|&)\W+)?".join(f"{t[0].upper()}(?i:{re.escape(t[1:])})" for t in toks)
    return bool(re.search(rf"\b{name}\b" if len(toks) > 1 else rf"(?<=\S\s){name}\b|\b{name}['’]s\b", question))


def _level(question, plain, grams, card):
    """How the question names this company: 1 full name, ticker or initials; 2 a distinctive word of the name; 3 a beginning of one; 4 one letter off; 0 no."""
    names_ = [n for n in [card.get("entity")] + list(card.get("aliases") or []) if n]
    initials = "".join(w[0] for w in words(card.get("entity")) if w not in STOP and len(w) >= 3)
    ticker = (card.get("ticker") or "").lower()
    if len(ticker) >= 2 and _written(ticker, question, plain) or len(initials) >= 3 and _written(initials, question, plain):
        return 1
    parts = [[w for w in plain_words(n) if w not in STOP] for n in names_]
    for toks in parts:
        if toks and all(t in ORDINARY for t in toks):
            if _capitalised(toks, question):
                return 1
        elif toks and "".join(toks) in grams:
            return 1
    distinctive = {w for n in names_ for w in words(n) if w not in STOP and w not in ORDINARY and len(w) >= 3}
    pairs = {a + b for toks in parts for a, b in zip(toks, toks[1:]) if a not in ORDINARY or b not in ORDINARY}  # "Wal-Mart" as "Walmart", not "bank" + "canada"
    # One word of a longer name is weak evidence: "instruments" is not Texas Instruments unless the writer capitalised it, and a capital at the
    # start of the sentence proves nothing unless the word begins the name. A question with no capitals at all says nothing either way.
    tokens = re.findall(r"[A-Za-z0-9&]+", re.sub(r"['’]s\b", "", question))
    capitals, first = {t.lower() for t in tokens if t != t.lower()}, tokens[0].lower() if tokens else ""
    casual, heads = question == question.lower(), {toks[0] for toks in parts if toks}
    if pairs & grams or any(t not in plain or casual or (t in capitals and (t in heads or t != first)) for t in distinctive & grams):
        return 2
    if any(len(toks) > 2 and _capitalised(toks[:2], question) for toks in parts):  # "Capital One" of Capital One Financial
        return 2
    asked = [w for w in plain if w not in ORDINARY and (casual or w in capitals)]
    if any(len(w) >= PREFIX_MIN_LEN and t.startswith(w) and len(w) / len(t) >= PREFIX_MIN_COVER for w in asked for t in distinctive):
        return 3
    if any(len(w) >= TYPO_MIN_LEN and w[0] == t[0] and w != t and _one_edit(w, t) for w in asked for t in distinctive):
        return 4
    return 0


def company_matches(question, cards):
    """{index of a card: level (see _level)} for the catalog lines the question names; the one place a question is matched to company names.
    A false match forces the search onto the wrong filing, a missed one leaves the choice to the planner, so anything doubtful is not a match.
    A word one letter off counts only when it points at a single company."""
    plain = [w for w in plain_words(question) if w not in STOP]
    grams = {"".join(plain[i:i + n]) for n in range(1, 5) for i in range(len(plain) - n + 1)} | set(words(question))
    found = {i: lv for i, c in enumerate(cards) if (lv := _level(question, plain, grams, c))}
    typos = {re.sub(r"[^a-z0-9]", "", (cards[i].get("entity") or "").lower()) for i, lv in found.items() if lv == 4}
    return {i: lv for i, lv in found.items() if lv < 4 or len(typos) == 1}


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


def named_docs(question, ws, cards):
    return [ws[i] for i in sorted(company_matches(question, [cards.get(d, {}) for d in ws]))]


def r5(question, ws, cards):
    """Filings the question names (name token in the question) and of the year it asks; a question naming no company but a year takes
    every filing of that year; a filing with no period is never dropped by the year. None: nothing named (caller falls back)."""
    qy = question_years(question, ranges=True)
    named = named_docs(question, ws, cards)
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
    qy = question_years(question)
    named = named_docs(question, ws, cards)
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
