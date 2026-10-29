"""Checks of a written answer against its excerpts (A4 numbers, citations) and the note for what stays unverified."""
from typing import Any, Dict, List

from app.services.answer_check.citations import check_citations, problems
from app.services.answer_check.numbers import check_numbers
from app.services.query_router.target_scope import ScopeDoc
from app.services.rag_workflow.generator import META_OPEN, split_answer


def verify(answer: str, chunks: List[Dict[str, Any]], docs: List[ScopeDoc]):
    """(A4 number check, citation check, problems as repair instructions)."""
    numbers = check_numbers(answer, chunks)
    cites = check_citations(split_answer(answer)[0], chunks, docs)
    return numbers, cites, problems(numbers, cites)


def flag_unverified(answer: str, numbers: Dict[str, Any], cites: Dict[str, Any], lang: str) -> str:
    """What is still unverified after the repair, said in the answer (before the v3 machine block)."""
    vi = lang == "vi"
    parts = []
    if numbers.get("unverified"):
        parts.append(("số chưa kiểm chứng được trong đoạn trích: " if vi else "figures not verified in the excerpts: ") + ", ".join(numbers["unverified"]))
    if cites["invalid"] or cites["wrong_company"] or cites["wrong_period"]:
        parts.append("có trích dẫn không khớp nguồn" if vi else "some citations do not match their source")
    line = "\n\n⚠️ " + ("Lưu ý: " if vi else "Note: ") + "; ".join(parts) + "."
    cut = answer.find(META_OPEN)
    return answer + line if cut < 0 else answer[:cut].rstrip() + line + "\n" + answer[cut:]
