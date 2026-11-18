"""A2 citation check, code only: every [n] an answer writes must point at an excerpt it was given, the excerpt must come from the
company / period the sentence talks about (an AMD figure cited to an NVIDIA page is caught here, before the user sees it), and a figure written
before [n] must be printed in that excerpt when another excerpt prints it (numbers.figures_off_their_citation: "Its revenue was $60,922 million [1]"
names no company, so only its figure tells; 19/11).

A sentence names a company when a catalog name token of a source (catalog_route.names: entity, aliases, initials, ticker) is among
its words; it names a period when it writes a year. The excerpt matches the period when the year is printed in the excerpt or is a
year its document covers. Lenient on purpose: a sentence naming nothing is not checked.
"""
import re
from typing import Any, Dict, List, Sequence

from app.modules.generation.answer_check.numbers import figures_off_their_citation
from app.modules.query_router.catalog_route import company_key, names, question_years, words
from app.modules.query_router.target_scope import ScopeDoc

CITE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def cited_numbers(answer: str) -> set:
    """The excerpt numbers an answer writes as [n] / [n, m] (the answer text only, without the v3 machine block)."""
    return {int(x) for m in CITE.finditer(answer) for x in re.split(r"\s*[,;]\s*", m.group(1))}


def check_citations(answer: str, chunks: Sequence[Dict[str, Any]], docs: Sequence[ScopeDoc]) -> Dict[str, Any]:
    """{"invalid": [n], "wrong_company": [{"n", "sentence"}], "wrong_period": [{"n", "year", "sentence"}], "wrong_figure": [{"n", "figure", "sentence"}]}."""
    by_id = {d.document_id: d for d in docs}
    tokens = {d.document_id: names(d.card) for d in docs}
    out: Dict[str, List[Any]] = {"invalid": [], "wrong_company": [], "wrong_period": []}
    runs: List[Any] = []  # [(text, [n...])]: the text each run of adjacent markers closes ("[1][2]" and "[1, 2]" are one run)
    for sentence in SENTENCE.split(answer):
        # each [n] is checked against the text it closes: from the previous marker (or the sentence start) up to it, so in
        # "Intel ... 2023 [1]; Salesforce ... FY2024 [3]" the year 2024 belongs to [3] only; adjacent markers ([1][2]) share one text
        start, segment = 0, ""
        run = None
        for m in CITE.finditer(sentence):
            if sentence[start:m.start()].strip():
                segment = sentence[start:m.start()]
                run = (segment, [])
                runs.append(run)
            start = m.end()
            if run is not None:
                run[1].extend(int(x) for x in re.split(r"\s*[,;]\s*", m.group(1)))
            said = set(words(segment))
            named = {company_key(by_id[i].filing.company) for i, t in tokens.items() if t & said}
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
                if named and company_key(doc.filing.company) not in named:
                    out["wrong_company"].append({"n": n, "sentence": short})
                covered = set(doc.years_covered) | ({doc.filing.fiscal_year} if doc.filing.fiscal_year else set())
                for y in years:
                    if str(y) not in chunk.get("content", "") and covered and y not in covered:
                        out["wrong_period"].append({"n": n, "year": y, "sentence": short})
    out["wrong_figure"] = [{"n": n, "figure": figure, "sentence": clause} for n, figure, clause in figures_off_their_citation(answer, chunks, runs)]
    return out

