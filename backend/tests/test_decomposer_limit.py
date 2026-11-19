"""The owner 19/11: a single-report question searches with at most 3 sub-queries; the prompt may ask for 2 to 4 (it asked for 2 to 5, and code kept
the first 3, settings.SUBQUERY_COUNT)."""
import json

from app.core.config import settings
from app.modules.query_router import decomposer


def test_the_prompt_asks_for_two_to_four_queries_in_both_languages():
    for prompt in (decomposer.PROMPT, decomposer.PROMPT_VI):
        assert "Write 2 to 4 short search queries" in prompt and "2 to 5" not in prompt


async def test_at_most_three_sub_queries_are_kept(monkeypatch):
    decomposer._cache.clear()

    async def five(messages, **kw):
        return json.dumps({"queries": ["a", "b", "c", "d", "e"]})

    monkeypatch.setattr(decomposer, "chat_completion", five)
    assert settings.SUBQUERY_COUNT == 3
    assert (await decomposer.decompose_query("What was the cash conversion cycle?"))[1] == ["a", "b", "c"]
