"""Checks of a written answer against its excerpts (A4 numbers, citations) and the note for what stays unverified."""
from typing import Any, Dict, List

from app.core.config import settings
from app.modules.generation.answer_check.citations import check_citations, problems
from app.modules.generation.answer_check.column_years import check_columns
from app.modules.generation.answer_check.formulas import check_formulas
from app.modules.generation.answer_check.inputs import check_inputs
from app.modules.generation.answer_check.numbers import check_numbers
from app.modules.query_router.target_scope import ScopeDoc
from app.modules.generation.generator import META_OPEN, split_answer


def verify(answer: str, chunks: List[Dict[str, Any]], docs: List[ScopeDoc]):
    """(A4 number check, citation check, problems as repair instructions)."""
    numbers = check_numbers(answer, chunks)
    text, meta = split_answer(answer)
    cites = check_citations(text, chunks, docs)
    # H4: the figures the answer says it took, checked against the excerpt each names; in the trace (numbers["inputs"]), a rewrite only when enabled
    numbers["inputs"] = check_inputs((meta or {}).get("inputs") or [], chunks)
    # TC-1: a figure stated for a year that the cited table prints under other years only
    numbers["columns"] = check_columns(text, chunks) if settings.COLUMN_CHECK_ENABLED else []
    # TC-4: a written step whose printed result is wrong, and a right division on the wrong formula (slice 1: a growth rate divided by the later period's value)
    numbers["formulas"] = check_formulas(text, chunks) if settings.FORMULA_CHECK_ENABLED else []
    issues = problems(numbers, cites) + [c["problem"] for c in numbers["columns"]] + [f["problem"] for f in numbers["formulas"]]
    if settings.ANSWER_INPUTS_REPAIR:
        issues += [p["problem"] for p in numbers["inputs"]]
    return numbers, cites, issues


def flag_unverified(answer: str, numbers: Dict[str, Any], cites: Dict[str, Any], lang: str) -> str:
    """What is still unverified after the repair, said in the answer (before the v3 machine block)."""
    vi = lang == "vi"
    parts = []
    if numbers.get("unverified"):
        parts.append(("số chưa kiểm chứng được trong đoạn trích: " if vi else "figures not verified in the excerpts: ") + ", ".join(numbers["unverified"]))
    if numbers.get("columns"):
        shown = ", ".join(f"{c['figure']} ({c['year']})" for c in numbers["columns"][:3])
        parts.append(("số nằm ở cột năm khác với năm được nêu: " if vi else "figures that sit in another year's column than the year stated: ") + shown)
    kinds = {f["kind"] for f in numbers.get("formulas") or []}
    if "arithmetic" in kinds:
        parts.append("có phép tính viết ra cho kết quả khác với kết quả đã ghi" if vi else "a written calculation does not give the result it states")
    if "growth_base" in kinds:
        parts.append("tốc độ tăng trưởng được chia cho số của kỳ sau thay vì kỳ trước" if vi else "a growth rate is divided by the later period's value instead of the earlier one")
    if cites["invalid"] or cites["wrong_company"] or cites["wrong_period"]:
        parts.append("có trích dẫn không khớp nguồn" if vi else "some citations do not match their source")
    line = "\n\n⚠️ " + ("Lưu ý: " if vi else "Note: ") + "; ".join(parts) + "."
    cut = answer.find(META_OPEN)
    return answer + line if cut < 0 else answer[:cut].rstrip() + line + "\n" + answer[cut:]
