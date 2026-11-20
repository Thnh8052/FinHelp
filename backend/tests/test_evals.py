"""The evaluation kit (backend/evals, run with `python -m evals`): where a lost question was lost (search or writing), the numeric grader, the comparison with
the committed baseline, and the free checks on the committed data (the quality floor: they fail when a rule change breaks what was measured)."""
import json

import pytest

from evals import checks, gold, grading
from evals.__main__ import compare, metrics_of


@pytest.mark.parametrize("complete, correct, kind", [
    (True, True, "ok"),
    (False, True, "lucky"),  # right although the search missed an evidence page
    (True, False, "writing"),  # every page was in the excerpts and the answer is still wrong
    (False, False, "retrieval"),
    (True, None, "unscored"),
    (False, None, "unscored"),
])
def test_failure_kind_says_where_a_question_was_lost(complete, correct, kind):
    assert checks.failure_kind(complete, correct) == kind


def test_failure_table_counts_every_scored_question_once():
    gold_rows = {"a": {"split": "dev", "behavior": "answer"}, "b": {"split": "test", "behavior": "answer"}, "c": {"split": "dev", "behavior": "not_available"}}
    search = {"a": {"comp": True}, "b": {"comp": False}, "c": {"comp": True}}
    graded = {"a": False, "b": False, "c": True}
    table = checks.failure_table(gold_rows, search, graded)
    assert table["by_kind"] == {"writing": 1, "retrieval": 1} and table["questions"] == 2  # only questions the gold wants answered
    assert table["by_split"]["dev"] == {"writing": 1} and table["by_split"]["test"] == {"retrieval": 1}


def test_grader_reads_the_numbers_of_the_answer_spec_with_their_tolerance():
    q = {"behavior": "answer", "answer_spec": {"answer_type": "numeric", "values": {"revenue_usd_m": 280522, "growth_pct": 21.0}, "units": {"growth_pct": "percent"}, "rel_tol": 0.01}}
    assert grading.grade(q, "Net sales were $280,522 million, up 21.0%.", "answered") is True
    assert grading.grade(q, "Net sales were $280,522 million, up 25.0%.", "answered") is False
    assert grading.grade({"behavior": "not_available", "answer_spec": {"answer_type": "abstain"}}, "The selected reports do not include FY2030.", "answered") is True


def test_compare_flags_only_what_got_worse_than_the_baseline():
    base = {"false_refusals": {"value": 0, "better": "lower"}, "evidence_pct": {"value": 89.8, "better": "higher"}}
    same = compare(base, {"false_refusals": {"value": 0, "better": "lower"}, "evidence_pct": {"value": 89.8, "better": "higher"}})
    assert [r["verdict"] for r in same] == ["same", "same"]
    worse = compare(base, {"false_refusals": {"value": 2, "better": "lower"}, "evidence_pct": {"value": 91.0, "better": "higher"}})
    assert {r["name"]: r["verdict"] for r in worse} == {"false_refusals": "WORSE", "evidence_pct": "better"}


def test_the_committed_data_is_consistent():
    questions = gold.questions()
    assert len(questions) == 200 and {q["split"] for q in questions.values()} == {"dev", "test"}
    assert all(d in gold.catalog() for q in questions.values() for d in q["workspace"])
    assert set(gold.search_snapshot()) <= set(questions) and set(gold.answer_snapshot()) <= set(questions)


def test_the_free_checks_hold_the_measured_floor():
    """Numbers of docs/VERSION_4 (input layer: no question the gold wants answered is stopped, 187 of them; P1: no legitimate question refused by code; TK-49 evidence)."""
    result = checks.run_free()
    layer = result["input_layer"]
    assert layer["answerable_false_refusals"] == 0 and layer["answerable"] == 187
    sec = result["security"]
    assert sec["legit_refused"] == 0 and sec["legit"] >= 40 and sec["code_expected_stopped"] >= 18
    search = result["search"]
    assert search["scored"] == 187 and search["evidence_complete_pct"] >= 89.0
    kinds = result["failures"]["by_kind"]
    assert sum(kinds.values()) == result["failures"]["questions"]


def test_the_metrics_of_a_run_are_numbers_with_a_direction():
    m = metrics_of(checks.run_free())
    assert m and all(set(v) == {"value", "better"} and v["better"] in ("higher", "lower") for v in m.values())
    json.dumps(m)
