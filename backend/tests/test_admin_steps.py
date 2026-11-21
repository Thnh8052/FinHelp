"""The steps of one answer, read from the trace the chat stored with it (owner 20/11: the admin should see what the system did, and why the guard decided
what it did). A pure function of the stored trace: no model call, no database. The shapes below are the ones the chat really stores (checked on the
development database); `facts` hold only short values and counts, never long text."""
import pytest

from app.modules.admin.steps import explain


def trace(**extra):
    """A normal single-question answer: the guard let it through, one report chosen by code, a plan, a search, a checked answer."""
    base = {
        "intent": "retrieval_rag", "router": None,
        "guard": {"label": "ok", "seconds": 1.13, "outcome": "passed"},
        "decision": {"action": "proceed", "assumption": "", "flags": [], "unlisted_companies": []},
        "targets": {"rule": "resolved", "documents": ["doc_a"]}, "routing": "targets_planner", "alternatives": [],
        "plan": [{"query": "consolidated statements of income net revenue", "documents": ["Intel | 10-K | FY2022"]}],
        "sub_queries": ["consolidated statements of income net revenue"],
        "timings": {"plan": 3.6, "search": 2.4, "search_embed": 1.2, "search_vector": 0.1, "search_bm25": 0.0, "search_mongo_text": 0.4, "search_rerank": 0.6,
                    "search_hydrate": 0.0, "generate": 9.3, "verify_repair": 0.03, "total": 15.5, "understood": 1.4, "first_text": 14.0},
        "chunk_ids": ["c1", "c2", "c3"], "retrieved_pages": [1, 6], "degraded": [],
        "review": {"first": [], "outcome": "accepted"}, "verification": {"passed": True, "unverified_figures": []},
        "answer_meta": {"status": "answered", "citations": [1, 2]},
        "llm": {"prompt_tokens": 10708, "completion_tokens": 1976, "reasoning_tokens": 1611, "calls": 3},
        "actions": {"chooser": [], "search_more": {"prominent": False}, "edit_question": False, "try_again": False},
        "notes": ["The question is about these sources: Intel 10-K FY2022. Answer for them."],
    }
    base.update(extra)
    return base


def by_step(result):
    return {s["step"]: s for s in result["steps"]}


def names(result):
    return [s["step"] for s in result["steps"]]


# ------------------------------------------------------------------ an answered question: every step, in order
def test_an_answered_question_shows_every_step_in_order_and_none_stopped():
    out = explain(trace())
    assert names(out) == ["gate", "input", "guard", "scope", "plan", "search", "write", "check", "buttons"]
    assert out["stopped_at"] is None and all(s["outcome"] == "ok" for s in out["steps"])
    assert out["total_seconds"] == 15.5


def test_each_step_carries_its_decision_code_seconds_and_short_facts():
    s = by_step(explain(trace()))
    assert (s["guard"]["code"], s["guard"]["seconds"]) == ("ok", 1.13)
    assert s["input"]["code"] == "proceed"
    assert (s["scope"]["code"], s["scope"]["facts"]["documents"], s["scope"]["facts"]["routing"]) == ("resolved", 1, "targets_planner")
    assert (s["plan"]["seconds"], s["plan"]["facts"]["items"]) == (3.6, 1)
    assert s["search"]["seconds"] == 2.4 and s["search"]["facts"]["excerpts"] == 3 and s["search"]["facts"]["rerank_seconds"] == 0.6
    assert (s["write"]["seconds"], s["write"]["facts"]["first_text_seconds"], s["write"]["facts"]["reasoning_tokens"]) == (9.3, 14.0, 1611)
    assert (s["check"]["code"], s["check"]["facts"]["findings"]) == ("accepted", 0)
    assert s["buttons"]["facts"]["search_more"] == "quiet"


# ------------------------------------------------------------------ where a question stopped, and who stopped it
def test_the_code_gate_stops_a_question_before_anything_else():
    out = explain({"intent": "refuse_instruction", "decision": {"action": "refuse_instruction"}, "gate": {"rule": "assistant", "signals": []}})
    assert names(out) == ["gate"] and out["stopped_at"] == "gate"
    assert (by_step(out)["gate"]["outcome"], by_step(out)["gate"]["code"]) == ("stopped", "assistant")


def test_an_input_rule_stops_a_question_and_the_guard_was_not_waited_for():
    out = explain({"intent": "period_unavailable", "guard": {"outcome": "not_waited"}, "decision": {"action": "period_unavailable", "available": ["FY2017"]},
                   "timings": {"total": 0.19}})
    s = by_step(out)
    assert names(out) == ["gate", "input", "guard"] and out["stopped_at"] == "input"
    assert (s["input"]["outcome"], s["input"]["code"], s["input"]["facts"]["available"]) == ("stopped", "period_unavailable", ["FY2017"])
    assert s["guard"]["outcome"] == "skipped"


