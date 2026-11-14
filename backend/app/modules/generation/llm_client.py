import asyncio
import json
from collections import Counter
from contextvars import ContextVar
from typing import Callable, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.error_codes import Code
from app.core.exceptions import DomainException
from app.core.logging import logger

RETRYABLE_STATUS = {408, 409, 425, 429}
# Token counts of every successful reply in this process (the API's `usage`, retried cut replies included): calls,
# prompt_tokens, completion_tokens, prompt_cache_hit_tokens, prompt_cache_miss_tokens. Read by the evaluation scripts for cost.
USAGE: Counter = Counter()
# The same counts for the request being served (set by the orchestrator, None elsewhere): calls and tokens go into its trace.
REQUEST_USAGE: ContextVar = ContextVar("request_usage", default=None)


class LLMUnavailableError(DomainException):
    """The language-model service has no key, rejected the call, or stayed unreachable after retries."""


def _record_usage(usage: Optional[Dict]) -> None:
    counts = {k: v for k, v in (usage or {}).items() if isinstance(v, int)} | {"calls": 1}
    reasoning = ((usage or {}).get("completion_tokens_details") or {}).get("reasoning_tokens")  # the API nests it; it is already inside completion_tokens
    if isinstance(reasoning, int):
        counts["reasoning_tokens"] = reasoning
    USAGE.update(counts)
    if REQUEST_USAGE.get() is not None:
        REQUEST_USAGE.get().update(counts)


def _drop(piece: str) -> None:
    """The listener of a stream that nobody shows piece by piece."""


async def _streamed(client: httpx.AsyncClient, url: str, headers: Dict, payload: Dict, on_delta: Callable[[str], None]) -> Tuple[int, str, Optional[str]]:
    """(status, content, finish_reason) of a streamed call; every piece of content goes to `on_delta` as it arrives. The reasoning
    of a thinking model (reasoning_content) is not passed on."""
    parts: List[str] = []
    finish: Optional[str] = None
    async with client.stream("POST", url, headers=headers, json={**payload, "stream": True, "stream_options": {"include_usage": True}}) as resp:
        if resp.status_code != 200:
            await resp.aread()
            return resp.status_code, "", None
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            if chunk.get("usage"):
                _record_usage(chunk["usage"])
            for choice in chunk.get("choices") or []:
                piece = (choice.get("delta") or {}).get("content")
                if piece:
                    parts.append(piece)
                    on_delta(piece)
                finish = choice.get("finish_reason") or finish
    return 200, "".join(parts).strip(), finish


async def chat_completion(
    messages: List[Dict[str, str]],
    *,
    max_tokens: int = 1200,
    json_mode: bool = False,
    timeout: float = 80.0,
    retries: int = 4,
    on_delta: Optional[Callable[[str], None]] = None,
    thinking: bool = True,
    stream: bool = False,
) -> str:
    """Call the DeepSeek chat-completions API (temperature 0) with timeout and exponential backoff.
    `max_tokens` is raised to LLM_MIN_MAX_TOKENS: the reasoning of deepseek-flash counts against it, and a small budget made the
    planner come back empty on ambiguous questions (finish_reason 'length', no content). A cut reply is retried with twice the budget.
    With `on_delta` the first attempt's pieces are passed to it as they arrive; a retry is not passed on (the caller receives the whole text
    as the return value and shows that).
    `stream=True` (or an `on_delta`) receives EVERY attempt as a stream even with no one listening. Needed for a call that may write for a long time: measured
    14/11, a non-streamed generation sends no byte until it ends (a 39 s one: headers at 0.5 s, the whole body at 39.0 s), so the read timeout then limits the whole
    generation (80 s is about 17,000 tokens) and a longer answer would time out, be asked again the same way, and fail. A stream sends bytes all along: the timeout
    only counts silence."""
    if not settings.DEEPSEEK_API_KEY:
        raise LLMUnavailableError(Code.LLM_NOT_CONFIGURED)

    payload: Dict = {
        "model": settings.DEFAULT_LLM_MODEL,
        "temperature": 0.0,
        "max_tokens": max(max_tokens, settings.LLM_MIN_MAX_TOKENS),
        "messages": messages,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if not thinking:  # a short classification: no reasoning (DeepSeek: temperature 0 then holds, replies are repeatable)
        payload["thinking"] = {"type": "disabled"}
    headers = {"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    delay = 2.0
    streaming = stream or on_delta is not None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, retries + 1):
            sink, on_delta = on_delta, None  # pieces go to the listener for the first attempt only: those of a second one would repeat the first
            try:
                if streaming:
                    status, content, finish = await _streamed(client, url, headers, payload, sink or _drop)
                else:
                    resp = await client.post(url, headers=headers, json=payload)
                    status, content, finish = resp.status_code, "", None
                    if status == 200:
                        body = resp.json()
                        _record_usage(body.get("usage"))
                        choice = body["choices"][0]
                        content, finish = (choice["message"].get("content") or "").strip(), choice.get("finish_reason")
                if status == 200:
                    if finish == "length" and payload["max_tokens"] < settings.LLM_MAX_TOKENS_CEILING:
                        logger.warning(f"LLM reply cut at max_tokens={payload['max_tokens']}; retrying with a larger budget")
                        payload["max_tokens"] = min(payload["max_tokens"] * 2, settings.LLM_MAX_TOKENS_CEILING)
                        continue
                    return content
                if status < 500 and status not in RETRYABLE_STATUS:
                    # Auth / bad-request errors do not heal by retrying.
                    raise LLMUnavailableError(Code.LLM_REJECTED, status=status)
                logger.warning(f"LLM call attempt {attempt}/{retries}: HTTP {status}")
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                logger.warning(f"LLM call attempt {attempt}/{retries} failed: {type(exc).__name__}")
            if attempt < retries:
                await asyncio.sleep(delay)
                delay = min(delay * 1.6, 20.0)
    raise LLMUnavailableError(Code.LLM_UNAVAILABLE)
