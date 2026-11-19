"""Owner's check 18/11/2026: a question is 5 to 5000 characters, and a reply to a message too short to show its language ("?") follows the
interface language, not English by default."""
import pytest

from app.modules.chat import chat as chat_api
from app.modules.query_router.input_policy import MSG, decide
from tests.test_input_policy import NIKE23


@pytest.mark.parametrize("q", ["abcd", "  EPS ", "????"])
def test_fewer_than_five_characters_is_refused(q):
    assert decide(q, [NIKE23], 1).action == "reject_input"


def test_five_characters_pass_the_length_check():
    assert decide("Sales", [NIKE23], 1).action != "reject_input"


def test_up_to_five_thousand_characters_pass_and_one_more_is_refused():
    long_q = "What was Nike's revenue in FY2023? " + "x" * (5000 - 35)
    assert len(long_q) == 5000 and decide(long_q, [NIKE23], 1).action != "reject_input"
    assert decide(long_q + "x", [NIKE23], 1).action == "reject_input"


def test_the_endpoint_limit_is_five_thousand():
    assert chat_api.MAX_QUERY_CHARS == 5000


@pytest.mark.parametrize("ui", ["vi", "en"])
def test_a_message_without_language_on_a_new_chat_follows_the_interface(ui):
    d = decide("?", [NIKE23], 1, [], ui_lang=ui)
    assert d.lang == ui and d.message == MSG["reject_input"][ui]


def test_the_previous_question_still_wins_over_the_interface():
    hist = [{"role": "user", "content": "What was Nike's revenue in FY2023?"}]
    assert decide("ok", [NIKE23], 1, hist, ui_lang="vi").lang == "en"


def test_a_question_that_shows_its_language_keeps_it():
    assert decide("What was Nike's revenue in FY2023?", [NIKE23], 1, [], ui_lang="vi").lang == "en"
    assert decide("Doanh thu của Nike năm 2023 là bao nhiêu?", [NIKE23], 1, [], ui_lang="en").lang == "vi"


async def test_the_interface_language_reaches_the_rules(monkeypatch):
    from app.modules.chat.orchestrator import RAGWorkflowOrchestrator
    from tests.test_validation import _scope

    orch = RAGWorkflowOrchestrator.__new__(RAGWorkflowOrchestrator)
    scope = _scope()

    async def resolve(*a, **k):
        return scope

    async def ready(*a, **k):
        return scope

    monkeypatch.setattr(orch, "resolve_scope", resolve)
    monkeypatch.setattr(orch, "_ready_documents", ready)
    r = await orch._execute_query("?", "nb", document_ids=[d.document_id for d in scope], ui_lang="vi")
    assert r["answer"] == MSG["reject_input"]["vi"] and r["charged"] is False


async def test_the_chat_endpoint_sends_the_interface_language(monkeypatch):
    from app.modules.notebooks.notebook import NotebookRecord
    from tests.test_conversation_focus import _ask

    seen = {}
    await _ask(monkeypatch, NotebookRecord(notebook_id="nb", owner_id="u"),
               {"answer": "x", "intent": "reject_input", "citations": [], "charged": False, "trace": {}}, "?", ui_lang="vi", seen=seen)
    assert seen["ui_lang"] == "vi"


# ------------------------------------------------------------------ the refusal says which limit (system test 18/11, C9)
def test_a_too_short_question_is_told_it_is_too_short_not_too_long():
    for ui in ("vi", "en"):
        d = decide("?", [NIKE23], 1, ui_lang=ui)
        assert d.action == "reject_input" and d.message == MSG["reject_input"][ui]
    assert "ngắn" in MSG["reject_input"]["vi"] and "dài" not in MSG["reject_input"]["vi"]
    assert "short" in MSG["reject_input"]["en"] and "long" not in MSG["reject_input"]["en"]


def test_a_too_long_question_is_told_it_is_too_long_and_the_limit():
    d = decide("What was revenue? " + "x" * 5000, [NIKE23], 1)
    assert d.action == "reject_input" and d.message == MSG["reject_long"]["en"]
    assert "5,000" in MSG["reject_long"]["en"] and "5.000" in MSG["reject_long"]["vi"] and "dài" in MSG["reject_long"]["vi"]