@pytest.mark.parametrize("guard, outcome_where", [
    ({"label": "personal_advice", "seconds": 1.46, "outcome": "kept"}, None),
    ({"label": "personal_data", "seconds": 1.46, "outcome": "blocked", "where": "search_cancelled"}, "search_cancelled"),
])
def test_the_guard_stops_a_question_with_its_label(guard, outcome_where):
    out = explain({"intent": "refuse_sensitive", "guard": guard, "decision": {"action": "refuse_sensitive"}, "timings": {"total": 1.46}})
    s = by_step(out)
    assert out["stopped_at"] == "guard" and names(out) == ["gate", "input", "guard"]
    assert s["input"]["outcome"] == "ok" and s["input"]["code"] == "proceed"  # the rules let it through: the label is what turned it away, not the reply's action
    assert s["guard"]["facts"]["reply"] == "refuse_sensitive"  # the reply the label led to
    assert (s["guard"]["outcome"], s["guard"]["code"], s["guard"]["seconds"]) == ("stopped", guard["label"], 1.46)
    assert s["guard"]["facts"].get("where") == outcome_where


def test_a_guard_that_timed_out_is_a_warning_and_says_why():
    out = explain(trace(guard={"label": None, "seconds": 3.01, "error": "timeout", "outcome": "unchecked"}))
    g = by_step(out)["guard"]
    assert (g["outcome"], g["code"], g["facts"]["error"]) == ("warn", None, "timeout")
    assert out["stopped_at"] is None  # the question went on without a label


def test_an_empty_plan_stops_at_the_plan_and_an_unlisted_company_at_the_scope():
    empty = explain(trace(intent="empty_plan", plan=[], sub_queries=[], timings={"plan": 1.26, "search": 0.0, "total": 1.87}))
    assert empty["stopped_at"] == "plan" and names(empty)[-1] == "plan" and by_step(empty)["plan"]["code"] == "empty"
    out = explain({"intent": "out_of_scope", "guard": {"outcome": "not_waited"}, "unlisted_companies": ["Pepsi"], "timings": {"total": 1.35}})
    assert out["stopped_at"] == "scope" and by_step(out)["scope"]["facts"]["unlisted"] == ["Pepsi"]


# ------------------------------------------------------------------ warnings inside an answered question
def test_a_step_dropped_for_time_is_a_warning_on_the_plan_and_the_search():
    s = by_step(explain(trace(degraded=["plan_deadline", "rerank_skipped"])))
    assert s["plan"]["outcome"] == "warn" and s["search"]["outcome"] == "warn"
    assert s["search"]["facts"]["degraded"] == ["plan_deadline", "rerank_skipped"]
    assert by_step(explain(trace(degraded=["rerank_skipped"])))["plan"]["outcome"] == "ok"  # only the plan deadline belongs to the plan


def test_unverified_figures_and_blocked_answers_show_on_the_check():
    warn = by_step(explain(trace(verification={"passed": False, "unverified_figures": ["11,715", "8,603"]}, review={"first": [{"check": "figure", "severity": "warn"}], "outcome": "annotated"})))["check"]
    assert (warn["outcome"], warn["code"], warn["facts"]["unverified_figures"], warn["facts"]["findings"]) == ("warn", "annotated", 2, 1)
    stopped = explain(trace(review={"first": [{"check": "advice", "severity": "block"}], "outcome": "blocked"}))
    assert by_step(stopped)["check"]["outcome"] == "stopped" and stopped["stopped_at"] == "check"


def test_a_short_answer_makes_the_search_deeper_button_prominent_and_says_so():
    s = by_step(explain(trace(answer_meta={"status": "not_found"}, actions={"chooser": [{"document_id": "a"}, {"document_id": "b"}], "search_more": {"prominent": True},
                                           "edit_question": False, "try_again": False})))
    assert s["check"]["facts"]["status"] == "not_found" and s["check"]["outcome"] == "warn"
    assert (s["buttons"]["facts"]["search_more"], s["buttons"]["facts"]["chooser"]) == ("prominent", 2)


def test_a_writer_call_that_failed_is_a_warning_on_the_write_step():
    out = explain(trace(llm_calls=[{"purpose": "answer", "seconds": 80.0, "attempts": 2, "status": "truncated", "completion_tokens": 24000}]))
    w = by_step(out)["write"]
    assert w["outcome"] == "warn" and w["facts"]["status"] == "truncated" and w["facts"]["attempts"] == 2


