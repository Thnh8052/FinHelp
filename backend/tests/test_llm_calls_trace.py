"""The trace of a question lists every language-model call it made, one record each: what the call was for, its seconds (with retries), the seconds to the first
piece of text of a streamed one, how it ended and its tokens. Until now the trace kept only the sum of the request (trace["llm"])."""
import httpx
import pytest

from app.core.config import settings
from app.modules.chat.orchestrator import RAGWorkflowOrchestrator
from app.modules.generation import llm_client

USAGE = {"prompt_tokens": 100, "completion_tokens": 30, "prompt_cache_hit_tokens": 60, "prompt_cache_miss_tokens": 40, "completion_tokens_details": {"reasoning_tokens": 20}}


class Client:
    """Answers the queued replies in order; an exception in the queue is raised."""

    def __init__(self, replies):
        self.replies = list(replies)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        finish, content, usage = reply
        return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": {"content": content}}], "usage": usage})


@pytest.fixture
def replies(monkeypatch):
    queue = []
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "k")
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", lambda timeout: Client(queue))

    async def no_wait(seconds):
        return None

    monkeypatch.setattr(llm_client.asyncio, "sleep", no_wait)
    return queue


@pytest.fixture
def calls():
    record = []
    token = llm_client.REQUEST_CALLS.set(record)
    yield record
    llm_client.REQUEST_CALLS.reset(token)


async def test_a_call_leaves_one_record_with_its_purpose_seconds_and_tokens(replies, calls):
    replies.append(("stop", "ok", USAGE))
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}], purpose="guard") == "ok"
    assert len(calls) == 1
    rec = calls[0]
    assert rec["purpose"] == "guard" and rec["status"] == "ok" and rec["attempts"] == 1
    assert isinstance(rec["seconds"], float) and rec["seconds"] >= 0 and rec["first_piece_seconds"] is None  # not streamed: no first piece
    assert (rec["prompt_tokens"], rec["completion_tokens"], rec["reasoning_tokens"]) == (100, 30, 20)
    assert (rec["prompt_cache_hit_tokens"], rec["prompt_cache_miss_tokens"]) == (60, 40)


async def test_a_cut_reply_that_is_asked_again_is_one_record_with_both_attempts_counted(replies, calls):
    replies += [("length", "", USAGE), ("stop", "done", USAGE)]
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}], purpose="plan") == "done"
    assert len(calls) == 1 and calls[0]["attempts"] == 2 and calls[0]["status"] == "ok"
    assert calls[0]["completion_tokens"] == 60 and calls[0]["prompt_tokens"] == 200  # what the request paid for, both replies


async def test_a_call_that_never_answers_is_recorded_as_failed_and_still_raises(replies, calls):
    replies += [httpx.ConnectError("no route"), httpx.ConnectError("no route")]
    with pytest.raises(llm_client.LLMUnavailableError):
        await llm_client.chat_completion([{"role": "user", "content": "q"}], purpose="answer", retries=2)
    assert len(calls) == 1 and calls[0]["status"] == "failed" and calls[0]["attempts"] == 2 and calls[0]["purpose"] == "answer"
    assert calls[0].get("completion_tokens", 0) == 0


async def test_a_reply_cut_at_the_ceiling_is_recorded_as_truncated(replies, calls):
    replies += [("length", "", USAGE)] * 4
    with pytest.raises(llm_client.LLMTruncatedError):
        await llm_client.chat_completion([{"role": "user", "content": "q"}], purpose="answer")
    assert calls[0]["status"] == "truncated" and calls[0]["attempts"] == 2


async def test_a_streamed_call_records_the_seconds_to_its_first_piece(monkeypatch, calls):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "k")
    seen = []

    async def streamed(client, url, headers, payload, on_delta):
        on_delta("The ")
        on_delta("answer")
        llm_client._record_usage(USAGE)
        return 200, "The answer", "stop"

    monkeypatch.setattr(llm_client, "_streamed", streamed)
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", lambda timeout: Client([]))
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}], purpose="answer", on_delta=seen.append) == "The answer"
    assert seen == ["The ", "answer"]  # the listener still gets every piece
    rec = calls[0]
    assert rec["first_piece_seconds"] is not None and 0 <= rec["first_piece_seconds"] <= rec["seconds"] and rec["completion_tokens"] == 30


async def test_without_a_request_to_record_into_a_call_works_as_before(replies):
    replies.append(("stop", "ok", USAGE))
    assert llm_client.REQUEST_CALLS.get() is None
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}], purpose="guard") == "ok"


async def test_the_trace_of_a_question_lists_its_calls(monkeypatch):
    async def guarded(self, query, notebook_id, **kwargs):
        llm_client.REQUEST_CALLS.get().append({"purpose": "guard", "seconds": 0.8, "status": "ok", "attempts": 1})
        llm_client.REQUEST_CALLS.get().append({"purpose": "answer", "seconds": 9.5, "status": "ok", "attempts": 1})
        return {"answer": "A", "intent": "x", "trace": {}}

    monkeypatch.setattr(RAGWorkflowOrchestrator, "_guarded", guarded)
    orch = RAGWorkflowOrchestrator.__new__(RAGWorkflowOrchestrator)
    result = await orch.execute_query("q", "nb")
    assert [c["purpose"] for c in result["trace"]["llm_calls"]] == ["guard", "answer"]
    assert llm_client.REQUEST_CALLS.get() is None  # reset after the question


@pytest.mark.parametrize("module, name", [("guard", "guard"), ("planner", "plan"), ("decomposer", "decompose"), ("bridge", "bridge"), ("input_policy", "rewrite_followup")])
def test_every_caller_names_what_its_call_is_for(module, name):
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(f"app.modules.query_router.{module}"))
    assert f'purpose="{name}"' in source


def test_the_answer_and_the_outside_company_check_name_their_calls_too():
    import inspect

    from app.modules.generation import generator
    from app.modules.query_router import planner

    assert 'purpose="answer"' in inspect.getsource(generator) and 'purpose="unlisted_check"' in inspect.getsource(planner)
