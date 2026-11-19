"""What a question gets when nothing is found (docs/Version_3/fail_cases.md)."""
import types

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.modules.chat import chat as chat_api
from app.modules.chat import orchestrator as orchestrator_module
from app.modules.chat.chat_models import MessageRecord
from app.modules.chat.orchestrator import RAGWorkflowOrchestrator, RetrievalResult
from app.modules.generation.replies import CHECK_SOURCES, NO_DATA_ANSWER, RETRY_APOLOGY
from app.modules.query_router.planner import PlanItem
from app.modules.query_router.input_policy import Decision
from tests.test_validation import AMD, NV, _scope


def orchestrator(monkeypatch, retrieved, plan=()):
    orch = RAGWorkflowOrchestrator.__new__(RAGWorkflowOrchestrator)

    async def no_unlisted(query, scope):
        return []

    async def retrieve(query, notebook_id, scope, forced=None):
        return RetrievalResult(scope, {"amd": AMD.label, "nv": NV.label}, list(plan), ["revenue"], list(retrieved), "planner", {})

    monkeypatch.setattr(orch, "find_unlisted", no_unlisted)
    monkeypatch.setattr(orch, "retrieve", retrieve)
    return orch


async def test_b7_no_excerpt_is_not_charged(monkeypatch):
    """B7: the search returned nothing, so no answer was written: the fixed reply does not count against the user's quota."""
    orch = orchestrator(monkeypatch, [])
    r = await orch._answer_one("Which company had the higher revenue in 2024?", "nb", _scope(), Decision(lang="en"))
    assert r["answer"] == NO_DATA_ANSWER["en"]
    assert r["charged"] is False

CHUNK = {"chunk_id": "a", "document_id": "amd", "page": 50, "content": "Net revenue 2024 25,785 2023 22,680"}
META = '<answer_meta>{"status": "%s", "short_answer": "x", "citations": %s}</answer_meta>'


def answering(monkeypatch, reply, plan=()):
    orch = orchestrator(monkeypatch, [CHUNK], plan)

    async def answer(query, chunks, notes=None, max_tokens=1200, fallback=True):
        return reply

    monkeypatch.setattr(orch, "_answer", answer)
    return orch


@pytest.mark.parametrize("lang,question", [("en", "How many stores did AMD have?"), ("vi", "AMD có bao nhiêu cửa hàng?")])
async def test_s2_a_not_found_answer_ends_with_check_your_sources(monkeypatch, lang, question):
    orch = answering(monkeypatch, "The excerpts do not show the number of stores.\n" + META % ("not_found", "[]"))
    r = await orch._answer_one(question, "nb", _scope(), Decision(lang=lang))
    assert r["answer"].rstrip().endswith(CHECK_SOURCES[lang])


async def test_s2_an_answered_question_gets_no_check_line(monkeypatch):
    orch = answering(monkeypatch, "AMD net revenue was $25,785 million in 2024 [1].\n" + META % ("answered", "[1]"))
    r = await orch._answer_one("What was AMD's revenue in 2024?", "nb", _scope(), Decision(lang="en"))
    assert CHECK_SOURCES["en"] not in r["answer"]


@pytest.mark.parametrize("lang", ["en", "vi"])
async def test_s2_no_excerpt_reply_also_says_check_your_sources(lang):
    assert NO_DATA_ANSWER[lang].endswith(CHECK_SOURCES[lang])


# ---------------------------------------------------------------- S3: several files, buttons to search again
PLAN_AMD_ONLY = [PlanItem("revenue", ["amd"])]  # the planner left NVIDIA out
PARTIAL = "AMD net revenue was $25,785 million in 2024 [1]. NVIDIA's figure was not found.\n" + META % ("partial", "[1]")


async def test_s3_a_partial_answer_over_several_files_offers_the_document_chooser_and_a_prominent_search_more(monkeypatch):
    # 17/11 (CODE_MODEL_DECISIONS 4.2): one chooser where several files can be ticked replaces the one-file buttons
    orch = answering(monkeypatch, PARTIAL, PLAN_AMD_ONLY)
    r = await orch._answer_one("Which company had the higher revenue in 2024?", "nb", _scope(), Decision(lang="en"))
    assert r["alternatives"] == []
    assert [(c["document_id"], c["checked"]) for c in r["actions"]["chooser"]] == [("amd", True), ("nv", False)]
    assert r["actions"]["search_more"] == {"prominent": True}


async def test_s3_an_answered_question_where_the_planner_chose_one_of_two_companies_shows_the_chooser_quietly(monkeypatch):
    orch = answering(monkeypatch, "AMD net revenue was $25,785 million in 2024 [1].\n" + META % ("answered", "[1]"), PLAN_AMD_ONLY)
    r = await orch._answer_one("Which company had the higher revenue in 2024?", "nb", _scope(), Decision(lang="en"))
    assert r["alternatives"] == [] and r["actions"]["search_more"] == {"prominent": False}
    assert [c["checked"] for c in r["actions"]["chooser"]] == [True, False] and r["understood"].startswith("I understood the question as about:")


async def test_s3_one_selected_file_gets_no_s3_buttons(monkeypatch):
    """One file: the "search deeper" button of S5 (it needs the first round's excerpts left out to be worth a click)."""
    orch = answering(monkeypatch, PARTIAL)
    r = await orch._answer_one("How many stores did AMD have?", "nb", _scope()[:1], Decision(lang="en"))
    assert r["alternatives"] == []


async def test_s3_a_question_tied_to_a_file_gets_no_s3_buttons(monkeypatch):
    """A question that names its company (or tags a file) is B3: unchanged here."""
    orch = answering(monkeypatch, PARTIAL)
    r = await orch._answer_one("What was Advanced Micro Devices' revenue in 2024?", "nb", _scope(), Decision(lang="en"))
    assert r["alternatives"] == []


