"""Quality per day on the overview (plan 26/11 3.4, like Langfuse's scores over time): the answers of each day that meet each problem of the review
queue (review.PROBLEMS, the same conditions, so the chart and the queue never disagree) and the admin's verdicts. Pure function: no database."""
from datetime import datetime

from app.modules.admin.overview import quality_series

DAYS = ["2026-11-25", "2026-11-26"]


def ans(day, **fields):
    return {"created_at": datetime.fromisoformat(day + "T09:00:00"), **fields}


def test_each_day_counts_its_answers_their_problems_and_the_admin_verdicts():
    answers = [
        ans("2026-11-25", user_rating=-1, trace_info={"answer_meta": {"status": "answered"}}),
        ans("2026-11-25", trace_info={"answer_meta": {"status": "not_found"}}, admin_review={"status": "ok"}),
        ans("2026-11-26", trace_info={"answer_meta": {"status": "partial"}, "verification": {"passed": False}}, admin_review={"status": "needs_fix"}),
        ans("2026-11-26", trace_info={"intent": "refuse_advice"}),
        ans("2026-11-26", trace_info={"answer_meta": {"status": "answered"}}),
    ]
    rows = quality_series(answers, DAYS)
    assert rows[0] == {"date": "2026-11-25", "answers": 2, "user_report": 1, "not_found": 1, "partial": 0, "not_traced": 0, "refused": 0,
                       "safety": 0, "blocked": 0, "reviewed_ok": 1, "needs_fix": 0}
    assert rows[1] == {"date": "2026-11-26", "answers": 3, "user_report": 0, "not_found": 0, "partial": 1, "not_traced": 1, "refused": 0,
                       "safety": 1, "blocked": 0, "reviewed_ok": 0, "needs_fix": 1}


def test_a_day_without_answers_is_all_zeros():
    assert quality_series([], ["2026-11-24"]) == [{"date": "2026-11-24", "answers": 0, "user_report": 0, "not_found": 0, "partial": 0, "not_traced": 0,
                                                   "refused": 0, "safety": 0, "blocked": 0, "reviewed_ok": 0, "needs_fix": 0}]
