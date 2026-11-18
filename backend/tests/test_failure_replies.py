"""The line code adds under an answer names the problem that happened, and the button fits it (behavior check 17/11/2026,
experiments/scripts/behavior/behavior_matrix.py): a figure that could not be verified is not "not found", a slow system is not "check your sources",
a model that could not be reached is said sorry for and asked again unchanged, a reply cut at the limit is edited, and neither costs a question."""
import pytest

from app.modules.chat import orchestrator as orch_mod
from app.modules.chat.orchestrator import RetrievalResult
from app.modules.generation.llm_client import LLMTruncatedError, LLMUnavailableError
from app.modules.generation.replies import CHECK_SOURCES, DEGRADED_NOTE, RETRY_APOLOGY, RETRY_FIGURES_APOLOGY
from app.modules.query_router.input_policy import Decision
from app.modules.query_router.planner import PlanItem
from tests.test_not_found_flow import CHUNK, META, orchestrator
from tests.test_validation import AMD, NV, _scope

Q = {"en": "Which company had the higher revenue in 2024?", "vi": "Công ty nào có doanh thu cao hơn năm 2024?"}
PLAN = [PlanItem("revenue", ["amd", "nv"])]
UNVERIFIED = "AMD net revenue was $99,999 million in 2024 [1].\n" + META % ("answered", "[1]")
NOT_FOUND = "The excerpts do not show NVIDIA's revenue.\n" + META % ("not_found", "[]")


async def run(monkeypatch, lang="en", reply=None, raises=None, retry=False, degraded=()):
    orch = orchestrator(monkeypatch, [CHUNK], PLAN)

    async def retrieve(query, notebook_id, scope, forced=None, **kw):
        return RetrievalResult(scope, {"amd": AMD.label, "nv": NV.label}, list(PLAN), ["revenue"], [dict(CHUNK)], "planner", {}, degraded=list(degraded))

    async def gen(*a, **k):
        if raises is not None:
            raise raises
        return reply

    monkeypatch.setattr(orch, "retrieve", retrieve)
    monkeypatch.setattr(orch_mod, "generate_answer", gen)
    return await orch._answer_one(Q[lang], "nb", _scope(), Decision(lang=lang), retry=retry)


@pytest.mark.parametrize("lang", ["en", "vi"])
async def test_a_click_that_leaves_only_unverified_figures_says_sorry_for_the_figures_not_for_missing_information(monkeypatch, lang):
    r = await run(monkeypatch, lang, UNVERIFIED, retry=True)
    assert RETRY_FIGURES_APOLOGY[lang] in r["answer"] and RETRY_APOLOGY[lang] not in r["answer"]


async def test_a_click_that_still_finds_nothing_keeps_the_not_found_apology(monkeypatch):
    r = await run(monkeypatch, "en", NOT_FOUND, retry=True)
    assert RETRY_APOLOGY["en"] in r["answer"] and RETRY_FIGURES_APOLOGY["en"] not in r["answer"]


@pytest.mark.parametrize("lang", ["en", "vi"])
async def test_a_slow_search_that_found_nothing_blames_the_slow_system_not_the_sources(monkeypatch, lang):
    r = await run(monkeypatch, lang, NOT_FOUND, degraded=["rerank_skipped"])
    assert DEGRADED_NOTE[lang] in r["answer"] and CHECK_SOURCES[lang] not in r["answer"]
    r = await run(monkeypatch, lang, NOT_FOUND, degraded=["rerank_skipped"], retry=True)  # a click on a slow system: still the slow system, not "not found"
    assert DEGRADED_NOTE[lang] in r["answer"] and RETRY_APOLOGY[lang] not in r["answer"] and CHECK_SOURCES[lang] not in r["answer"]


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_the_slow_system_note_names_no_button(lang):
    # the button's label follows the interface language, the note the question's: naming it could name a button the screen does not show
    for label in ("Tìm kỹ hơn", "Search deeper", "Tìm lại", "Search again"):
        assert label not in DEGRADED_NOTE[lang]


@pytest.mark.parametrize("lang,sorry", [("en", "Sorry"), ("vi", "Xin lỗi")])
async def test_a_model_that_cannot_be_reached_says_sorry_offers_try_again_and_costs_nothing(monkeypatch, lang, sorry):
    r = await run(monkeypatch, lang, raises=LLMUnavailableError("LLM_UNAVAILABLE"))
    assert r["answer"].startswith(sorry)
    assert r["actions"]["try_again"] is True and r["actions"]["search_more"] is None
    assert r["charged"] is False


async def test_a_reply_cut_at_the_limit_offers_editing_the_question_and_costs_nothing(monkeypatch):
    r = await run(monkeypatch, "en", raises=LLMTruncatedError("LLM_UNAVAILABLE"))
    assert r["actions"]["edit_question"] is True and r["actions"]["search_more"] is None and r["actions"]["try_again"] is False
    assert r["charged"] is False


async def test_a_failed_writer_on_a_slow_system_still_offers_try_again(monkeypatch):
    r = await run(monkeypatch, "en", raises=LLMUnavailableError("LLM_UNAVAILABLE"), degraded=["rerank_skipped"])
    assert r["actions"]["try_again"] is True and r["charged"] is False


ADVICE = "AMD net revenue was $25,785 million in 2024 [1]. You should buy AMD shares now.\n" + META % ("answered", "[1]")


@pytest.mark.parametrize("lang", ["en", "vi"])
async def test_an_answer_blocked_for_advice_offers_no_search_and_costs_nothing(monkeypatch, lang):
    # owner's check 18/11/2026: the fixed "could not produce a suitable answer" reply had "Search deeper" and used a question
    from app.core.config import settings
    from app.modules.generation.answer_check import policy

    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", True)
    r = await run(monkeypatch, lang, ADVICE)
    assert r["answer"].startswith(policy.BLOCKED[lang])
    assert r["actions"]["search_more"] is None and r["actions"]["chooser"] == [] and r["actions"]["try_again"] is False
    assert r["actions"]["edit_question"] is True  # the reply asks to rephrase
    assert r["charged"] is False


async def test_a_blocked_answer_to_a_click_also_costs_nothing(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", True)
    r = await run(monkeypatch, "en", ADVICE, retry=True)
    assert r["actions"]["search_more"] is None and r["actions"]["edit_question"] is True and r["charged"] is False