@pytest.mark.parametrize("status", ["partial", "not_found"])
async def test_s3_the_click_gets_no_more_buttons_and_an_apology_when_it_still_fails(monkeypatch, status):
    orch = answering(monkeypatch, "NVIDIA's figure was not found.\n" + META % (status, "[]"), PLAN_AMD_ONLY)
    r = await orch._answer_one("Which company had the higher revenue in 2024?", "nb", _scope(), Decision(lang="vi"), retry=True)
    assert r["alternatives"] == []
    assert r["answer"].rstrip().endswith(RETRY_APOLOGY["vi"]) and CHECK_SOURCES["vi"] not in r["answer"].replace(RETRY_APOLOGY["vi"], "")


async def test_s3_a_click_that_answers_gets_no_apology(monkeypatch):
    orch = answering(monkeypatch, "AMD net revenue was $25,785 million in 2024 [1].\n" + META % ("answered", "[1]"), PLAN_AMD_ONLY)
    r = await orch._answer_one("Which company had the higher revenue in 2024?", "nb", _scope(), Decision(lang="en"), retry=True)
    assert RETRY_APOLOGY["en"] not in r["answer"]


# ---------------------------------------------------------------- S3: the click reaches the API as retry_of (the answer it searches again for)


class Messages:
    def __init__(self, *records):
        self.records = list(records)

    async def get_messages(self, notebook_id, limit=500):
        return [m for m in self.records if m.notebook_id == notebook_id]


ASKED = MessageRecord(message_id="m1", notebook_id="nb", role="user", content="Which company had the higher revenue?")
ANSWERED = MessageRecord(message_id="m2", notebook_id="nb", role="assistant", content="AMD ... [1].")


async def test_s3_retry_of_names_an_answer_of_this_notebook():
    assert (await chat_api.retried_message(Messages(ASKED, ANSWERED), "nb", "m2")).message_id == "m2"
    assert await chat_api.retried_message(Messages(ASKED, ANSWERED), "nb", None) is None


@pytest.mark.parametrize("message_id,notebook_id", [("nope", "nb"), ("m1", "nb"), ("m2", "other")])
async def test_s3_retry_of_anything_else_is_refused(message_id, notebook_id):
    """An unknown id, a question instead of an answer, an answer of another notebook: 404 before any quota is reserved."""
    with pytest.raises(HTTPException) as refused:
        await chat_api.retried_message(Messages(ASKED, ANSWERED), notebook_id, message_id)
    assert refused.value.status_code == 404 and refused.value.detail["code"] == "message_not_found"


async def test_s3_a_click_is_answered_as_a_retry_and_remembered_in_the_trace():
    seen = {}

    class Orchestrator:
        async def execute_query(self, **kw):
            seen.update(kw)
            return {"answer": "x", "intent": "retrieval_rag", "citations": [], "trace": {}}

    adm = chat_api._Admitted(types.SimpleNamespace(focus_state={}), ["amd", "nv"], ["nv"], Orchestrator(), [], None, retry_of=ANSWERED)
    req = chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["amd", "nv"], mentions=["nv"], retry_of="m2")
    result = await chat_api._answered(adm, req, "u1")
    assert seen["retry"] is True and result["trace"]["retry_of"] == "m2"


async def test_s3_alternatives_are_kept_in_the_trace_so_a_reloaded_chat_shows_the_buttons(monkeypatch):
    orch = RAGWorkflowOrchestrator.__new__(RAGWorkflowOrchestrator)
    buttons = [{"document_id": "all", "label": "", "document_ids": ["amd", "nv"], "kind": "retry_all"}]

    async def guarded(query, notebook_id, **kw):
        return {"answer": "x", "intent": "retrieval_rag", "citations": [], "alternatives": buttons, "trace": {}}

    monkeypatch.setattr(orch, "_guarded", guarded)
    r = await orch.execute_query("q", "nb")
    assert r["trace"]["alternatives"] == buttons


# ---------------------------------------------------------------- one click only, enforced by the server
RETRIED = MessageRecord(message_id="m4", notebook_id="nb", role="assistant", content="...", trace_info={"retry_of": "m2"})


@pytest.mark.parametrize("message_id", ["m2", "m4"])
async def test_s3_an_answer_already_searched_again_or_a_retry_itself_cannot_be_searched_again(message_id):
    with pytest.raises(HTTPException) as refused:
        await chat_api.retried_message(Messages(ASKED, ANSWERED, RETRIED), "nb", message_id)
    assert refused.value.status_code == 409 and refused.value.detail["code"] == "retry_used"


def test_s3_a_reloaded_chat_shows_no_search_again_button_on_an_answer_already_searched_again():
    buttons = [{"document_id": "all", "label": "", "document_ids": ["amd", "nv"], "kind": "retry_all"}, {"document_id": "nv", "label": "NVIDIA"}]
    answered = MessageRecord(message_id="m2", notebook_id="nb", role="assistant", content="...", trace_info={"alternatives": buttons})
    shown = chat_api.shown_messages([ASKED, answered, RETRIED])
    assert shown[1].alternatives == [{"document_id": "nv", "label": "NVIDIA"}]  # an alternative of the router stays


@pytest.mark.parametrize("lang,scope_words", [("vi", "các nguồn đã chọn"), ("en", "the selected sources")])
def test_the_no_excerpt_reply_names_the_selected_sources_not_the_notebook(lang, scope_words):
    # owner's check 18/11/2026: only the selected sources are searched, never every document of the notebook
    first = NO_DATA_ANSWER[lang].split(". ")[0]
    assert scope_words in first and "notebook" not in NO_DATA_ANSWER[lang]
