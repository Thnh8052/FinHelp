"""G3: which of the selected documents a question is about, decided by code (no model call).

1. @file mentions (sent as document ids, not parsed from the text) are the strongest signal: exactly those documents. A company or
   year in the text that the tagged documents do not have is not a reason to stop: the answer covers the tagged documents and says
   what it could not cover.
2. Otherwise the companies the question names (catalog names: entity, aliases, initials, ticker; catalog_route.names) and its years
   go through target_resolver.resolve. Several documents for one target -> a default by rule (latest period; resolve already
   prefers the 10-K), stated in `understood`, with the other documents as `alternatives`. Never a blocking question.
3. No company named: no decision here (the planner chooses among the selected documents, with the safety net).
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from app.services.query_router.catalog_route import QNUM, QPAIR, names, question_years, words
from app.services.query_router.target_resolver import Filing, Target, _key, alignment_note, resolve

FISCAL = re.compile(r"\bfy\s?\d{2,4}\b|\bfiscal\b|năm tài chính", re.I)
CALENDAR = re.compile(r"\bcalendar\b|năm dương lịch", re.I)
# "a year earlier" / "prior year" next to a named year also needs the year before (the earlier report)
RELATIVE = re.compile(r"\b(?:a|one) year (?:earlier|before|ago)\b|\b(?:previous|prior|preceding) (?:fiscal )?year\b|\bthe year before\b|"
                      r"\byear[- ]over[- ]year\b|\byoy\b|năm trước|cùng kỳ năm", re.I)
ACRONYM = re.compile(r"[A-Z][A-Z&.]{1,5}")  # "TD", "RBC", "P&G": the shape of an abbreviated company name
# a report type the question names: only that type of the company's documents, when it has one
FORMS = {"8-K": re.compile(r"\b8-?K\b", re.I), "10-Q": re.compile(r"\b10-?Q\b", re.I), "10-K": re.compile(r"\b10-?K\b", re.I),
         "earnings release": re.compile(r"\b(?:earnings|press) release\b", re.I)}


@dataclass
class ScopeDoc:
    document_id: str
    label: str  # "Company | form | FY2024" (orchestrator.document_label)
    card: Dict  # orchestrator.catalog_card (entity, aliases, ticker, ...)
    filing: Filing
    years_covered: List[int] = field(default_factory=list)


@dataclass
class TargetDecision:
    document_ids: List[str] = field(default_factory=list)  # documents the search is forced to; empty = the planner chooses
    understood: str = ""  # shown above the answer
    alternatives: List[Dict[str, str]] = field(default_factory=list)  # [{"document_id", "label"}] other documents that also match
    notes: List[str] = field(default_factory=list)  # for the answer prompt
    rule: str = "none"  # mentions | resolved | none
    uncertain: bool = False  # the question also writes names no selected document's catalog carries: the other documents get the safety net


def _named(question: str, docs: Sequence[ScopeDoc]) -> List[ScopeDoc]:
    asked = set(words(question))
    return [d for d in docs if names(d.card) & asked]


def _understood(docs: Sequence[ScopeDoc], vi: bool, extra: str = "") -> str:
    listed = "; ".join(d.label for d in docs)
    return (f"Tôi hiểu câu hỏi về: {listed}." if vi else f"I understood the question as about: {listed}.") + (f" {extra}" if extra else "")


def _hint(vi: bool) -> str:
    return ("End the answer with one short sentence telling the user that if this is not what they meant, they can tag the right file "
            "with @ or name the company / year." + (" Write that sentence in Vietnamese." if vi else ""))


def from_mentions(question: str, docs: Sequence[ScopeDoc], mentions: Sequence[str], vi: bool) -> TargetDecision:
    tagged = [d for d in docs if d.document_id in set(mentions)]
    tagged_keys = {_key(d.filing.company) for d in tagged}
    others = sorted({d.card.get("entity") or d.label for d in _named(question, docs) if _key(d.filing.company) not in tagged_keys})
    covered = {y for d in tagged for y in ([d.filing.fiscal_year] if d.filing.fiscal_year else []) + d.years_covered}
    missing_years = sorted(y for y in question_years(question) if covered and y not in covered)
    gaps = others + [f"FY{y}" for y in missing_years]
    out = TargetDecision([d.document_id for d in tagged], rule="mentions")
    if gaps:
        what = ", ".join(gaps)
        out.understood = _understood(tagged, vi, (f"(Câu hỏi nhắc {what}, nhưng không có trong file được tag.)" if vi else
                                                  f"(The question mentions {what}, which the tagged files do not cover.)"))
        out.notes.append(f"Answer ONLY for the tagged sources ({'; '.join(d.label for d in tagged)}). The question also mentions {what}, which "
                         f"the tagged sources do not cover: say so in one sentence, without figures for it.")
        out.notes.append(_hint(vi))
    else:
        out.understood = _understood(tagged, vi)
        out.notes.append(f"The user tagged these sources: {'; '.join(d.label for d in tagged)}. Answer for them.")
    return out


def _unknown_names(question: str, docs: Sequence[ScopeDoc]) -> bool:
    """Capitalised terms (not ordinary words) that no selected document's catalog names: "TD" when the catalog only says
    "The Toronto-Dominion Bank" and no ticker was confirmed."""
    from app.services.query_router.planner import CatalogEntry, name_candidates  # local import: planner imports the LLM client

    known = set().union(*(names(d.card) for d in docs)) if docs else set()
    terms = name_candidates(question, [CatalogEntry(d.document_id, d.filing.company, d.filing.form, "", "") for d in docs])
    return any(ACRONYM.fullmatch(t) and not (set(words(t)) & known) for t in terms)


def from_names(question: str, docs: Sequence[ScopeDoc], vi: bool) -> TargetDecision:
    named = _named(question, docs)
    if not named:
        return TargetDecision()
    by_id = {d.document_id: d for d in docs}
    basis = "fiscal" if FISCAL.search(question) else ("calendar" if CALENDAR.search(question) else "unspecified")
    pairs = list(dict.fromkeys((int(y), QNUM[q]) for q, y in QPAIR.findall(question.lower())))  # (year, quarter), several per question
    years = set(question_years(question, ranges=True))
    if RELATIVE.search(question):
        years |= {y - 1 for y in years}
    annual = sorted(years - {y for y, _ in pairs}) or ([None] if not pairs else [])
    companies = list(dict.fromkeys(d.filing.company for d in named))
    targets = [Target(c, y, basis, q) for c in companies for y, q in pairs] + [Target(c, y, basis) for c in companies for y in annual]
    forms = [f for f, rx in FORMS.items() if rx.search(question)]
    has_form = {_key(d.filing.company) for d in docs if d.filing.form in forms}
    filings = [d.filing for d in docs if not forms or _key(d.filing.company) not in has_form or d.filing.form in forms]
    chosen, alternatives, assumptions = [], [], []
    for r in resolve(targets, filings):
        ids = [i for i in r.document_ids if i in by_id]
        if not ids and r.target.year and r.target.quarter is None:  # no report of that year: the earliest later report of the company that shows it (comparative column)
            later = sorted((d for d in docs if _key(d.filing.company) == _key(r.target.company) and r.target.year in d.years_covered),
                           key=lambda d: d.filing.fiscal_year or 0)
            if later:
                ids = [later[0].document_id]
                assumptions.append(f"FY{r.target.year} " + (f"lấy từ cột so sánh của {later[0].label}" if vi else f"from the comparative column of {later[0].label}"))
        if not ids:
            continue  # period missing: input_policy refuses years no source covers; the answer says what it lacks
        if len(ids) > 1:
            ids.sort(key=lambda i: (by_id[i].filing.fiscal_year or 0, by_id[i].filing.period_end or ""), reverse=True)
            alternatives += [i for i in ids[1:] if i not in alternatives]
            assumptions.append(f"{by_id[ids[0]].label} " + ("(mới nhất trong các file khớp)" if vi else "(the latest of the matching files)"))
        elif r.rule == "no year: latest filing" and sum(1 for d in docs if _key(d.filing.company) == _key(r.target.company)) > 1:
            assumptions.append(f"{by_id[ids[0]].label} " + ("(câu hỏi không nêu năm: lấy kỳ mới nhất)" if vi else "(no year asked: the latest period)"))
            alternatives += [d.document_id for d in docs if _key(d.filing.company) == _key(r.target.company) and d.document_id != ids[0]]
        if ids[0] not in chosen:
            chosen.append(ids[0])
    if not chosen:
        return TargetDecision()
    out = TargetDecision(chosen, rule="resolved", uncertain=_unknown_names(question, docs),
                         alternatives=[{"document_id": i, "label": by_id[i].label} for i in alternatives if i not in chosen])
    note = alignment_note(resolve(targets, filings), filings, vi)
    extra = " ".join(x for x in (("Giả định: " if vi else "Assumed: ") + "; ".join(assumptions) + "." if assumptions else "", note) if x)
    out.understood = _understood([by_id[i] for i in chosen], vi, extra)
    out.notes.append(f"The question is about these sources: {'; '.join(by_id[i].label for i in chosen)}. Answer for them.")
    if assumptions:
        out.notes.append("State the assumption in one short sentence at the start: " + "; ".join(assumptions) + ".")
        out.notes.append(_hint(vi))
    if note:
        out.notes.append("Say how the fiscal years were aligned: " + note)
    return out


def decide_targets(question: str, docs: Sequence[ScopeDoc], mentions: Optional[Sequence[str]], vi: bool) -> TargetDecision:
    if mentions:
        return from_mentions(question, docs, mentions, vi)
    return from_names(question, docs, vi)
