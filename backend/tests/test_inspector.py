"""The admin inspector (/retrieval/research) runs the chat's own steps up to the search, so it shows what the chat really does: the
same stop, the same decision, the same forced filings. No network, no GPU, no database."""
import types

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.auth.user import UserRecord
from app.modules.chat import inspector
from app.modules.chat.chat import validate_question
from app.modules.notebooks.notebook import NotebookRecord
from app.modules.query_router.intent import Intent
from app.shared.deps import get_current_user
from tests.test_input_policy import HIST, NIKE_DOCS, _doc, _orchestrator

KO = _doc("k", "ko.pdf", company_name="The Coca-Cola Company", fiscal_year=2022, report_type="10-K")
PEP = _doc("p", "pep.pdf", company_name="PepsiCo, Inc", fiscal_year=2022, report_type="10-K")


async def test_an_unconfirmed_document_stops_both_before_any_search(monkeypatch):
    unconfirmed = _doc("u", "unknown.pdf", fiscal_year=2023)  # no company name: nobody confirmed what this document is
    orch, _ = _orchestrator([unconfirmed], monkeypatch)
    chat = await orch.execute_query("What was the revenue?", "nb", document_ids=["u"])
    seen = await orch.inspect_question("What was the revenue?", "nb", document_ids=["u"])
    assert chat["intent"] == seen["decision"] == "ask_confirm_catalog" and seen["parts"] == []
    assert not orch.hybrid_search.calls


async def test_small_talk_the_router_blocks_is_not_searched_by_either(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod

    async def router(question, embed, evidence=()):
        return Intent("small_talk", 0.9, 0.5, True)

    orch, _ = _orchestrator(NIKE_DOCS[1:], monkeypatch)
    orch.hybrid_search.embedder = types.SimpleNamespace(embed_queries=None)
    monkeypatch.setattr(settings, "INTENT_ROUTER_ENABLED", True)
    monkeypatch.setattr(orch_mod, "classify_intent", router)
    chat = await orch.execute_query("bạn ổn không ?", "nb", document_ids=["d2"])
    seen = await orch.inspect_question("bạn ổn không ?", "nb", document_ids=["d2"])
    assert chat["intent"] == seen["decision"] == "static_reply" and seen["intent"]["label"] == "small_talk"
    assert not orch.hybrid_search.calls


async def test_a_follow_up_is_searched_as_its_rewrite(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod

    async def rewrite(q, history):
        return "What was Nike's net income in FY2023?"

    orch, _ = _orchestrator(NIKE_DOCS[1:], monkeypatch)
    monkeypatch.setattr(orch_mod, "rewrite_followup", rewrite)
    seen = await orch.inspect_question("And the net income?", "nb", document_ids=["d2"], history=HIST)
    assert seen["searched_query"] == seen["parts"][0]["query"] == "What was Nike's net income in FY2023?"
    assert seen["followup"] == {"method": "llm", "resolved": "What was Nike's net income in FY2023?"} and seen["parts"][0]["chunks"]


async def test_a_comparison_with_a_company_outside_the_sources_is_answered_by_both(monkeypatch):
    orch, _ = _orchestrator(NIKE_DOCS[:1], monkeypatch, listed=["Tesla"])
    question = "Compare Nike's revenue with Tesla's revenue"
    chat = await orch.execute_query(question, "nb", document_ids=["d1"])
    part = (await orch.inspect_question(question, "nb", document_ids=["d1"]))["parts"][0]
    assert chat["intent"] != "out_of_scope" and not part.get("refused") and part["chunks"]
    assert any("Tesla" in n for n in part["notes"])
    part = (await orch.inspect_question("What was Tesla's revenue?", "nb", document_ids=["d1"]))["parts"][0]
    assert part["refused"] is True and "Tesla" in part["message"]


async def test_a_named_company_forces_the_same_filing_in_both(monkeypatch):
    orch, _ = _orchestrator([KO, PEP], monkeypatch)
    question = "What was PepsiCo's revenue in 2022?"
    chat = await orch.execute_query(question, "nb", document_ids=["k", "p"])
    part = (await orch.inspect_question(question, "nb", document_ids=["k", "p"]))["parts"][0]
    assert part["targets"] == chat["trace"]["targets"] and part["targets"]["documents"] == ["p"]
    assert part["routing"] == chat["trace"]["routing"]


async def test_several_questions_are_inspected_one_by_one(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod

    async def rewrite(q, history):
        return "What is Nike's " + ("total assets?" if "assets" in q else "net income?")

    orch, _ = _orchestrator(NIKE_DOCS[1:], monkeypatch)
    monkeypatch.setattr(orch_mod, "rewrite_followup", rewrite)
    seen = await orch.inspect_question("What is Nike's revenue? How about its total assets? And its net income?", "nb", document_ids=["d2"])
    assert seen["decision"]["action"] == "split_questions" and len(seen["parts"]) == 3
    assert [p["query"] for p in seen["parts"]][1] == "What is Nike's total assets?"


async def test_an_overview_shows_the_excerpts_the_chat_would_use(monkeypatch):
    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    seen = await orch.inspect_question("Summarize all the files", "nb", document_ids=["d1", "d2"])
    assert seen["decision"]["action"] == "overview" and len(seen["parts"][0]["chunks"]) == 2


def test_the_inspector_checks_a_question_like_the_chat():
    with pytest.raises(HTTPException) as exc:  # an administrator has the same limit as every signed-in account
        validate_question([f"d{i}" for i in range(settings.MAX_SELECTED_DOCS_USER + 1)], None, None, "q", signed_in=True)
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException):
        validate_question(["d1"], None, ["d2"], "q", signed_in=True)  # only a selected source can be tagged


def test_an_administrator_gets_the_inspection_with_the_conversation_and_topic(monkeypatch):
    nb = NotebookRecord(notebook_id="nb", owner_id="a", title="t", focus_state={"document_ids": ["d1"], "fiscal_years": [2023], "metric": "revenue"})
    received = {}

    async def notebook(db, notebook_id, user_id, write=False):
        return nb

    async def ready(*a):
        return None

    async def history(db, notebook_id):
        return HIST

    class Orchestrator:
        def __init__(self, db, qdrant):
            pass

        async def inspect_question(self, query, notebook_id, **kw):
            received.update(kw)
            return {"query": query, "parts": []}

    monkeypatch.setattr(inspector, "require_notebook", notebook)
    monkeypatch.setattr(inspector, "ensure_documents_ready", ready)
    monkeypatch.setattr(inspector, "load_history", history)
    monkeypatch.setattr(inspector, "RAGWorkflowOrchestrator", Orchestrator)
    app = FastAPI()
    app.include_router(inspector.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_qdrant_client] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: UserRecord(user_id="a", email="a@example.com", username="admin", hashed_password="x", role="admin")
    r = TestClient(app).post("/retrieval/research", json={"notebook_id": "nb", "query": "and net income?", "document_ids": ["d1"], "mentions": ["d1"]})
    assert r.status_code == 200
    assert received == {"document_ids": ["d1"], "history": HIST, "mentions": ["d1"], "focus_state": nb.focus_state}
