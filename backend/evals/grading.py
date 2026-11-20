"""Machine grading of an answer against the answer spec of the gold question (numbers written in the answer, listed items, ranking order, abstention).
A screen, not the owner's hand grading: it reads the figures, not the reasoning. Ported from experiments/scripts/gold_v2/e2e_grade_v2.py (numbers_of and the numeric rule come from
experiments/scripts/rag_improvement/lazy_net_e2e.py)."""
import re

STOP = {"the", "and", "of", "a", "an", "in", "for", "to", "its", "is", "was", "were", "with", "by", "on", "as", "at", "or", "from", "that", "this"}
MISSING = re.compile(r"not (?:included|in the|among|available|covered|part of|provided|found)|no (?:filing|data|report|information|figures?)|cannot be (?:answered|determined|compared|provided)|"
                     r"(?:does|do) not (?:include|contain|cover|have)|isn't (?:included|available)|is not (?:one of|among)|không có|không được|không tìm thấy", re.I)


def numbers_of(text):
    out = set()
    for m in re.finditer(r"(\d[\d,]*\.?\d*)\s*(billion|bn|million|%)?", text.replace("$", " "), re.I):
        try:
            v = float(m.group(1).replace(",", "").rstrip("."))
        except ValueError:
            continue
        out.add(v)
        if (m.group(2) or "").lower() in ("billion", "bn"):
            out.add(v * 1000)
    return out


def _tolerance(spec, key, target):
    units = (spec or {}).get("units") or {}
    if units.get(key) == "percent" or "pct" in key:
        return max((spec.get("abs_tol_pp") or 0.1), 0.06)
    return max((spec.get("rel_tol") or 0.01) * abs(target), 0.5)


def grade_values(text, spec):
    """True when every numeric value of the spec is written in the text (sign not compared); None when the spec has no number."""
    vals = {k: v for k, v in ((spec or {}).get("values") or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if not vals:
        return None
    found = numbers_of(text)
    return all(any(abs(c - abs(t)) <= _tolerance(spec, k, t) for c in found) for k, t in vals.items())


def _words(s):
    return [w for w in re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", s.lower().replace(",", "")) if w not in STOP and (len(w) >= 3 or w.isdigit())]


def grade_items(text, spec, share=0.6):
    """True when every must_include item has at least `share` of its key words in the text; None without items."""
    items = (spec or {}).get("must_include") or []
    if not items:
        return None
    have = set(_words(text))
    return all(sum(w in have for w in _words(it)) >= share * max(1, len(_words(it))) for it in items)


def grade_ranking(text, spec):
    """The values are all written and appear in the order of the spec."""
    if not grade_values(text, spec):
        return False
    clean = text.replace("$", " ")
    pos = []
    for key in spec["order"]:
        t = spec["values"][key]
        tol = _tolerance(spec, key, t)
        hit = next((m.start() for m in re.finditer(r"\d[\d,]*\.?\d*", clean) if _num(m.group(0)) is not None and abs(_num(m.group(0)) - abs(t)) <= tol), None)
        pos.append(hit)
    return all(p is not None for p in pos) and pos == sorted(pos)


def _num(s):
    try:
        return float(s.replace(",", "").rstrip("."))
    except ValueError:
        return None


def grade_abstain(text, status):
    """The answer says the data is not in the sources (status not_found / partial, or an explicit statement). A figure for the missing part is checked by hand."""
    return status in ("not_found", "partial") or bool(MISSING.search(text or ""))


def grade(q, text, status):
    spec = q["answer_spec"]
    kind = spec.get("answer_type")
    if q.get("behavior") == "clarify_or_answer_all" and status == "clarify":
        return True
    if kind == "abstain":
        return grade_abstain(text, status)
    if kind == "ranking":
        return grade_ranking(text, spec)
    if kind in ("list", "text"):
        return grade_items(text, spec)
    return grade_values(text, spec)


