"""Three fixes from the live behavior check of 18/11/2026 (docs/VERSION_4/BEHAVIOR_CHECK_2026-11-18.md, traces in experiments/outputs/behavior_live):
P1 a message too short to show its language after a turn that did not show one either ("abcd" then "?") follows the interface (V21 got English on a
Vietnamese interface); P3 a chat label of the guard on a message with no tie to the reports stops the search at once (E18 "Hello there!" waited 6 s
for a search it did not need); P4 the guard is called once when the server starts, so the first user message is not let through unchecked (E01)."""
import asyncio
import time

import pytest

from app.core.config import settings
from app.modules.query_router import guard
from app.modules.query_router.input_policy import MSG, decide
from tests.test_input_policy import NIKE23, NIKE_DOCS, _orchestrator
from tests.test_guard import fake_guard


# ------------------------------------------------------------------ P1
@pytest.mark.parametrize("ui", ["vi", "en"])
@pytest.mark.parametrize("earlier", ["abcd", "?", "ok"])
def test_after_a_turn_that_showed_no_language_a_short_message_follows_the_interface(ui, earlier):
    d = decide("?", [NIKE23], 1, [{"role": "user", "content": earlier}, {"role": "assistant", "content": "..."}], ui_lang=ui)
    assert d.lang == ui and d.message == MSG["reject_input"][ui]


def test_a_previous_question_that_showed_its_language_still_wins():
    vi = [{"role": "user", "content": "Doanh thu của Nike năm 2023 là bao nhiêu?"}, {"role": "assistant", "content": "..."}]
    assert decide("ok", [NIKE23], 1, vi, ui_lang="en").lang == "vi"


# ------------------------------------------------------------------ P3
def _slow_search(orch, seconds):
    """Every search route of the fake search waits `seconds` first (which one runs depends on the scope and the plan)."""
    for name in ("retrieve_research", "retrieve_multi_doc", "retrieve_by_content", "retrieve_planned"):
        real = getattr(orch.hybrid_search, name, None)
        if real is None:
            continue

        async def slow(*a, _real=real, **k):
            await asyncio.sleep(seconds)
            return await _real(*a, **k)

        setattr(orch.hybrid_search, name, slow)


async def test_a_chat_label_on_a_message_with_no_tie_to_the_reports_stops_the_search_at_once(monkeypatch):
    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    _slow_search(orch, 3.0)
    fake_guard(monkeypatch, "small_talk", delay=0.05)
    t0 = time.perf_counter()
    r = await orch.execute_query("Hello there, nice to meet you!", "nb", document_ids=["d1", "d2"])
    assert time.perf_counter() - t0 < 1.5  # it waited for the 3 s search before
    assert r["answer"] == MSG["small_talk"]["en"] and r["charged"] is False and r["trace"]["guard"]["where"] == "search_cancelled"


async def test_a_chat_label_on_a_question_about_a_report_still_lets_it_be_answered(monkeypatch):
    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    _slow_search(orch, 0.2)
    fake_guard(monkeypatch, "small_talk", delay=0.05)
    r = await orch.execute_query("Thanks! And what was Nike's revenue?", "nb", document_ids=["d1", "d2"])
    assert r["answer"].startswith("ANSWER to") and r["trace"]["guard"]["outcome"] == "kept"


# ------------------------------------------------------------------ P4
async def test_the_guard_is_called_once_at_start_when_it_is_on(monkeypatch):
    from app.modules.retrieval import warmup

    calls = []

    async def classify(message, reports):
        calls.append(message)
        return guard.Verdict("ok", 0.1)

    monkeypatch.setattr(guard, "classify", classify)
    monkeypatch.setattr(settings, "GUARD_ENABLED", True)
    await warmup.warm_guard()
    assert len(calls) == 1
    monkeypatch.setattr(settings, "GUARD_ENABLED", False)
    await warmup.warm_guard()
    assert len(calls) == 1  # off: no call


async def test_a_failing_warm_up_never_stops_the_server(monkeypatch):
    from app.modules.retrieval import warmup

    async def broken(message, reports):
        raise RuntimeError("no key")

    monkeypatch.setattr(guard, "classify", broken)
    monkeypatch.setattr(settings, "GUARD_ENABLED", True)
    await warmup.warm_guard()  # no exception
