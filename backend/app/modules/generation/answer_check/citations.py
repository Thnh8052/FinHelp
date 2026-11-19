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


def _covers(chunk: Dict[str, Any], doc: ScopeDoc, year: int) -> bool:
    """The excerpt prints the year, its report covers it, or the report's years are unknown."""
    covered = set(doc.years_covered) | ({doc.filing.fiscal_year} if doc.filing.fiscal_year else set())
    return str(year) in chunk.get("content", "") or not covered or year in covered


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
                # the run before it in the sentence: "the FY2017 report [2] gives 18,434, the FY2019 report [1] ..." names the report before its figure
                run = (segment, [], run[1] if run is not None else [])
                runs.append(run)
            start = m.end()
            if run is not None:
                run[1].extend(int(x) for x in re.split(r"\s*[,;]\s*", m.group(1)))
            said = set(words(segment))
            named = {company_key(by_id[i].filing.company) for i, t in tokens.items() if t & said}
            for n in (int(x) for x in re.split(r"\s*[,;]\s*", m.group(1))):
                if not 1 <= n <= len(chunks):
                    out["invalid"].append(n)
                    continue
                doc = by_id.get(chunks[n - 1].get("document_id"))
                if doc is not None and named and company_key(doc.filing.company) not in named:
                    out["wrong_company"].append({"n": n, "sentence": segment.strip()[:160]})
    # a year of the text is checked against the excerpts cited together: "FY2015 ... and FY2020 ... [2][1]" cites each report for its own year
    # (live answer 19/11: checked marker by marker, both were reported)
    for segment, ns, before in runs:  # the run before it in the sentence counts too ("the FY2015 report [2] gives ... 2015, the FY2020 report [1] ...")
        cited = [(n, chunks[n - 1], by_id.get(chunks[n - 1].get("document_id"))) for n in ns + before if 1 <= n <= len(chunks)]
        cited = [(n, chunk, doc) for n, chunk, doc in cited if doc is not None]
        for y in question_years(segment):
            if cited and not any(_covers(chunk, doc, y) for _, chunk, doc in cited):
                out["wrong_period"] += [{"n": n, "year": y, "sentence": segment.strip()[:160]} for n, _, _ in cited if n in ns]
    out["wrong_figure"] = [{"n": n, "figure": figure, "sentence": clause} for n, figure, clause in figures_off_their_citation(answer, chunks, runs)]
    return out

