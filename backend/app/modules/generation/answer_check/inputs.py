"""H4 of plan v2: the figures an answer says it took from the excerpts (`inputs` of its answer_meta block), checked against the excerpt
each one names. Code only, no model.

For each entry {"value", "item", "period", "excerpt"}:
  excerpt  the excerpt number exists
  value    the value is printed in THAT excerpt (when it is printed in another one instead, the problem says which)
  item     on a line of that excerpt that prints the value, the line's label (first cell of a table row, or the sentence) carries most words
           of the item, so a figure taken from the wrong row is caught even though the number itself is in the excerpts
  period   when the excerpt's table header has years and the value sits in a column, the column's year is one the period names

Measured in experiments/ before this module (h4_inputs.py, on entries built from about 300 stored answers): 0 false alarms on 751 correct
entries, also with reworded items; a wrong item, excerpt, period or value is caught 97.8-100 % of the time. Not yet measured on entries a
model writes itself, so the result goes to the trace and only triggers a rewrite when settings.ANSWER_INPUTS_REPAIR is on.
"""
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

STOP = {"the", "and", "of", "for", "from", "in", "to", "a", "an", "on", "at", "by", "with", "as", "per", "its", "their", "or", "total"}
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")  # also inside "FY2018"


def _words(text: str) -> Set[str]:
    return {w for w in re.findall(r"[a-z][a-z&'-]+", text.lower()) if w not in STOP and len(w) >= 3}


def _numbers(text: str) -> Set[float]:
    return {float(n.replace(",", "")) for n in NUMBER.findall(text.replace("$", ""))}


def _value(printed: Any) -> Optional[float]:
    found = NUMBER.findall(str(printed).replace("$", ""))
    return float(found[0].replace(",", "")) if found else None


def _tables(content: str) -> List[Tuple[List[List[str]], List[Tuple[str, List[str]]]]]:
    """[(header years by column, [(label, cells)])] of every Markdown table of an excerpt."""
    out, header, rows = [], None, []
    for line in content.splitlines() + [""]:
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            if header is None:
                header = [YEAR.findall(c) for c in cells]
            else:
                rows.append((cells[0] if cells else "", cells))
        elif header is not None:
            out.append((header, rows))
            header, rows = None, []
    return out


def _places(value: float, content: str) -> List[Tuple[str, Optional[str]]]:
    """[(label, column year or None)] of every place the excerpt prints `value`: table rows (label = first cell), else the sentence."""
    places = []
    for header, rows in _tables(content):
        for label, cells in rows:
            for j, cell in enumerate(cells[1:], 1):
                if value in _numbers(cell):
                    years = header[j] if j < len(header) else []
                    places.append((label, years[0] if len(years) == 1 else None))
    if not places:
        for sentence in re.split(r"(?<=[.;])\s+|\n", content):
            if not sentence.strip().startswith("|") and value in _numbers(sentence):
                places.append((sentence, None))
    return places


def _fit(item: Set[str], label: str) -> Tuple[float, float]:
    """(share of the item's words on the line, Jaccard of the two word sets): how well a line's label fits the item written."""
    words = _words(label)
    return (len(item & words) / len(item), len(item & words) / len(item | words)) if item and words else (0.0, 0.0)


def check_inputs(inputs: Sequence[Dict[str, Any]], chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[{"entry", "problem"}] for the entries that do not check (the problem is written as a rewrite instruction)."""
    problems: List[Dict[str, Any]] = []
    for e in inputs or []:
        n, v = e.get("excerpt"), _value(e.get("value"))
        if not isinstance(n, int) or not 1 <= n <= len(chunks):
            problems.append({"entry": e, "problem": f"excerpt {n} does not exist"})
            continue
        if v is None:
            problems.append({"entry": e, "problem": "an input has no value"})
            continue
        places = _places(v, chunks[n - 1].get("content", ""))
        if not places:
            elsewhere = [k for k, c in enumerate(chunks, 1) if _places(v, c.get("content", ""))]
            problems.append({"entry": e, "problem": f"{e.get('value')} is not printed in excerpt {n}" + (f"; it is in excerpt {elsewhere[0]}" if elsewhere else "; it is in no excerpt")})
            continue
        item = _words(str(e.get("item", "")))
        matching = [(label, year) for label, year in places if item and len(item & _words(label)) / len(item) >= 0.6]
        # another row of the excerpt fits the item better than every row holding the value: the figure was taken from the wrong row
        # ("Net loss attributable to the company" written for the value of "... to noncontrolling interests")
        best_other = max((_fit(item, label) for _, rows in _tables(chunks[n - 1].get("content", "")) for label, cells in rows
                          if not any(v in _numbers(c) for c in cells[1:])), default=(0.0, 0.0)) if item else (0.0, 0.0)
        if item and (not matching or best_other > max(_fit(item, label) for label, _ in matching)):
            problems.append({"entry": e, "problem": f"{e.get('value')} in excerpt {n} is on the line '{places[0][0][:80]}', not '{e.get('item')}'"})
            continue
        asked = set(YEAR.findall(str(e.get("period", ""))))
        column_years = {year for _, year in (matching or places) if year}
        if asked and column_years and not (asked & column_years):
            problems.append({"entry": e, "problem": f"{e.get('value')} in excerpt {n} sits in the {sorted(column_years)[0]} column, not {e.get('period')}"})
    return problems
