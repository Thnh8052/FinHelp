"""Step 3 of docs/VERSION_4/CODE_MODEL_DECISIONS_2026-11-17.md (decision D13, TRIED KH-13 and KH-21; STATUS_2026-11-18.md A2 and A3).

A VALID empty plan (the planner read the question and chose no selected report) is not a failure: on gold v2 it came 6 times in 200 questions, all
of them unanswerable, and 0 times in 274 answerable ones. Nothing is searched or written then: a fixed reply, not charged, with the button "search
all sources" and the document chooser. Code vetoes it when it already chose the question's documents (a named company, @ tags): those are searched
as before (wrong veto 0 of 13, KH-21).
A planner that FAILED (the model could not be reached, no valid plan twice) is a different thing: the question goes the way without a plan as
before, and the result now says so (`degraded` "plan_unavailable", like "plan_deadline"), so the answer gets the slow-system line and a prominent
"search deeper" (before, only a planner past its deadline did)."""
import json
import types

import pytest

from app.core.config import settings
from app.modules.chat import chat as chat_api
from app.modules.chat import orchestrator as orch_mod
from app.modules.chat import retrieval_step
from app.modules.chat.chat_models import MessageRecord
from app.modules.chat.orchestrator import RetrievalResult
from app.modules.generation.llm_client import LLMUnavailableError
from app.modules.generation.replies import DEGRADED_NOTE, EMPTY_PLAN_ANSWER
from app.modules.query_router import planner
from app.modules.query_router.input_policy import Decision
from app.modules.query_router.planner import PlanItem, PlanUnavailable
from tests.test_deadlines import _Search
from tests.test_multidoc import CATALOG
from tests.test_no_gate import _doc
from tests.test_not_found_flow import CHUNK, META, orchestrator
from tests.test_validation import AMD, NV, _scope

Q = {"en": "Which company had the higher revenue in 2024?", "vi": "Công ty nào có doanh thu cao hơn năm 2024?"}
SCOPE = [_doc("d1", "Alpha Corp", 2023), _doc("d2", "Beta Inc", 2023)]


# ---------------------------------------------------------------- the planner tells a valid empty plan from a failure
async def test_a_valid_empty_plan_comes_back_empty_and_a_failed_planner_raises(monkeypatch):
    replies, calls = [], []

    async def fake_chat(messages, **kwargs):
        calls.append(1)
        return replies[len(calls) - 1]

    planner._cache.clear()
    monkeypatch.setattr(planner, "chat_completion", fake_chat)
    replies[:] = [json.dumps({"plan": []})] * 2
    assert await planner.plan_multi_doc("q_empty", CATALOG) == [] and len(calls) == 1  # the model chose no report: an answer, not an error
    replies[:], calls[:] = ["not json"] * 2, []
    with pytest.raises(PlanUnavailable):
        await planner.plan_multi_doc("q_invalid", CATALOG)
    assert len(calls) == 2  # asked twice, as before


async def test_a_planner_that_cannot_reach_the_model_raises(monkeypatch):
    async def down(messages, **kwargs):
        raise LLMUnavailableError("down")

    planner._cache.clear()
    monkeypatch.setattr(planner, "chat_completion", down)
    with pytest.raises(PlanUnavailable):
        await planner.plan_multi_doc("q", CATALOG)
    with pytest.raises(PlanUnavailable):
        await planner.plan_with_then("q", CATALOG)


# ---------------------------------------------------------------- the search
async def test_a_failed_planner_routes_without_a_plan_and_says_so(monkeypatch):
    async def failed(query, catalog):
        raise PlanUnavailable("down")

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", failed)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    search = _Search()
    found = await retrieval_step.retrieve_for_scope(search, "Compare Alpha Corp and Beta Inc revenue", "nb", SCOPE)
    assert found.plan == [] and found.degraded == ["plan_unavailable"]
    assert search.calls and search.calls[0][0] in ("code", "content")  # the route without a plan, as before


