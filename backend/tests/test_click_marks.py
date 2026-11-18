"""Which button asked a question again is kept, so the interface can mark it (owner 18/11/2026: a click sent the same question again and looked
like a duplicate; the user could not tell a deeper search from a new question). The answer to a click carries `click` ("deeper" | "again" |
"chooser"); the answer that was clicked carries `clicked`, also after a reload."""
import asyncio
import types

from app.modules.chat import chat as chat_api
from app.modules.chat.chat_models import MessageRecord


class Orchestrator:
    async def execute_query(self, **kw):
        return {"answer": "x", "intent": "retrieval_rag", "citations": [], "trace": {}}


def answer(mid, trace=None):
    return MessageRecord(message_id=mid, notebook_id="nb", role="assistant", content="...", trace_info=trace or {})


def run(**flags):
    clicked = answer("m1", {"chunk_ids": ["a1"]})
    adm = chat_api._Admitted(types.SimpleNamespace(focus_state={}), ["d1"], [], Orchestrator(), [], None, retry_of=clicked)
    req = chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"], retry_of="m1", **flags)
    return asyncio.run(chat_api._answered(adm, req, "u1"))


def test_the_answer_to_a_click_records_which_button_asked():
    assert run(deeper=True)["trace"]["click"] == "deeper"
    assert run(again=True)["trace"]["click"] == "again"
    assert run()["trace"]["click"] == "chooser"


def test_a_question_that_is_no_click_records_none():
    adm = chat_api._Admitted(types.SimpleNamespace(focus_state={}), ["d1"], [], Orchestrator(), [], None)
    r = asyncio.run(chat_api._answered(adm, chat_api.QueryRequest(notebook_id="nb", query="q", document_ids=["d1"]), "u1"))
    assert "click" not in r["trace"]


def test_a_reloaded_chat_marks_the_click_and_the_answer_it_was_made_on():
    shown = chat_api.shown_messages([answer("m1"), answer("m2", {"retry_of": "m1", "click": "deeper"}), answer("m3")])
    by_id = {m.message_id: m for m in shown}
    assert by_id["m1"].clicked == "deeper" and by_id["m1"].click == ""
    assert by_id["m2"].click == "deeper" and by_id["m2"].clicked == ""
    assert by_id["m3"].click == "" and by_id["m3"].clicked == ""


def test_an_older_click_without_its_kind_still_marks_the_answer_it_was_made_on():
    shown = chat_api.shown_messages([answer("m1"), answer("m2", {"retry_of": "m1"})])
    assert shown[0].clicked == "retry" and shown[1].click == "retry"  # stored before 18/11 without its kind: it may have been either button, so a neutral mark
