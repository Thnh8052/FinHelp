"""Progress of the question being answered, for the streamed chat (POST /chat/query/stream).

The streamed route attaches a ChatStream to its request; everywhere else emit() and answer_sink() do nothing, so the plain
/chat/query, the inspector and the evaluation scripts behave exactly as before. Events are (kind, data) pairs:
  stage      {"name": "understanding" | "searching" | "writing" | "checking"}   what the system is doing now (never which component)
  understood {"text", "alternatives"}                                            how the question was understood, before the answer
  delta      {"text"}                                                            the next piece of the answer as the model writes it
  done / error                                                                    sent by the route once the answer is recorded or failed
"""
import asyncio
import time
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, Tuple

Event = Tuple[Optional[str], Dict[str, Any]]


class ChatStream:
    def __init__(self) -> None:
        self.queue: "asyncio.Queue[Event]" = asyncio.Queue()
        self.answer_streamed = False  # only the first answer written for the request streams: a rewrite or a second part does not
        self.answer_stream_off = False
        self.first: Dict[str, float] = {}  # kind -> time.perf_counter() of its first event (what the user waited for, into the trace)

    def emit(self, kind: str, data: Dict[str, Any]) -> None:
        self.first.setdefault(kind, time.perf_counter())
        self.queue.put_nowait((kind, data))

    def close(self) -> None:
        self.queue.put_nowait((None, {}))


_STREAM: ContextVar[Optional[ChatStream]] = ContextVar("chat_stream", default=None)


def attach(stream: ChatStream) -> None:
    """Call at the start of the task that answers the question: the steps it awaits (and the tasks they start) see the stream."""
    _STREAM.set(stream)


def emit(kind: str, **data: Any) -> None:
    stream = _STREAM.get()
    if stream is not None:
        stream.emit(kind, data)


def stage(name: str) -> None:
    emit("stage", name=name)


def writing() -> None:
    """The "writing" stage, unless the first answer is already written: a rewrite after a check stays under "checking"."""
    stream = _STREAM.get()
    if stream is not None and not stream.answer_streamed:
        stream.emit("stage", {"name": "writing"})


def no_answer_stream() -> None:
    """For answers assembled from several parts: the final event carries the whole text, nothing is streamed piece by piece."""
    stream = _STREAM.get()
    if stream is not None:
        stream.answer_stream_off = True


def first_seen(since: float) -> Dict[str, float]:
    """Seconds from `since` (time.perf_counter()) to the first understanding line and the first piece of answer text the user was sent:
    {"understood", "first_text"}, only those that happened; {} outside a streamed chat."""
    stream = _STREAM.get()
    if stream is None:
        return {}
    return {key: round(stream.first[kind] - since, 2) for kind, key in (("understood", "understood"), ("delta", "first_text")) if kind in stream.first}


def answer_sink() -> Optional[Callable[[str], None]]:
    """The callback for the answer's pieces, or None: no stream, answers that must not stream, or an answer already streamed."""
    stream = _STREAM.get()
    if stream is None or stream.answer_stream_off or stream.answer_streamed:
        return None
    stream.answer_streamed = True
    return lambda text: stream.emit("delta", {"text": text})