async def test_a_valid_empty_plan_searches_nothing(monkeypatch):
    async def empty(query, catalog):
        return []

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", empty)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    search = _Search()
    found = await retrieval_step.retrieve_for_scope(search, "What was the weather in Hanoi in 2023?", "nb", SCOPE)
    assert found.routing == retrieval_step.EMPTY_PLAN and found.retrieved == [] and found.degraded == []
    assert search.calls == []  # not one search: the planner already read the catalog of every selected report


async def test_code_vetoes_an_empty_plan_and_searches_every_document_it_chose(monkeypatch):
    # the documents were chosen by code (a named company) or by the user (@ tags, the chooser, "search all sources"): EACH of them is searched with the
    # question, as a tagged document the plan skips is (tests/test_tagged_documents.py). Live check 18/11: the route without a plan (R5) kept only the
    # report of the year asked, so "search all sources" over Amazon FY2018 + Costco FY2015 never searched Costco
    async def empty(query, catalog):
        return []

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", empty)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    scope = [_doc("d1", "Alpha Corp", 2018), _doc("d2", "Beta Inc", 2015)]
    q = "What was the revenue of the electric vehicle maker in 2018?"
    search = _Search()
    found = await retrieval_step.retrieve_for_scope(search, q, "nb", scope, forced=["d1", "d2"])
    assert found.routing == "targets_question" and found.retrieved and found.degraded == []
    assert search.calls == [("planned", [PlanItem(q, ["d1"]), PlanItem(q, ["d2"])])]  # one search per document, the planned path (TK-49 selection)


async def test_a_failed_planner_with_chosen_documents_still_takes_the_route_without_a_plan(monkeypatch):
    # only a VALID empty plan is vetoed this way; a planner that failed keeps the old route (replacing it is KH-12, to be measured on TK-49 first)
    async def failed(query, catalog):
        raise PlanUnavailable("down")

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", failed)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    search = _Search()
    found = await retrieval_step.retrieve_for_scope(search, "What was the revenue?", "nb", SCOPE, forced=["d1", "d2"])
    assert found.degraded == ["plan_unavailable"] and search.calls and search.calls[0][0] in ("code", "content")


# ---------------------------------------------------------------- the reply
def _empty_plan_orchestrator(monkeypatch, written):
    orch = orchestrator(monkeypatch, [])

    async def retrieve(query, notebook_id, scope, forced=None, **kw):
        return RetrievalResult(scope, {"amd": AMD.label, "nv": NV.label}, [], [], [], retrieval_step.EMPTY_PLAN, {"plan": 2.1})

    async def gen(*a, **k):
        written.append(1)
        return "never"

    monkeypatch.setattr(orch, "retrieve", retrieve)
    monkeypatch.setattr(orch_mod, "generate_answer", gen)
    return orch


@pytest.mark.parametrize("lang", ["en", "vi"])
async def test_an_empty_plan_gets_the_fixed_reply_with_search_all_and_the_chooser_and_costs_nothing(monkeypatch, lang):
    written = []
    orch = _empty_plan_orchestrator(monkeypatch, written)
    r = await orch._answer_one(Q[lang], "nb", _scope(), Decision(lang=lang))
    assert r["answer"] == EMPTY_PLAN_ANSWER[lang] and written == []  # nothing was written
    assert r["charged"] is False and r["citations"] == [] and r["understood"] == ""
    assert r["actions"]["search_all"] is True and r["actions"]["search_more"] is None and r["actions"]["try_again"] is False
    assert [(c["document_id"], c["checked"]) for c in r["actions"]["chooser"]] == [("amd", False), ("nv", False)]
    assert r["trace"]["routing"] == retrieval_step.EMPTY_PLAN and r["trace"]["chunk_ids"] == []
    assert not r.get("focus_docs")  # the conversation's topic stays where it was


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_the_empty_plan_reply_names_no_button_and_no_component(lang):
    # the buttons' labels follow the interface language, the reply the question's; users never see which component decided (black box)
    for word in ("Tìm kỹ hơn", "Search deeper", "Vẫn tìm", "Search all", "planner", "kế hoạch", "plan"):
        assert word.lower() not in EMPTY_PLAN_ANSWER[lang].lower()


