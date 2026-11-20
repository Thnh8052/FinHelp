"""calls_by_purpose: the stored llm_calls of many questions, summed up per kind of call (what scripts/latency_report.py prints)."""
from app.modules.chat.trace_stats import calls_by_purpose


def call(purpose, seconds, status="ok", first=None, prompt=0, completion=0):
    return {"purpose": purpose, "seconds": seconds, "status": status, "attempts": 1, "first_piece_seconds": first, "prompt_tokens": prompt, "completion_tokens": completion}


TRACES = [
    {"llm_calls": [call("guard", 0.8, prompt=600, completion=5), call("plan", 3.0, prompt=4000, completion=900), call("answer", 10.0, first=9.0, prompt=9000, completion=1500)]},
    {"llm_calls": [call("guard", 1.2, prompt=620, completion=5), call("answer", 20.0, first=18.0, prompt=11000, completion=2500)]},
    {"llm_calls": [call("guard", 3.0, status="cancelled", prompt=0, completion=0)]},
    {"timings": {"total": 5.0}},  # an answer stored before llm_calls existed
    {"llm_calls": None},
]


def test_one_row_per_purpose_slowest_kind_first():
    rows = calls_by_purpose(TRACES)
    assert [r["purpose"] for r in rows] == ["answer", "plan", "guard"]  # ordered by the median seconds


def test_a_row_counts_calls_failures_seconds_and_tokens():
    rows = {r["purpose"]: r for r in calls_by_purpose(TRACES)}
    answer, guard = rows["answer"], rows["guard"]
    assert answer["n"] == 2 and answer["failed"] == 0 and answer["seconds_p50"] == 15.0 and answer["seconds_max"] == 20.0
    assert answer["first_piece_p50"] == 13.5 and answer["prompt_tokens_mean"] == 10000 and answer["completion_tokens_mean"] == 2000
    assert guard["n"] == 3 and guard["failed"] == 1  # the call the guard gave up on counts as failed
    assert guard["first_piece_p50"] is None  # none of the guard's calls streams


def test_traces_without_calls_are_skipped_and_nothing_gives_no_rows():
    assert calls_by_purpose([{"timings": {}}, {"llm_calls": None}, {}]) == []
    assert calls_by_purpose([]) == []
