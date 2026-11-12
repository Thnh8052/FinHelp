"""chat_completion: token budget floor and retry of a reply cut by the budget (deepseek-flash reasoning counts against max_tokens)."""
import httpx

from app.core.config import settings
from app.modules.generation import llm_client


class FakeClient:
    """Answers the queued replies in order and records the max_tokens of every request."""

    def __init__(self, replies, seen):
        self.replies, self.seen = list(replies), seen

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        self.seen.append(json["max_tokens"])
        finish, content = self.replies.pop(0)
        return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": {"content": content}}]})


def patch(monkeypatch, replies):
    seen = []
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "k")
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", lambda timeout: FakeClient(replies, seen))
    return seen


async def test_small_budgets_are_raised_to_the_floor(monkeypatch):
    seen = patch(monkeypatch, [("stop", '{"plan": []}')])
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}], max_tokens=200) == '{"plan": []}'
    assert seen == [settings.LLM_MIN_MAX_TOKENS]


async def test_reply_cut_by_the_budget_is_retried_with_a_larger_one(monkeypatch):
    seen = patch(monkeypatch, [("length", ""), ("stop", '{"plan": [{"query": "q", "doc_ids": ["d1"]}]}')])
    out = await llm_client.chat_completion([{"role": "user", "content": "q"}], max_tokens=1500)
    assert out.startswith('{"plan": [{')
    assert seen == [settings.LLM_MIN_MAX_TOKENS, 2 * settings.LLM_MIN_MAX_TOKENS]


async def test_retry_stops_at_the_ceiling(monkeypatch):
    seen = patch(monkeypatch, [("length", "")] * 4)
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}]) == ""
    assert seen[-1] == settings.LLM_MAX_TOKENS_CEILING and len(seen) == 3


def test_reasoning_tokens_nested_in_usage_are_counted_for_the_request():
    counts = llm_client.Counter()
    token = llm_client.REQUEST_USAGE.set(counts)
    try:
        llm_client._record_usage({"prompt_tokens": 10, "completion_tokens": 50, "completion_tokens_details": {"reasoning_tokens": 40}})
        llm_client._record_usage({"prompt_tokens": 5, "completion_tokens": 8})  # a reply without the detail
    finally:
        llm_client.REQUEST_USAGE.reset(token)
    assert counts["reasoning_tokens"] == 40 and counts["completion_tokens"] == 58 and counts["calls"] == 2


def test_search_parts_add_up_per_name_and_do_nothing_outside_a_request():
    from app.modules.retrieval.hybrid_search import SEARCH_PARTS, part_done
    import time
    part_done("embed", time.perf_counter())  # no collector set: no error
    parts = {}
    token = SEARCH_PARTS.set(parts)
    try:
        part_done("net", time.perf_counter() - 0.5)
        part_done("net", time.perf_counter() - 0.25)
    finally:
        SEARCH_PARTS.reset(token)
    assert 0.7 <= parts["net"] <= 0.9
