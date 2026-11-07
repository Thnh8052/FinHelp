import asyncio
from collections import Counter
from contextvars import ContextVar
from typing import Dict, List

import httpx

from app.core.config import settings
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


async def chat_completion(
    messages: List[Dict[str, str]],
    *,
    max_tokens: int = 1200,
    json_mode: bool = False,
    timeout: float = 80.0,
    retries: int = 4,
) -> str:
    """Call the DeepSeek chat-completions API (temperature 0) with timeout and exponential backoff.
    `max_tokens` is raised to LLM_MIN_MAX_TOKENS: the reasoning of deepseek-flash counts against it, and a small budget made the
    planner come back empty on ambiguous questions (finish_reason 'length', no content). A cut reply is retried with twice the budget."""
    if not settings.DEEPSEEK_API_KEY:
        raise LLMUnavailableError("Chưa cấu hình khóa dịch vụ ngôn ngữ (DEEPSEEK_API_KEY).")

    payload: Dict = {
        "model": settings.DEFAULT_LLM_MODEL,
        "temperature": 0.0,
        "max_tokens": max(max_tokens, settings.LLM_MIN_MAX_TOKENS),
        "messages": messages,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

    delay = 2.0
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, retries + 1):
            try:
                resp = await client.post(f"{settings.LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    body = resp.json()
                    counts = {k: v for k, v in (body.get("usage") or {}).items() if isinstance(v, int)} | {"calls": 1}
                    USAGE.update(counts)
                    if REQUEST_USAGE.get() is not None:
                        REQUEST_USAGE.get().update(counts)
                    choice = body["choices"][0]
                    content = (choice["message"].get("content") or "").strip()
                    if choice.get("finish_reason") == "length" and payload["max_tokens"] < settings.LLM_MAX_TOKENS_CEILING:
                        logger.warning(f"LLM reply cut at max_tokens={payload['max_tokens']}; retrying with a larger budget")
                        payload["max_tokens"] = min(payload["max_tokens"] * 2, settings.LLM_MAX_TOKENS_CEILING)
                        continue
                    return content
                if resp.status_code < 500 and resp.status_code not in RETRYABLE_STATUS:
                    # Auth / bad-request errors do not heal by retrying.
                    raise LLMUnavailableError(f"Dịch vụ ngôn ngữ từ chối yêu cầu (HTTP {resp.status_code}).")
                logger.warning(f"LLM call attempt {attempt}/{retries}: HTTP {resp.status_code}")
            except httpx.HTTPError as exc:
                logger.warning(f"LLM call attempt {attempt}/{retries} failed: {type(exc).__name__}")
            if attempt < retries:
                await asyncio.sleep(delay)
                delay = min(delay * 1.6, 20.0)
    raise LLMUnavailableError("Dịch vụ tạo câu trả lời tạm thời chưa sẵn sàng.")
