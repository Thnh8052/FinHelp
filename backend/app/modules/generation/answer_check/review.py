"""The review of a written answer (docs/Version_3/RAG_REDESIGN_SPEC.md section 4). Every check returns Findings of one shape; the orchestrator writes
the answer ONCE, then blocks it (a hard finding) or shows it with one "⚠️" line for what is still wrong (annotate). Code only, no model.
The one rewrite was removed 19/11 (T4, owner's decision of 18/11): it cost 4-54 s and 2 of 3 rewritten answers were right already.

Checks (each reuses the module that measures it):
  safety     policy.py: investment advice, its own instructions, internal names, foul language        hard: the fixed reply instead (policy.blocked)
  language   policy.py: answer not in the question's language                                          repairable: kept in the trace, no line
  arithmetic calculations.wrong_steps: a written step whose printed result is wrong                    repairable: the "⚠️" line
  figure     numbers.check_numbers: a figure neither printed in the excerpts nor derived from them     repairable: the "⚠️" line lists it
  citation   citations.check_citations: [n] to no excerpt, to another company or period, or [n]       repairable: the "⚠️" line
             after a figure only another excerpt prints
  status     policy.py: an answered status with no [n] at all                                         note: kept in the trace only
The notes of the findings (what was wrong, the right result) stay for the trace. Measured on 923 stored answers: every planted wrong written result is
caught; 42 answers have a repairable finding (4 of them graded correct), see experiments/scripts/system_test_18_11.
"""
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Sequence

from app.modules.generation.answer_check import policy
from app.modules.generation.answer_check.calculations import NUMTOK, SINGLE, evaluate, holds, is_calc, readings_of, steps, wrong_steps
from app.modules.generation.answer_check.citations import check_citations
from app.modules.generation.answer_check.numbers import check_numbers
from app.modules.generation.generator import META_OPEN, split_answer

HARD, REPAIRABLE, NOTE = "hard", "repairable", "note"
NEAR = 0.05  # a result the answer computed, within 5 % of an unverified figure of the same kind (percent or not), is named in that figure's note


@dataclass
class Finding:
    check: str  # safety | language | arithmetic | figure | citation | status
    severity: str  # hard | repairable | note
    text: str  # what the answer printed ("$99,999", "[7]", "(a − b) ÷ b = 20.0%"); empty for a whole-answer problem
    note: str  # what the one rewrite is told, pointed at the spot


def _computed(answer: str) -> List[tuple]:
    """[(result as printed, value)] of the answer's written steps whose result is right: the figures it computed itself."""
    loc = readings_of(answer)[0]
    out = []
    for left, right, _ in steps(answer):
        if is_calc(left) and SINGLE.fullmatch(right) and holds(left, right, loc):
            value = evaluate(right, loc)
            if value is not None:
                out.append((right.replace("**", "").strip(), value[0]))
    return out


def run_checks(answer: str, chunks: Sequence[Dict[str, Any]], docs: Sequence[Any], lang: str, policy_checks: bool = True, figures: bool = True) -> List[Finding]:
    """Every finding of `answer`. `policy_checks` False leaves out safety, language and status (OUTPUT_POLICY_ENABLED); `figures` False leaves out the
    arithmetic, figure and citation checks (the overview and previous-citation answers, which were never checked for them)."""
    found: List[Finding] = []
    if policy_checks:
        for p in policy.check(answer, chunks, lang):
            check, severity = ("safety", HARD) if p.hard else (("language", REPAIRABLE) if p.kind == "wrong_language" else ("status", NOTE))
            found.append(Finding(check, severity, "", p.fix))
    if not figures:
        return found
    wrong = wrong_steps(answer)
    reported = set()
    for left, shown, right_result in wrong:
        token = NUMTOK.search(shown)
        reported.add(token.group(0) if token else shown)
        found.append(Finding("arithmetic", REPAIRABLE, f"{left} = {shown}",
                             f"the written step \"{left} = {shown}\" is wrong: {left} = {right_result}; correct it and every figure that depends on it"))
    computed = _computed(answer)
    for figure in check_numbers(answer, chunks)["unverified"]:
        token = NUMTOK.search(figure)
        if (token.group(0) if token else figure) in reported:
            continue  # the arithmetic finding already says what is wrong and what is right
        note = f"the figure {figure} is not printed in the excerpts and does not follow from figures that are"
        value = evaluate(figure)
        if value is not None:
            percent = figure.rstrip().endswith("%")
            close = {r for r, v in computed if r.endswith("%") == percent and v and r != figure and abs(abs(value[0]) - abs(v)) / abs(v) <= NEAR}
            if len(close) == 1:
                note += f"; your own calculation in this answer gives {close.pop()}"
        found.append(Finding("figure", REPAIRABLE, figure, note))
    text, _ = split_answer(answer)
    cites = check_citations(text, chunks, docs)
    for n in sorted(set(cites["invalid"])):
        found.append(Finding("citation", REPAIRABLE, f"[{n}]", f"citation [{n}] points at no excerpt"))
    for w in cites["wrong_company"]:
        found.append(Finding("citation", REPAIRABLE, f"[{w['n']}]", f"excerpt [{w['n']}] is from a different company than the sentence says: \"{w['sentence']}\""))
    for w in cites["wrong_period"]:
        found.append(Finding("citation", REPAIRABLE, f"[{w['n']}]", f"excerpt [{w['n']}] does not cover {w['year']}: \"{w['sentence']}\""))
    for w in cites["wrong_figure"]:
        found.append(Finding("citation", REPAIRABLE, f"[{w['n']}]", f"the figure {w['figure']} is not in excerpt [{w['n']}] but in another one: \"{w['sentence']}\""))
    return found


def has_hard(findings: Sequence[Finding]) -> bool:
    return any(f.severity == HARD for f in findings)


def annotate(answer: str, findings: Sequence[Finding], lang: str) -> str:
    """The answer with one "⚠️" line when a written calculation gives a different result than the one stated (before its machine block); unchanged
    otherwise. Owner 19/11 (week12 audit of 200 E2E planner answers): of 24 lines that also listed untraced figures and citations, 1 pointed at a real
    problem and none at the real error of a wrong answer, so figure and citation findings stay in the trace and the admin review queue only."""
    if not any(f.check == "arithmetic" for f in findings):
        return answer
    vi = lang == "vi"
    line = "\n\n⚠️ " + ("Lưu ý: có phép tính viết ra cho kết quả khác với kết quả đã ghi." if vi
                         else "Note: a written calculation gives a different result than the one stated.")
    cut = answer.find(META_OPEN)
    return answer + line if cut < 0 else answer[:cut].rstrip() + line + "\n" + answer[cut:]


def trace(findings: Sequence[Finding]) -> List[Dict[str, Any]]:
    return [{k: v for k, v in asdict(f).items() if k != "note"} for f in findings]

