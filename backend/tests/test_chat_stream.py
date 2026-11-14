"""The streamed chat (POST /chat/query/stream): the model's reply read piece by piece, the <answer_meta> block never shown, and the
route's events. No database, no network, no language model: everything outside the code under test is faked."""
import json
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.chat import chat as chat_api
from app.modules.chat import events
from app.modules.generation import llm_client
from app.modules.generation.generator import hold_meta
from app.shared.deps import get_optional_user_id


# ---------------------------------------------------------------- the <answer_meta> block stays hidden
def _fed(pieces):
    sent = []
    feed = hold_meta(sent.append)
    for p in pieces:
        feed(p)
    return sent


def test_the_meta_block_is_never_sent_even_when_its_tag_is_split():
    sent = _fed(["Revenue was **10** [1].", "\n<ans", "wer_meta>{\"status\": \"answered\"}", "</answer_meta>"])
    assert "".join(sent) == "Revenue was **10** [1].\n"


def test_text_that_only_looks_like_the_tag_is_sent_once_it_is_clearly_not():
    assert "".join(_fed(["a <", "b> c"])) == "a <b> c"


def test_an_answer_without_a_block_is_sent_whole():
    assert "".join(_fed(["One ", "two ", "three."])) == "One two three."


# ---------------------------------------------------------------- the streamed model call
def _sse_body(*chunks):
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


@pytest.fixture
def model(monkeypatch):
    """The DeepSeek API replaced by `model.reply`, a function of the request body that returns an httpx.Response."""
    state = types.SimpleNamespace(bodies=[], reply=None)

    def handler(request):
        body = json.loads(request.content)
        state.bodies.append(body)
        return state.reply(body)

    real = httpx.AsyncClient
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    return state


async def test_a_streamed_reply_arrives_piece_by_piece_without_the_reasoning(model):
    model.reply = lambda body: httpx.Response(200, text=_sse_body(
        {"choices": [{"delta": {"reasoning_content": "thinking..."}}]},
        {"choices": [{"delta": {"content": "Net income "}}]},
        {"choices": [{"delta": {"content": "was 5."}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 4}},
    ))
    pieces = []

    text = await llm_client.chat_completion([{"role": "user", "content": "q"}], on_delta=pieces.append)

    assert text == "Net income was 5." and pieces == ["Net income ", "was 5."]
    assert model.bodies[0]["stream"] is True and model.bodies[0]["stream_options"] == {"include_usage": True}


async def test_a_retry_after_a_streamed_attempt_is_received_as_a_stream_but_not_shown_again(model):
    attempts = []

    def reply(body):  # the first attempt is cut at the token budget: retried with a larger one
        attempts.append(body["max_tokens"])
        if len(attempts) == 1:
            return httpx.Response(200, text=_sse_body({"choices": [{"delta": {"content": "Half"}, "finish_reason": "length"}]}))
        return httpx.Response(200, text=_sse_body({"choices": [{"delta": {"content": "The whole answer."}, "finish_reason": "stop"}]}))

    model.reply = reply
    pieces = []

    text = await llm_client.chat_completion([{"role": "user", "content": "q"}], on_delta=pieces.append)

    assert text == "The whole answer." and pieces == ["Half"]  # the caller shows the returned text: the streamed half is replaced, the retry's pieces are not sent again
    assert [b.get("stream", False) for b in model.bodies] == [True, True]  # the retry is the longest call: it must be a stream too (L22 follow-up, see below)


async def test_a_call_asked_to_stream_is_received_as_a_stream_without_a_listener(model):
    """Measured 14/11 with a real call: a non-streamed generation sends no byte until it ends (a 39 s one: headers at 0.5 s, the whole body at 39.0 s), so httpx's read timeout
    (80 s) acts as a limit on the whole generation and an answer of more than about 17,000 tokens would never arrive. Received as a stream, bytes arrive all along and
    the timeout only counts silence."""
    model.reply = lambda body: httpx.Response(200, text=_sse_body(
        {"choices": [{"delta": {"reasoning_content": "thinking..."}}]},
        {"choices": [{"delta": {"content": "A long "}}]},
        {"choices": [{"delta": {"content": "answer."}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 4, "completion_tokens_details": {"reasoning_tokens": 2}}},
    ))
    counts = llm_client.Counter()
    token = llm_client.REQUEST_USAGE.set(counts)
    try:
        text = await llm_client.chat_completion([{"role": "user", "content": "q"}], stream=True)
    finally:
        llm_client.REQUEST_USAGE.reset(token)

    assert text == "A long answer." and model.bodies[0]["stream"] is True and model.bodies[0]["stream_options"] == {"include_usage": True}
    assert counts["calls"] == 1 and counts["completion_tokens"] == 4 and counts["reasoning_tokens"] == 2  # the cost of the request is still counted


async def test_every_attempt_of_a_call_asked_to_stream_is_a_stream_and_a_cut_one_is_retried(model):
    attempts = []

    def reply(body):
        attempts.append(body["max_tokens"])
        cut = len(attempts) == 1
        return httpx.Response(200, text=_sse_body({"choices": [{"delta": {"content": "" if cut else "Done."}, "finish_reason": "length" if cut else "stop"}]}))

    model.reply = reply
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}], stream=True) == "Done."
    assert [b.get("stream", False) for b in model.bodies] == [True, True] and attempts[1] == min(2 * attempts[0], settings.LLM_MAX_TOKENS_CEILING)


