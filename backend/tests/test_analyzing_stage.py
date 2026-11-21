"""T6a (owner 20/11): the wait before the first word of an answer is the model thinking (measured: the first text arrives at 8 s for one report, 30 s for several). The streamed chat now
says "analyzing the figures" from the moment the model's first reasoning piece arrives, and the page counts the seconds from then. Backend half: the reasoning piece is reported once,
before any text; the stage event is sent once; only the first answer of a request reports it. No network, no model: the DeepSeek API is faked as in test_chat_stream.py."""
import httpx
import pytest

from app.modules.chat import events
from app.modules.generation import generator, llm_client
from tests.test_chat_stream import _sse_body, model  # noqa: F401  (the fake DeepSeek API)

ASK = [{"role": "user", "content": "q"}]


async def test_the_first_reasoning_piece_is_reported_once_and_before_any_text(model):  # noqa: F811
    model.reply = lambda body: httpx.Response(200, text=_sse_body(
        {"choices": [{"delta": {"reasoning_content": "thinking "}}]},
        {"choices": [{"delta": {"reasoning_content": "more..."}}]},
        {"choices": [{"delta": {"content": "Net income "}}]},
        {"choices": [{"delta": {"content": "was 5."}, "finish_reason": "stop"}]},
    ))
    seen = []
    text = await llm_client.chat_completion(ASK, on_delta=seen.append, on_thinking=lambda: seen.append("<thinking>"))
    assert text == "Net income was 5." and seen == ["<thinking>", "Net income ", "was 5."]


async def test_a_reply_without_reasoning_never_reports_thinking(model):  # noqa: F811
    model.reply = lambda body: httpx.Response(200, text=_sse_body({"choices": [{"delta": {"content": "Short."}, "finish_reason": "stop"}]}))
    calls = []
    await llm_client.chat_completion(ASK, on_delta=lambda p: None, on_thinking=lambda: calls.append(1))
    assert calls == []


async def test_a_retry_does_not_report_thinking_again(model):  # noqa: F811
    attempts = []

    def reply(body):  # the first attempt thinks and is cut at the token budget; the retry thinks again
        attempts.append(1)
        text = {"choices": [{"delta": {"content": "Half" if len(attempts) == 1 else "Whole."}, "finish_reason": "length" if len(attempts) == 1 else "stop"}]}
        return httpx.Response(200, text=_sse_body({"choices": [{"delta": {"reasoning_content": "hm"}}]}, text))

    model.reply = reply
    calls = []
    await llm_client.chat_completion(ASK, on_delta=lambda p: None, on_thinking=lambda: calls.append(1))
    assert len(attempts) == 2 and calls == [1]


async def test_thinking_is_ignored_when_nobody_listens(model):  # noqa: F811
    model.reply = lambda body: httpx.Response(200, text=_sse_body(
        {"choices": [{"delta": {"reasoning_content": "hm"}}]}, {"choices": [{"delta": {"content": "Fine."}, "finish_reason": "stop"}]}))
    assert await llm_client.chat_completion(ASK, stream=True) == "Fine."


# ---------------------------------------------------------------- the stage event
def test_the_analyzing_stage_is_sent_once_however_often_it_is_asked():
    stream = events.ChatStream()
    token = events._STREAM.set(stream)
    try:
        events.analyzing()
        events.analyzing()
    finally:
        events._STREAM.reset(token)
    assert [stream.queue.get_nowait() for _ in range(stream.queue.qsize())] == [("stage", {"name": "analyzing"})]


def test_outside_a_streamed_chat_the_analyzing_stage_does_nothing():
    token = events._STREAM.set(None)
    try:
        events.analyzing()
    finally:
        events._STREAM.reset(token)


# ---------------------------------------------------------------- the answer call reports it
@pytest.mark.parametrize("streamed", [True, False])
async def test_only_the_streamed_first_answer_asks_to_be_told_when_the_model_starts_thinking(monkeypatch, streamed):
    seen = {}

    async def fake(messages, **kwargs):
        seen.update(kwargs)
        return "answer"

    monkeypatch.setattr(generator, "chat_completion", fake)
    monkeypatch.setattr(generator, "build_context", lambda chunks: "ctx")
    monkeypatch.setattr(generator, "build_messages", lambda *a, **k: ASK)
    monkeypatch.setattr(generator.settings, "OUTPUT_POLICY_ENABLED", False)
    token = events._STREAM.set(events.ChatStream() if streamed else None)
    try:
        await generator.generate_answer("q", [{"document_id": "d"}])
    finally:
        events._STREAM.reset(token)
    assert (seen.get("on_thinking") is events.analyzing) is streamed
