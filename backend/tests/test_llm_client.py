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


# ---------------------------------------------------------------- the default budget (found 13/11: 4 of 5 analysis answers hit the 8,000 budget, the whole reply was thrown away and asked again)
class SizedClient(FakeClient):
    """A model that needs `needs` tokens of budget for this reply: with less it is cut during its reasoning, with enough it answers."""

    def __init__(self, needs, seen):
        super().__init__([], seen)
        self.needs = needs

    async def post(self, url, headers=None, json=None):
        self.seen.append(json["max_tokens"])
        cut = json["max_tokens"] < self.needs
        return httpx.Response(200, json={"choices": [{"finish_reason": "length" if cut else "stop", "message": {"content": "" if cut else "the answer"}}]})


def sized(monkeypatch, needs):
    seen = []
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "k")
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", lambda timeout: SizedClient(needs, seen))
    return seen


async def test_an_answer_that_reasons_for_eleven_thousand_tokens_is_written_in_one_call(monkeypatch):
    """The longest complete reply measured (reasoning and answer) was about 11,000 tokens; a cut one wastes its whole budget and is paid for."""
    seen = sized(monkeypatch, needs=11_500)
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}], max_tokens=1200) == "the answer"
    assert len(seen) == 1


async def test_the_budget_has_a_ceiling_that_bounds_a_runaway_reply(monkeypatch):
    """A larger budget is only a ceiling (the API bills the tokens generated), but a reply that never ends must still stop: at most three requests, none above the ceiling."""
    assert settings.LLM_MIN_MAX_TOKENS <= settings.LLM_MAX_TOKENS_CEILING <= 64_000
    seen = sized(monkeypatch, needs=10 ** 9)
    assert await llm_client.chat_completion([{"role": "user", "content": "q"}]) == ""
    assert len(seen) <= 3 and max(seen) <= settings.LLM_MAX_TOKENS_CEILING