# ------------------------------------------------------------------ the model calls, and traces of other shapes
def test_the_model_calls_are_listed_with_purpose_seconds_and_tokens():
    calls = [{"purpose": "guard", "seconds": 1.13, "attempts": 1, "status": "ok", "prompt_tokens": 716, "completion_tokens": 6, "reasoning_tokens": 0, "thinking": False},
             {"purpose": "answer", "seconds": 9.26, "attempts": 1, "status": "ok", "first_piece_seconds": 8.25, "prompt_tokens": 8756, "completion_tokens": 1582,
              "reasoning_tokens": 1274, "thinking": True}]
    out = explain(trace(llm_calls=calls))
    assert [(c["purpose"], c["seconds"], c["status"]) for c in out["calls"]] == [("guard", 1.13, "ok"), ("answer", 9.26, "ok")]
    assert out["calls"][1]["reasoning_tokens"] == 1274 and out["calls"][1]["first_piece_seconds"] == 8.25


def test_a_question_split_into_parts_says_how_many():
    out = explain(trace(decision={"action": "split_questions", "sub_questions": ["a", "b"]}, parts=[{"query": "a"}, {"query": "b"}]))
    assert by_step(out)["input"]["code"] == "split_questions" and by_step(out)["input"]["facts"]["parts"] == 2


@pytest.mark.parametrize("old", [None, {}, {"intent": "retrieval_rag"}])
def test_an_old_or_empty_trace_gives_no_steps_and_no_error(old):
    out = explain(old)
    assert out["stopped_at"] is None and out["calls"] == [] and out["total_seconds"] is None
    assert len(out["steps"]) <= 1  # at most the gate, inferred from the intent


def test_facts_stay_short_primitives_so_the_page_never_holds_an_excerpt():
    import json

    out = explain(trace(plan=[{"query": "q" * 5000, "documents": ["d"] * 50}], notes=["n" * 5000]))
    assert len(json.dumps(out)) < 4000


# ------------------------------------------------------------------ reading them for one stored answer (GET /auth/admin/steps/{message_id})
class OneMessage:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, query, projection=None):
        return self.doc if all(self.doc.get(k) == v for k, v in query.items()) else None


async def test_the_steps_of_a_stored_answer_come_with_its_id_and_latency_and_a_missing_one_is_none():
    from app.infrastructure.database import collections
    from app.modules.admin.steps import answer_steps

    db = {collections.MESSAGES_COLLECTION: OneMessage({"message_id": "m1", "role": "assistant", "latency_ms": 15500, "trace_info": trace()})}
    out = await answer_steps(db, "m1")
    assert out["message_id"] == "m1" and out["latency_ms"] == 15500 and out["steps"][0]["step"] == "gate" and out["stopped_at"] is None
    assert await answer_steps(db, "nope") is None


# ------------------------------------------------------------------ slice 2: the guard's wait, the funnel of the search, the reasons of the buttons
def test_the_guard_wait_the_search_funnel_and_the_button_reasons_show_in_their_steps():
    s = by_step(explain(trace(
        guard={"label": "ok", "seconds": 1.13, "outcome": "passed", "waited_seconds": 0.4},
        search_counts={"documents": 2, "searches": 5, "candidates": 120, "rerank_pairs": 160, "chosen": 9, "tokens": 8800, "max_tokens": 13000},
        actions={"chooser": [{"document_id": "a"}], "search_more": {"prominent": True}, "edit_question": False, "try_again": False}, actions_why=["short"])))
    assert s["guard"]["facts"]["waited_seconds"] == 0.4
    assert {k: s["search"]["facts"][k] for k in ("candidates", "rerank_pairs", "tokens", "max_tokens")} == {"candidates": 120, "rerank_pairs": 160, "tokens": 8800, "max_tokens": 13000}
    assert s["buttons"]["facts"]["why"] == ["short"]


def test_a_trace_without_the_new_fields_still_explains_itself():
    s = by_step(explain(trace()))
    assert "waited_seconds" not in s["guard"]["facts"] and "candidates" not in s["search"]["facts"] and "why" not in s["buttons"]["facts"]


def test_a_single_document_question_has_no_plan_but_a_split_of_the_question_and_that_is_not_an_empty_plan():
    # live trial 21/11: the one-report path has no planner, its query split is what takes the "plan" seconds; it showed as "empty plan"
    s = by_step(explain(trace(routing="targets_single", plan=[], sub_queries=["consolidated statements of income"])))
    assert (s["plan"]["code"], s["plan"]["outcome"]) == ("split", "ok")
    assert by_step(explain(trace(intent="empty_plan", plan=[], sub_queries=[])))["plan"]["code"] == "empty"  # only a stop at the plan is an empty plan