async def test_every_answer_call_is_received_as_a_stream_the_second_writings_too(monkeypatch):
    """The repair, the answer after the lazy net and the policy rewrite are not shown piece by piece (no listener) but they write as long as the first answer."""
    from app.modules.generation import generator

    seen = []

    async def spy(messages, **kw):
        seen.append(kw)
        return "Revenue was 100 [1]."

    monkeypatch.setattr(generator, "chat_completion", spy)
    chunks = [{"document_id": "d", "page": 1, "content": "Revenue 100", "chunk_id": "c"}]
    await generator.generate_answer("What was revenue?", chunks)  # no listener: a second writing, or a request that is not streamed to the browser
    events.attach(events.ChatStream())
    await generator.generate_answer("What was revenue?", chunks)  # the first answer of a streamed request: it has a listener
    assert [kw.get("stream") for kw in seen] == [True, True]
    assert seen[0]["on_delta"] is None and seen[1]["on_delta"] is not None


async def test_a_call_without_a_listener_is_not_streamed(model):
    model.reply = lambda body: httpx.Response(200, json={"choices": [{"message": {"content": "Plain."}, "finish_reason": "stop"}], "usage": {}})

    assert await llm_client.chat_completion([{"role": "user", "content": "q"}]) == "Plain." and "stream" not in model.bodies[0]


# ---------------------------------------------------------------- which answers stream
async def test_only_the_first_answer_of_a_request_streams():
    stream = events.ChatStream()
    events.attach(stream)

    first, second = events.answer_sink(), events.answer_sink()

    assert first is not None and second is None  # a rewrite after a check is not streamed: the final event carries it


async def test_answers_made_of_several_parts_do_not_stream():
    events.attach(events.ChatStream())
    events.no_answer_stream()

    assert events.answer_sink() is None


async def test_outside_a_streamed_request_nothing_streams():
    assert events.answer_sink() is None
    events.emit("stage", name="searching")  # and emitting is harmless


# ---------------------------------------------------------------- the route
def _events(text):
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.fixture
def stream_api(monkeypatch):
    refunds = []

    class Orchestrator:
        outcome = None

        async def execute_query(self, **kw):
            events.stage("searching")
            events.emit("understood", text="Apple 10-K FY2020", alternatives=[])
            events.writing()
            sink = events.answer_sink()
            sink("Total assets were ")
            sink("323,888.")
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return {"answer": "Total assets were **323,888** [1].", "intent": "retrieval_rag", "citations": [], "trace": {}}

    orch = Orchestrator()

    async def admit(request, req, user_id, db, qdrant):
        async def consume_quota(uid, messages=0, tokens=0):
            refunds.append(messages)

        return chat_api._Admitted(types.SimpleNamespace(focus_state={}, title="x"), ["d1"], [], orch, [],
                                  types.SimpleNamespace(consume_quota=consume_quota))

    async def record(adm, req, user_id, db, result):
        return chat_api.QueryResponse(title="t", query=req.query, answer=result["answer"], citations=[])

    monkeypatch.setattr(chat_api, "_admit", admit)
    monkeypatch.setattr(chat_api, "_record", record)
    app = FastAPI()
    app.include_router(chat_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_qdrant_client] = lambda: None
    app.dependency_overrides[get_optional_user_id] = lambda: "u1"
    return types.SimpleNamespace(client=TestClient(app), orch=orch, refunds=refunds)


def _ask(api):
    response = api.client.post("/chat/query/stream", json={"notebook_id": "nb", "query": "Apple total assets?", "document_ids": ["d1"]})
    return response, _events(response.text)


def test_the_stream_shows_the_stages_the_answer_as_written_then_the_recorded_answer(stream_api):
    response, got = _ask(stream_api)

    assert response.headers["content-type"].startswith("text/event-stream") and response.headers["x-accel-buffering"] == "no"
    assert [k for k, _ in got] == ["stage", "stage", "understood", "stage", "delta", "delta", "done"]
    assert [d["name"] for k, d in got if k == "stage"] == ["understanding", "searching", "writing"]
    assert "".join(d["text"] for k, d in got if k == "delta") == "Total assets were 323,888."
    assert got[-1][1]["answer"] == "Total assets were **323,888** [1]."  # the checked answer replaces the streamed text
    assert stream_api.refunds == []


def test_a_failure_while_answering_is_an_error_event_and_the_question_is_given_back(stream_api):
    stream_api.orch.outcome = ServiceUnavailableError("system_not_ready")

    _, got = _ask(stream_api)

    assert got[-1] == ("error", {"status": 503, "code": "system_not_ready", "params": {}})
    assert stream_api.refunds == [-1]


def test_an_unforeseen_failure_names_no_internal_detail(stream_api):
    stream_api.orch.outcome = RuntimeError("Qdrant exploded at 10.0.0.3")

    _, got = _ask(stream_api)

    assert got[-1] == ("error", {"status": 500, "code": "internal_error", "params": {}}) and "Qdrant" not in json.dumps(got)
