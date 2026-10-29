"""A2 citation check, code only: every [n] an answer writes must point at an excerpt it was given, and the excerpt must come from the
company / period the sentence talks about (an AMD figure cited to an NVIDIA page is caught here, before the user sees it).

A sentence names a company when a catalog name token of a source (catalog_route.names: entity, aliases, initials, ticker) is among
its words; it names a period when it writes a year. The excerpt matches the period when the year is printed in the excerpt or is a
year its document covers. Lenient on purpose: a sentence naming nothing is not checked.
"""
import re
from typing import Any, Dict, List, Sequence

from app.services.query_router.catalog_route import names, question_years, words
from app.services.query_router.target_scope import ScopeDoc
from app.services.query_router.target_resolver import _key

CITE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def cited_numbers(answer: str) -> set:
    """The excerpt numbers an answer writes as [n] / [n, m] (the answer text only, without the v3 machine block)."""
    return {int(x) for m in CITE.finditer(answer) for x in re.split(r"\s*[,;]\s*", m.group(1))}


def check_citations(answer: str, chunks: Sequence[Dict[str, Any]], docs: Sequence[ScopeDoc]) -> Dict[str, Any]:
    """{"invalid": [n], "wrong_company": [{"n", "sentence"}], "wrong_period": [{"n", "year", "sentence"}]}."""
    by_id = {d.document_id: d for d in docs}
    tokens = {d.document_id: names(d.card) for d in docs}
    out: Dict[str, List[Any]] = {"invalid": [], "wrong_company": [], "wrong_period": []}
    for sentence in SENTENCE.split(answer):
        # each [n] is checked against the text it closes: from the previous marker (or the sentence start) up to it, so in
        # "Intel ... 2023 [1]; Salesforce ... FY2024 [3]" the year 2024 belongs to [3] only; adjacent markers ([1][2]) share one text
        start, segment = 0, ""
        for m in CITE.finditer(sentence):
            segment = sentence[start:m.start()] if sentence[start:m.start()].strip() else segment
            start = m.end()
            said = set(words(segment))
            named = {_key(by_id[i].filing.company) for i, t in tokens.items() if t & said}
            years = question_years(segment)
            for n in (int(x) for x in re.split(r"\s*[,;]\s*", m.group(1))):
                if not 1 <= n <= len(chunks):
                    out["invalid"].append(n)
                    continue
                chunk = chunks[n - 1]
                doc = by_id.get(chunk.get("document_id"))
                if doc is None:
                    continue
                short = segment.strip()[:160]
                if named and _key(doc.filing.company) not in named:
                    out["wrong_company"].append({"n": n, "sentence": short})
                covered = set(doc.years_covered) | ({doc.filing.fiscal_year} if doc.filing.fiscal_year else set())
                for y in years:
                    if str(y) not in chunk.get("content", "") and covered and y not in covered:
                        out["wrong_period"].append({"n": n, "year": y, "sentence": short})
    return out


def problems(numbers: Dict[str, Any], cites: Dict[str, Any]) -> List[str]:
    """The issues as instructions for the one repair call (empty: the answer passes)."""
    out = []
    if numbers.get("unverified"):
        out.append("these figures are not printed in the excerpts and do not follow from figures that are: " + ", ".join(numbers["unverified"]))
    if cites["invalid"]:
        out.append("these citation numbers point at no excerpt: " + ", ".join(f"[{n}]" for n in sorted(set(cites["invalid"]))))
    for w in cites["wrong_company"]:
        out.append(f"excerpt [{w['n']}] is from a different company than the sentence says: \"{w['sentence']}\"")
    for w in cites["wrong_period"]:
        out.append(f"excerpt [{w['n']}] does not cover {w['year']}: \"{w['sentence']}\"")
    return out
