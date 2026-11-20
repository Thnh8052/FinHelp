"""The free checks: no model, no GPU, no network, no database. Each returns plain numbers that `python -m evals` compares with the committed baseline.

  input_layer   the input rules (input_policy.decide) on the 200 gold questions, with the question's reports as the selected sources
  security      the code layers of the guardrails (gate.screen, input rules, output checks, document flags) on the P1 set written after the code was frozen
  search        how often the evidence pages were in the excerpts (stored search, page rule)
  failures      for every question the gold wants answered: where it was lost, search or writing (failure_kind)
"""
from collections import Counter, defaultdict
from typing import Dict, Optional

from app.modules.generation.answer_check import policy, review
from app.modules.query_router.gate import screen
from app.modules.query_router.input_policy import TERMINAL, SourceInfo, decide, instruction_like

from . import gold, grading, security_set as S

ANSWERABLE = {"answer", "answer_latest", "answer_all", "clarify_or_answer_all"}
PERIOD_REFUSALS = {"period_unavailable", "form_unavailable"}
GOING_ON = {"proceed", "ask_clarify", "rewrite_followup", "answer_per_source_and_ask", "split_questions"}  # the question would be searched and answered
AMAZON = [SourceInfo("Amazon.com, Inc.", "10-K", 2019, None, "Amazon.com, Inc. | 10-K | FY2019")]
EXCERPTS = [{"chunk_id": "c", "document_id": "amzn", "page": 37,
             "content": "Total net sales 2019 280,522 2017 177,866. Operating income 14,541. Investor Relations: ir@amazon.com, (206) 266-2171."}]


def failure_kind(evidence_complete: bool, answer_correct: Optional[bool]) -> str:
    """Where a question was lost. ok: right with every evidence page in the excerpts. lucky: right although a page was missing. writing: every page was there and the
    answer is wrong (the writer's fault: definition, formula, wrong line). retrieval: a page was missing and the answer is wrong. unscored: the grader has no number to read."""
    if answer_correct is None:
        return "unscored"
    if answer_correct:
        return "ok" if evidence_complete else "lucky"
    return "writing" if evidence_complete else "retrieval"


def failure_table(question_rows: Dict[str, dict], search: Dict[str, dict], graded: Dict[str, Optional[bool]]) -> dict:
    """{"questions", "by_kind", "by_split"} over the questions the gold wants answered that have both a search result and a graded answer."""
    by_kind, by_split = Counter(), defaultdict(Counter)
    for qid, q in question_rows.items():
        if q["behavior"] not in ANSWERABLE or qid not in search or qid not in graded:
            continue
        kind = failure_kind(search[qid]["comp"], graded[qid])
        by_kind[kind] += 1
        by_split[q["split"]][kind] += 1
    return {"questions": sum(by_kind.values()), "by_kind": dict(by_kind), "by_split": {s: dict(c) for s, c in by_split.items()}}


def source_of(doc: str, meta: dict) -> SourceInfo:
    fy, company = meta.get("fiscal_year"), meta.get("company_name") or ""
    return SourceInfo(company, meta.get("report_type") or "", fy, meta.get("fiscal_quarter"), f"{company or doc} | {meta.get('report_type') or ''} | FY{fy}",
                      0, f"{doc}.pdf", list(meta.get("years_covered") or []), list(meta.get("aliases") or []), meta.get("ticker"))


def input_layer() -> dict:
    """Every gold question through input_policy.decide. An answerable question must not be stopped; a "not available" one must be refused for its period or form."""
    out = Counter()
    for q in gold.questions().values():
        sources = [source_of(d, gold.catalog()[d]) for d in q["workspace"]]
        action = decide(q["question"], sources, len(sources)).action
        if q["behavior"] in ANSWERABLE:
            out["answerable"] += 1
            out["answerable_false_refusals"] += action in TERMINAL
        elif q["behavior"] == "not_available":
            out["not_available"] += 1
            out["not_available_refused_right"] += action in PERIOD_REFUSALS
    return dict(out)


def _stopped_by_code(message: str) -> bool:
    """The gate, then the input rules on the clean text: what chat._answered does before the guard (a model) is asked."""
    screened = screen(message)
    return bool(screened.action) or decide(screened.clean, AMAZON, 1).action not in GOING_ON


def security() -> dict:
    """The P1 set (written 20/11 after the code of the guardrails was frozen). Direct attacks the design leaves to code, tricky legitimate questions (none may be
    refused), bad answers through the output checks, hidden text in reports."""
    expected = [m for _, _, layer, m in S.DIRECT if layer == "code"]
    stopped_code = sum(_stopped_by_code(m) for m in expected)
    stopped_all = sum(_stopped_by_code(m) for _, _, _, m in S.DIRECT)
    legit_refused = [q for q in S.LEGIT if _stopped_by_code(q)]
    bad = good = bad_stopped = good_left = 0
    for _, _, answer, expect in S.BAD_ANSWERS:
        cleaned = policy.clean(answer, EXCERPTS)
        found = review.run_checks(cleaned, EXCERPTS, [], "vi" if policy._VIETNAMESE.search(answer) else "en", figures=False)
        stop = review.has_hard(found) or cleaned != answer
        if expect == "stop":
            bad, bad_stopped = bad + 1, bad_stopped + stop
        else:
            good, good_left = good + 1, good_left + (not stop)
    return {"direct": len(S.DIRECT), "direct_stopped_by_code": stopped_all, "code_expected": len(expected), "code_expected_stopped": stopped_code,
            "legit": len(S.LEGIT), "legit_refused": len(legit_refused), "bad_answers": bad, "bad_answers_stopped": bad_stopped, "good_answers": good, "good_answers_left": good_left,
            "planted_text": len(S.PLANTED), "planted_text_flagged": sum(bool(instruction_like(t)) for t in S.PLANTED), "report_text": len(S.REPORT_TEXT),
            "report_text_wrongly_flagged": sum(bool(instruction_like(t)) for t in S.REPORT_TEXT)}


def search_summary(search: Dict[str, dict]) -> dict:
    rows = list(search.values())
    return {"scored": len(rows), "evidence_complete": sum(r["comp"] for r in rows),
            "evidence_complete_pct": round(100 * sum(r["comp"] for r in rows) / len(rows), 1) if rows else 0.0}


def answers_graded(question_rows: Dict[str, dict], answers: Dict[str, dict]) -> Dict[str, Optional[bool]]:
    return {qid: grading.grade(question_rows[qid], a.get("answer") or "", a.get("status")) for qid, a in answers.items() if qid in question_rows}


def run_free(search: Optional[Dict[str, dict]] = None, answers: Optional[Dict[str, dict]] = None) -> dict:
    """All the free checks. `search` and `answers` default to the committed stored runs; pass a fresh run's (gold.load_search / gold.load_answers) to score that."""
    qs = gold.questions()
    search = gold.search_snapshot() if search is None else search
    answers = gold.answer_snapshot() if answers is None else answers
    graded = answers_graded(qs, answers)
    failures = failure_table(qs, search, graded)
    scored = [g for qid, g in graded.items() if qs[qid]["behavior"] in ANSWERABLE and g is not None]
    return {"input_layer": input_layer(), "security": security(), "search": search_summary(search), "failures": failures,
            "answers": {"graded": len(scored), "machine_correct": sum(scored), "machine_correct_pct": round(100 * sum(scored) / len(scored), 1) if scored else 0.0}}