async def test_the_empty_plan_reply_waits_for_the_guard(monkeypatch):
    # a message the guard turns away gets the guard's reply, not "the sources do not seem to contain this" (the guard is read before anything is shown)
    orch = _empty_plan_orchestrator(monkeypatch, [])
    read = []

    async def cleared():
        read.append(1)

    monkeypatch.setattr(orch, "_cleared", cleared)
    await orch._answer_one(Q["en"], "nb", _scope(), Decision(lang="en"))
    assert read


@pytest.mark.parametrize("lang", ["en", "vi"])
async def test_a_failed_planner_answers_with_the_slow_system_line_and_a_prominent_search_deeper(monkeypatch, lang):
    orch = orchestrator(monkeypatch, [CHUNK])

    async def retrieve(query, notebook_id, scope, forced=None, **kw):
        return RetrievalResult(scope, {"amd": AMD.label, "nv": NV.label}, [], [Q[lang]], [dict(CHUNK)], "r4", {}, degraded=["plan_unavailable"])

    async def gen(*a, **k):
        return "AMD net revenue was 25,785 in 2024 [1].\n" + META % ("answered", "[1]")

    monkeypatch.setattr(orch, "retrieve", retrieve)
    monkeypatch.setattr(orch_mod, "generate_answer", gen)
    r = await orch._answer_one(Q[lang], "nb", _scope(), Decision(lang=lang))
    assert DEGRADED_NOTE[lang] in r["answer"] and r["actions"]["search_more"] == {"prominent": True} and r["charged"] is True


# ---------------------------------------------------------------- the button "search all sources"
def _answer(mid, trace=None):
    return MessageRecord(message_id=mid, notebook_id="nb", role="assistant", content="...", trace_info=trace or {})


def test_search_all_asks_again_over_every_source_of_the_answer_as_tags():
    asked = {"asked": {"document_ids": ["d1", "d2"], "mentions": []}}
    req = chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"], retry_of="m1", everywhere=True)
    assert chat_api.uses_answer_documents(req)  # the sources of the clicked answer, not the sidebar's at click time
    assert chat_api.click_documents(req, _answer("m1", asked), ["d1"], []) == (["d1", "d2"], ["d1", "d2"])  # every one tagged: code vetoes an empty plan


def test_the_other_clicks_keep_their_documents():
    asked = {"asked": {"document_ids": ["d1", "d2"], "mentions": ["d2"]}}
    deeper = chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"], retry_of="m1", deeper=True)
    chooser = chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1", "d2"], mentions=["d1"], retry_of="m1")
    assert chat_api.click_documents(deeper, _answer("m1", asked), ["d1"], []) == (["d1", "d2"], ["d2"])
    assert chat_api.click_documents(chooser, _answer("m1", asked), ["d1", "d2"], ["d1"]) == (["d1", "d2"], ["d1"])  # the chooser's ticks


def test_the_answer_to_search_all_is_marked_and_the_clicked_answer_loses_the_button():
    class Orchestrator:
        async def execute_query(self, **kw):
            return {"answer": "x", "intent": "retrieval_rag", "citations": [], "trace": {}}

    import asyncio

    clicked = _answer("m1", {"actions": {"search_all": True, "chooser": [{"document_id": "d1"}]}})
    adm = chat_api._Admitted(types.SimpleNamespace(focus_state={}), ["d1", "d2"], ["d1", "d2"], Orchestrator(), [], None, retry_of=clicked)
    req = chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"], retry_of="m1", everywhere=True)
    assert asyncio.run(chat_api._answered(adm, req, "u1"))["trace"]["click"] == "everywhere"
    shown = chat_api.shown_messages([clicked, _answer("m2", {"retry_of": "m1", "click": "everywhere"})])
    assert shown[0].clicked == "everywhere" and shown[0].actions["search_all"] is False and shown[0].actions["chooser"] == []
