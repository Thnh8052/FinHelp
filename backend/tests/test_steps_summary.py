"""Slice 3 of the admin trace (owner 20/11): the steps of many answers added up, and a small sample of what the guard let through.
- summarize(traces): per step how often a question stopped there and how long the step took (median and p90), the guard's labels and outcomes and how often the answer
  waited for it, the steps dropped for time, and how often the "Search deeper" button was there and was clicked. Pure: no database, no model.
- the guard's sample: GUARD_SAMPLE_RATE of the messages it lets through are marked in their trace (guard.sampled) and get the review label "guard_sample", so the admin can
  mark a miss; every message it turns away is already in the queue (label "safety" and "refused")."""
import pytest

from app.core.config import settings
from app.modules.admin import review as R
from app.modules.admin.steps_summary import summarize
from tests.test_admin_steps import trace
from tests.test_admin_review import _answer
from tests.test_guard import fake_guard
from tests.test_input_policy import NIKE_DOCS, _orchestrator


def answered(plan=3.0, search=2.0, generate=9.0, guard=1.0, waited=0.0, **extra):
    t = trace(guard={"label": "ok", "seconds": guard, "outcome": "passed", "waited_seconds": waited},
              timings={"plan": plan, "search": search, "generate": generate, "verify_repair": 0.03, "total": plan + search + generate + 0.03}, **extra)
    return t


REFUSED_BY_GUARD = {"intent": "refuse_advice", "guard": {"label": "personal_advice", "seconds": 1.4, "outcome": "kept"}, "decision": {"action": "refuse_advice"}, "timings": {"total": 1.4}}
REFUSED_BY_INPUT = {"intent": "period_unavailable", "guard": {"outcome": "not_waited"}, "decision": {"action": "period_unavailable", "available": ["FY2017"]}, "timings": {"total": 0.2}}


def test_questions_are_counted_by_where_they_stopped():
    out = summarize([answered(), answered(), REFUSED_BY_GUARD, REFUSED_BY_INPUT, {}])
    assert out["questions"] == 4  # the empty trace of an old answer is left out
    assert out["stopped"] == {"guard": 1, "input": 1} and out["answered"] == 2


def test_each_step_has_its_median_and_p90_seconds():
    out = summarize([answered(plan=p) for p in (1.0, 2.0, 3.0, 4.0, 10.0)])
    plan = out["seconds"]["plan"]
    assert (plan["n"], plan["p50"], plan["p90"]) == (5, 3.0, 10.0)
    assert out["seconds"]["write"]["p50"] == 9.0 and out["seconds"]["guard"]["p50"] == 1.0
    assert "buttons" not in out["seconds"] and "gate" not in out["seconds"]  # steps with no time of their own


def test_the_guard_labels_outcomes_and_how_often_the_answer_waited_for_it():
    out = summarize([answered(waited=0.0), answered(waited=0.8), answered(waited=1.2), REFUSED_BY_GUARD, REFUSED_BY_INPUT])
    g = out["guard"]
    assert g["labels"] == {"ok": 3, "personal_advice": 1} and g["outcomes"] == {"passed": 3, "kept": 1, "not_waited": 1}
    assert g["waited"] == {"answers": 3, "over_half_second": 2}


def test_steps_dropped_for_time_and_the_search_deeper_button_are_counted():
    quiet = answered()
    short = answered(degraded=["plan_deadline"], actions={"chooser": [], "search_more": {"prominent": True}, "edit_question": False, "try_again": False})
    clicked = answered(click="deeper", retry_of="m1", actions={"chooser": [], "search_more": None, "edit_question": False, "try_again": False})
    out = summarize([quiet, short, clicked])
    assert out["degraded"] == {"plan_deadline": 1}
    assert out["search_deeper"] == {"offered": 2, "prominent": 1, "clicks": 1}


def test_an_empty_list_gives_zeros_not_an_error():
    out = summarize([])
    assert out["questions"] == 0 and out["stopped"] == {} and out["seconds"] == {} and out["guard"]["labels"] == {}


# ------------------------------------------------------------------ the guard's sample
def test_the_default_sample_is_two_percent():
    assert settings.GUARD_SAMPLE_RATE == 0.02


@pytest.mark.parametrize("rate, sampled", [(1.0, True), (0.0, False)])
async def test_a_message_the_guard_passes_is_marked_at_the_sample_rate(monkeypatch, rate, sampled):
    monkeypatch.setattr(settings, "GUARD_SAMPLE_RATE", rate)
    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    fake_guard(monkeypatch, "ok")
    r = await orch.execute_query("What was Nike's revenue?", "nb", document_ids=["d1", "d2"])
    assert r["trace"]["guard"].get("sampled", False) is sampled


async def test_a_message_the_guard_turns_away_is_never_sampled(monkeypatch):
    monkeypatch.setattr(settings, "GUARD_SAMPLE_RATE", 1.0)
    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    fake_guard(monkeypatch, "personal_data")
    r = await orch.execute_query("What was Nike's revenue? Give me the home address of Nike's CEO", "nb", document_ids=["d1", "d2"])
    assert "sampled" not in r["trace"]["guard"]  # it is in the queue already


def test_a_sampled_answer_gets_its_own_label_in_the_review_queue():
    assert R.problem_labels(_answer(1, trace_info__guard__sampled=True)) == ["guard_sample"]
    assert "guard_sample" in R.LABELS
