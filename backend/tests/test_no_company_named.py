"""B2 + S4 (docs/VERSION_4/PLANNER_ERRORS_2026-11-26.md 8.3, owner 26/11): a question that names no company, where the planner searched the reports of
only some of the selected companies. The line above the answer says the question named no company and which reports were used, the chooser comes right
under that line, and the writer answers for those reports only. Before, the input policy's note ("answer separately for each source, then ask which one")
made a one-company answer talk about the other reports and ask "which company did you mean?" (UI check 26/11, "the e-commerce company").
When the planner searched every company, nothing changes: each is answered, then the user is asked."""
import pytest

from app.modules.query_router.input_policy import PER_SOURCE_PREFIX, Decision, per_source_note
from app.modules.query_router.planner import PlanItem
from app.modules.query_router.target_scope import no_company_line
from tests.test_not_found_flow import CHUNK, META, PLAN_AMD_ONLY, orchestrator
from tests.test_validation import _scope

ANSWER = "AMD net revenue was $25,785 million in 2024 [1].\n" + META % ("answered", "[1]")
QUESTION = {"en": "Which chip maker had revenue above $20 billion in 2024?", "vi": "Hãng chip nào có doanh thu trên 20 tỷ USD năm 2024?"}


def test_the_line_says_no_company_was_named_and_where_to_pick_another():
    assert no_company_line(["AMD | 10-K | FY2024"], vi=False) == \
        "The question names no company; I understood it as about: AMD | 10-K | FY2024. To ask about another company, pick it just below."
    assert no_company_line(["AMD | 10-K | FY2024"], vi=True) == \
        "Câu hỏi không nêu tên công ty; tôi hiểu là về: AMD | 10-K | FY2024. Muốn hỏi công ty khác, hãy chọn ngay bên dưới."


def test_the_input_policy_note_starts_with_the_prefix_code_looks_for():
    assert per_source_note("AMD | 10-K | FY2024; NVIDIA | 10-K | FY2024").startswith(PER_SOURCE_PREFIX)


def writing(monkeypatch, plan):
    orch = orchestrator(monkeypatch, [CHUNK], plan)
    seen = {}

    async def answer(query, chunks, notes=None, max_tokens=1200, fallback=True):
        seen["notes"] = list(notes or [])
        return ANSWER

    monkeypatch.setattr(orch, "_answer", answer)
    return orch, seen


def per_source(lang):
    return Decision(lang=lang, action="answer_per_source_and_ask", notes=[per_source_note("AMD | 10-K | FY2024; NVIDIA | 10-K | FY2024")])


@pytest.mark.parametrize("lang,head", [("en", "The question names no company; I understood it as about:"), ("vi", "Câu hỏi không nêu tên công ty; tôi hiểu là về:")])
async def test_the_planner_choosing_some_companies_answers_for_them_without_asking_back(monkeypatch, lang, head):
    orch, seen = writing(monkeypatch, PLAN_AMD_ONLY)
    r = await orch._answer_one(QUESTION[lang], "nb", _scope(), per_source(lang))
    assert not any(n.startswith(PER_SOURCE_PREFIX) for n in seen["notes"])  # no "answer each source, then ask which one"
    assert any("do not ask which company or period they meant" in n and "Advanced Micro Devices" in n for n in seen["notes"])
    assert r["understood"].startswith(head)
    assert r["actions"]["chooser_first"] is True and [c["checked"] for c in r["actions"]["chooser"]] == [True, False]


async def test_the_planner_choosing_every_company_keeps_answering_each_and_asking(monkeypatch):
    orch, seen = writing(monkeypatch, [PlanItem("revenue", ["amd", "nv"])])
    r = await orch._answer_one(QUESTION["en"], "nb", _scope(), per_source("en"))
    assert any(n.startswith(PER_SOURCE_PREFIX) for n in seen["notes"])
    assert r["understood"].startswith("I understood the question as about:") and "chooser_first" not in r["actions"]


# ---------------------------------------------------------------- S5 (UI check 26/11): sources the user ticked or tagged are not "no company named"
async def test_sources_the_user_ticked_drop_the_answer_each_and_ask_note(monkeypatch):
    """The chooser sends the ticked reports as @ tags. The writer got both "the user tagged these sources: answer for them" and the input policy's
    "named no company ... answer each source, then ask which one" listing every selected report, and the answer asked "which source did you mean?"."""
    orch, seen = writing(monkeypatch, [PlanItem("revenue", ["amd", "nv"])])
    await orch._answer_one(QUESTION["en"], "nb", _scope(), per_source("en"), mentions=["amd", "nv"])
    assert not any(n.startswith(PER_SOURCE_PREFIX) for n in seen["notes"])
    assert any(n.startswith("The user tagged these sources") for n in seen["notes"])
