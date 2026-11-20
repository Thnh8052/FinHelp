"""Slice 2 of the admin trace (owner 20/11): what the steps page (admin/steps.py) could not say about real traces.
1. the guard runs beside the search: the trace now says how long the answer waited for it (0 when its label was ready first);
2. the planned search kept only its seconds: it now keeps how many candidates, how many pairs went to the reranker, how many excerpts it kept and the token budget;
3. the buttons: why each one is there (the answer fell short, a step was dropped, the system chose among files, the model asked to clarify, a click, an outage...).
No model, no worker: fakes as in test_multidoc.py and test_guard.py."""
import pytest

from app.core.config import settings
from app.modules.chat.orchestrator import answer_actions
from app.modules.query_router.planner import PlanItem
from app.modules.query_router.target_scope import TargetDecision
from app.modules.retrieval.hybrid_search import SEARCH_COUNTS, planned_ceilings
from tests.test_answer_actions import CVS, JNJ, found
from tests.test_guard import fake_guard
from tests.test_input_policy import NIKE_DOCS, _orchestrator
from tests.test_multidoc import _planned


# ------------------------------------------------------------------ 1. how long the answer waited for the guard
async def test_a_slow_guard_shows_how_long_the_answer_waited_for_it(monkeypatch):
    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    fake_guard(monkeypatch, "ok", delay=0.3)  # slower than the whole fake search: the answer cannot be written before the label is known
    r = await orch.execute_query("What was Nike's revenue?", "nb", document_ids=["d1", "d2"])
    assert r["trace"]["guard"]["outcome"] == "passed" and r["trace"]["guard"]["waited_seconds"] >= 0.1


async def test_a_guard_that_was_ready_first_costs_no_waiting(monkeypatch):
    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    fake_guard(monkeypatch, "ok")
    r = await orch.execute_query("What was Nike's revenue?", "nb", document_ids=["d1", "d2"])
    assert r["trace"]["guard"]["waited_seconds"] < 0.1


# ------------------------------------------------------------------ 2. the funnel of the planned search
async def test_the_planned_search_keeps_what_it_found_sent_to_the_reranker_and_kept(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_WINDOWS_ENABLED", False)
    by_document = {"d1": [("a1", 0.9), ("a2", 0.8)], "d2": [("b1", 0.9)]}
    text = {"a1": "revenue a", "a2": "other a", "b1": "revenue b"}
    svc = _planned(monkeypatch, by_document, text, lambda q, t: 0.9)
    counts = {}
    token = SEARCH_COUNTS.set(counts)
    try:
        chunks = await svc.retrieve_planned("the question", [PlanItem("revenue", ["d1", "d2"])], "nb", ["d1", "d2"])
    finally:
        SEARCH_COUNTS.reset(token)
    assert counts["documents"] == 2 and counts["searches"] >= 3  # the plan's searches and the question's
    assert counts["candidates"] >= counts["chosen"] == len(chunks) > 0
    assert counts["rerank_pairs"] > 0 and 0 < counts["tokens"] <= counts["max_tokens"] == planned_ceilings(2)[1]


def test_no_collector_set_means_no_error_and_no_cost():
    from app.modules.retrieval.hybrid_search import count_done

    count_done("candidates", 5)  # called outside a question's search: nothing happens


# ------------------------------------------------------------------ 3. why each button is there
def why_of(selected, f, targets=TargetDecision(), status="answered", short=False, unfinished="", retry=False):
    why = []
    answer_actions(selected, f, targets, status, short, unfinished, retry, why=why)
    return why


def test_a_quiet_answer_has_nothing_to_explain():
    assert why_of([CVS], found([CVS])) == []


def test_a_short_answer_says_so_once_though_two_buttons_follow_from_it():
    assert why_of([CVS, JNJ], found([CVS, JNJ], [PlanItem("revenue", ["cvs", "jnj"])]), status="partial", short=True) == ["short"]


def test_a_dropped_step_makes_the_search_deeper_button_prominent_for_that_reason():
    assert why_of([CVS], found([CVS], degraded=["plan_deadline"])) == ["degraded"]


def test_the_system_choosing_among_files_is_why_the_chooser_is_there():
    targets = TargetDecision(["cvs"], "I understood...", [{"document_id": "jnj", "label": "JNJ"}], rule="resolved")
    assert why_of([CVS, JNJ], found([CVS], [PlanItem("revenue", ["cvs"])]), targets) == ["chose_for_user"]


@pytest.mark.parametrize("kwargs, expected", [
    ({"status": "clarify"}, ["clarify"]),
    ({"unfinished": "outage", "status": None}, ["outage"]),
    ({"unfinished": "cut", "status": None}, ["cut"]),
    ({"unfinished": "blocked", "status": None}, ["blocked"]),
    ({"retry": True, "short": True, "status": "partial"}, ["click", "short"]),
])
def test_each_other_reason_has_its_own_code(kwargs, expected):
    assert why_of([CVS, JNJ], found([CVS, JNJ], [PlanItem("revenue", ["cvs", "jnj"])]), **kwargs) == expected
