"""python -m evals   (from backend/)   every free check, then the table "baseline vs now".  See evals/README.md.

  python -m evals                      free checks; exit code 1 when a number got worse than evals/baseline.json
  python -m evals --tests              also the whole pytest suite (counted as numbers too)
  python -m evals --search F --answers G   score another run: F a snapshot or retrieval_*.json, G a jsonl of {"id", "answer", "status"} per line
  python -m evals --update-baseline    write today's numbers as the new baseline (after a change you meant to make)
  python -m evals --json out.json      the full result as json
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from . import checks, gold

BASELINE = Path(__file__).resolve().parent / "baseline.json"


def metrics_of(result: dict) -> Dict[str, dict]:
    """The numbers the baseline tracks, each with the direction that is better."""
    sec, kinds = result["security"], result["failures"]["by_kind"]
    lo, hi = "lower", "higher"
    rows = [("input.answerable_false_refusals", result["input_layer"].get("answerable_false_refusals", 0), lo),
            ("input.not_available_refused_right", result["input_layer"].get("not_available_refused_right", 0), hi),
            ("security.code_expected_stopped", sec["code_expected_stopped"], hi), ("security.legit_refused", sec["legit_refused"], lo),
            ("security.bad_answers_stopped", sec["bad_answers_stopped"], hi), ("security.good_answers_left", sec["good_answers_left"], hi),
            ("security.planted_text_flagged", sec["planted_text_flagged"], hi), ("security.report_text_wrongly_flagged", sec["report_text_wrongly_flagged"], lo),
            ("search.evidence_complete_pct", result["search"]["evidence_complete_pct"], hi), ("answers.machine_correct_pct", result["answers"]["machine_correct_pct"], hi),
            ("failures.retrieval", kinds.get("retrieval", 0), lo), ("failures.writing", kinds.get("writing", 0), lo)]
    if "tests" in result:
        rows += [("tests.failed", result["tests"]["failed"], lo), ("tests.passed", result["tests"]["passed"], hi)]
    return {name: {"value": value, "better": better} for name, value, better in rows}


def compare(baseline: Dict[str, dict], now: Dict[str, dict]) -> List[dict]:
    """One row per number of `now`: same / better / WORSE against the baseline, or new when the baseline has no such number."""
    out = []
    for name, m in now.items():
        before = baseline.get(name)
        if before is None:
            verdict, b = "new", None
        else:
            b = before["value"]
            delta = m["value"] - b
            verdict = "same" if delta == 0 else "better" if (delta > 0) == (m["better"] == "higher") else "WORSE"
        out.append({"name": name, "before": b, "now": m["value"], "better": m["better"], "verdict": verdict})
    return out


def run_tests() -> dict:
    """The whole backend suite in a child process: {"passed", "failed"} read from its last line."""
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--ignore=tests/test_evals.py"], capture_output=True, text=True, encoding="utf-8")
    last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    count = lambda word: int(next(iter(re.findall(rf"(\d+) {word}", last)), 0))
    return {"passed": count("passed"), "failed": count("failed") + count("error"), "line": last}


def show(result: dict, rows: List[dict]) -> str:
    kinds, split = result["failures"]["by_kind"], result["failures"]["by_split"]
    lines = ["| number | baseline | now | verdict |", "|---|---|---|---|"]
    lines += [f"| {r['name']} | {'-' if r['before'] is None else r['before']} | {r['now']} | {r['verdict']} |" for r in rows]
    lines += ["", f"Where the {result['failures']['questions']} questions the gold wants answered were lost (stored search + answers, machine grading):",
              "| kind | all | " + " | ".join(sorted(split)) + " |", "|---|---|" + "---|" * len(split)]
    meaning = {"ok": "right, evidence complete", "lucky": "right, a page was missing", "writing": "wrong, evidence complete: the writer", "retrieval": "wrong, a page was missing: the search",
               "unscored": "no number to grade"}
    for kind in ("ok", "lucky", "writing", "retrieval", "unscored"):
        lines.append(f"| {kind} ({meaning[kind]}) | {kinds.get(kind, 0)} | " + " | ".join(str(split[s].get(kind, 0)) for s in sorted(split)) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tests", action="store_true")
    ap.add_argument("--search")
    ap.add_argument("--answers")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = checks.run_free(gold.load_search(Path(a.search)) if a.search else None, gold.load_answers(Path(a.answers)) if a.answers else None)
    if a.tests:
        result["tests"] = run_tests()
    now = metrics_of(result)
    base = json.loads(BASELINE.read_text(encoding="utf-8"))["metrics"] if BASELINE.exists() else {}
    rows = compare(base, now)
    print(show(result, rows))
    if a.json:
        Path(a.json).write_text(json.dumps({"result": result, "metrics": now}, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.update_baseline:
        BASELINE.write_text(json.dumps({"note": "python -m evals --update-baseline", "metrics": now}, indent=1), encoding="utf-8")
        print(f"\nbaseline written: {BASELINE}")
        return 0
    worse = [r["name"] for r in rows if r["verdict"] == "WORSE"]
    print("\n" + (f"WORSE than the baseline: {', '.join(worse)}" if worse else "nothing is worse than the baseline"))
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
