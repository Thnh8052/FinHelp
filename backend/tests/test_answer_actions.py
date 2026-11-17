"""The buttons under an answer (docs/VERSION_4/CODE_MODEL_DECISIONS_2026-11-17.md section 4.2), one pure function of what the search and the answer did:
- chooser: every selected document, those the answer used ticked; the user ticks several and asks again (they become @ tags). Shown when the system
  chose for the user (code by a company name with other matching files; the planner, no company named, only some companies chosen), when an answer over
  several files fell short, or when the model asks for clarification. Several files can be ticked: a question about two companies needs two.
- search_more: on every answer that searched (a full search again, leaving out the excerpts already sent); prominent when the answer fell short, a step was
  dropped for time (degraded) or the writer failed.
- edit_question: put the question back in the box (a click that still fell short, or a request for clarification).
A click is a retry: one click only, so the answer to a click offers no chooser and no search_more."""
from app.modules.chat.orchestrator import answer_actions
from app.modules.chat.retrieval_step import RetrievalResult
from app.modules.query_router.planner import PlanItem
from app.modules.query_router.target_scope import TargetDecision
from tests.test_no_gate import _doc

CVS, JNJ, AMD = _doc("cvs", "CVS Health Corp", 2019), _doc("jnj", "Johnson & Johnson", 2018), _doc("amd", "Advanced Micro Devices", 2023)
CHUNK = {"chunk_id": "c", "document_id": "cvs", "page": 1, "content": "x"}


def found(scope, plan=(), degraded=(), retrieved=(CHUNK,)):
    return RetrievalResult(list(scope), {d.document_id: d.document_id.upper() for d in scope}, list(plan), [], list(retrieved), "planner", {}, degraded=list(degraded))


def actions(selected, f, targets=TargetDecision(), status="answered", short=False, unfinished=False, retry=False):
    return answer_actions(selected, f, targets, status, short, unfinished, retry)


def chooser(a):
    return [(c["document_id"], c["checked"]) for c in a["chooser"]]


def test_one_document_answered_gets_only_a_quiet_search_more():
    a = actions([CVS], found([CVS]))
    assert a == {"chooser": [], "search_more": {"prominent": False}, "edit_question": False}


def test_one_document_short_gets_a_prominent_search_more():
    assert actions([CVS], found([CVS]), status="partial", short=True)["search_more"] == {"prominent": True}


def test_the_planner_choosing_one_of_two_companies_for_a_question_naming_none_gets_the_chooser():
    a = actions([CVS, JNJ, AMD], found([CVS, JNJ, AMD], [PlanItem("net earnings", ["cvs"])]))
    assert chooser(a) == [("cvs", True), ("jnj", False), ("amd", False)]  # several can be ticked, nothing is asked before the answer


def test_the_planner_choosing_every_company_needs_no_chooser():
    a = actions([CVS, JNJ], found([CVS, JNJ], [PlanItem("revenue", ["cvs", "jnj"])]))
    assert a["chooser"] == [] and a["search_more"] == {"prominent": False}


def test_code_choosing_by_name_with_other_matching_files_gets_the_chooser_with_its_choice_ticked():
    targets = TargetDecision(["cvs"], "I understood...", [{"document_id": "jnj", "label": "JNJ"}], rule="resolved")
    a = actions([CVS, JNJ], found([CVS], [PlanItem("revenue", ["cvs"])]), targets)
    assert chooser(a) == [("cvs", True), ("jnj", False)]


def test_a_short_answer_over_several_files_gets_the_chooser_and_a_prominent_search_more():
    a = actions([CVS, JNJ], found([CVS, JNJ], [PlanItem("revenue", ["cvs", "jnj"])]), status="partial", short=True)
    assert chooser(a) == [("cvs", True), ("jnj", True)] and a["search_more"] == {"prominent": True}


def test_a_degraded_search_makes_search_more_prominent():
    for why in ("plan_deadline", "rerank_skipped"):
        assert actions([CVS, JNJ], found([CVS, JNJ], degraded=[why]))["search_more"] == {"prominent": True}


def test_a_failed_writer_gets_a_prominent_search_more():
    assert actions([CVS], found([CVS]), status=None, unfinished=True)["search_more"] == {"prominent": True}


def test_a_request_for_clarification_offers_the_chooser_and_editing_the_question():
    a = actions([CVS, JNJ], found([CVS, JNJ], [PlanItem("revenue", ["cvs", "jnj"])]), status="clarify")
    assert a["edit_question"] is True and chooser(a) == [("cvs", True), ("jnj", True)]


def test_a_click_gets_no_more_clicks_and_editing_the_question_when_it_still_falls_short():
    assert actions([CVS, JNJ], found([CVS, JNJ]), status="partial", short=True, retry=True) == {"chooser": [], "search_more": None, "edit_question": True}
    assert actions([CVS, JNJ], found([CVS, JNJ]), retry=True) == {"chooser": [], "search_more": None, "edit_question": False}


def test_nothing_searched_offers_no_search_more():
    assert actions([CVS], found([CVS], retrieved=()))["search_more"] is None
