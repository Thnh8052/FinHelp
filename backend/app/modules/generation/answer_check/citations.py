"""Citation check, code only: every [n] an answer writes must point at an excerpt it was given.

Simplified 19/11 (owner: keep the final checks simple, report to the admin): the rules that guessed from the sentence which company, period or figure
a citation should cover were removed. On the 200 E2E planner answers of the week 12 audit, 10 of their 11 reports were false (a year named to
compare, "J&J" or "Sam's Club" not read as a company name, a total the answer adds up); a citation to an excerpt that does not exist is surely wrong.
"""
import re
from typing import Any, Dict, List, Sequence

CITE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")


def cited_numbers(answer: str) -> set:
    """The excerpt numbers an answer writes as [n] / [n, m] (the answer text only, without the v3 machine block)."""
    return {int(x) for m in CITE.finditer(answer) for x in re.split(r"\s*[,;]\s*", m.group(1))}


def check_citations(answer: str, chunks: Sequence[Dict[str, Any]], docs: Sequence[Any] = ()) -> Dict[str, List[int]]:
    """{"invalid": [n]}: the citations that point at no excerpt, in order of first appearance. `docs` is no longer read (kept for the callers)."""
    return {"invalid": sorted(n for n in cited_numbers(answer) if not 1 <= n <= len(chunks))}
