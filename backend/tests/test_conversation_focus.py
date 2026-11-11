"""The conversation's focus: short follow-ups are completed from it by code, and only a searched question moves it."""
import pytest

from app.modules.chat import chat as chat_api
from app.modules.query_router.focus import Focus, build_focus, fill_from_focus, focus_view, metric_in, short_name
from app.modules.query_router.input_policy import SourceInfo, decide

INTC22 = SourceInfo("Intel Corporation", "10-K", 2022, None, "Intel | 10-K | FY2022", years_covered=[2022, 2021])
INTC21 = SourceInfo("Intel Corporation", "10-K", 2021, None, "Intel | 10-K | FY2021", years_covered=[2021, 2020])
NVDA22 = SourceInfo("NVIDIA Corporation", "10-K", 2022, None, "NVIDIA | 10-K | FY2022", years_covered=[2022, 2021])
SOURCES = [INTC22, INTC21, NVDA22]
INTEL_REVENUE = Focus(["Intel Corporation"], [2022], "revenue")
HIST = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]


@pytest.mark.parametrize("text, key", [
    ("What was the net income?", "net_income"), ("lợi nhuận sau thuế", "net_income"), ("gross profit margin", "gross_margin"), ("gross profit", "gross_profit"),
    ("cost of sales", "cost_of_revenue"), ("net sales", "revenue"), ("doanh thu", "revenue"), ("net interest income", "net_interest_income"), ("the risk factors", None),
])
def test_metrics_are_recognised_most_specific_first(text, key):
    assert metric_in(text) == key


def test_short_names():
    assert [short_name(c) for c in ("PepsiCo, Inc.", "The Coca-Cola Company", "JPMorgan Chase & Co.", "Bank of America Corporation")] == ["PepsiCo", "Coca-Cola", "JPMorgan Chase", "Bank of America"]


@pytest.mark.parametrize("question, focus, lang, expected", [
    ("lợi nhuận ròng?", INTEL_REVENUE, "vi", "Lợi nhuận ròng của Intel năm 2022 là bao nhiêu?"),
    ("còn lợi nhuận ròng?", INTEL_REVENUE, "vi", "Lợi nhuận ròng của Intel năm 2022 là bao nhiêu?"),
    ("and the net income?", INTEL_REVENUE, "en", "What was the net income of Intel in 2022?"),
    ("còn năm 2021?", INTEL_REVENUE, "vi", "Doanh thu của Intel năm 2021 là bao nhiêu?"),
    ("còn NVIDIA thì sao?", INTEL_REVENUE, "vi", "Doanh thu của NVIDIA năm 2022 là bao nhiêu?"),
    ("so với năm trước?", INTEL_REVENUE, "vi", "So sánh doanh thu của Intel năm 2022 với năm 2021"),
    ("compared with the year before?", INTEL_REVENUE, "en", "Compare the revenue of Intel in 2022 with 2021"),
    ("and the year before?", INTEL_REVENUE, "en", "What was the revenue of Intel in 2021?"),
    ("còn lợi nhuận ròng?", Focus(["Intel Corporation", "NVIDIA Corporation"], [2022], "revenue"), "vi", "So sánh lợi nhuận ròng của Intel và NVIDIA năm 2022"),
])
def test_a_follow_up_is_completed_from_the_focus(question, focus, lang, expected):
    assert fill_from_focus(question, focus, SOURCES, lang) == expected


@pytest.mark.parametrize("question, focus", [
    ("còn quý 3?", INTEL_REVENUE),  # quarters are left to the model
    ("còn năm 2021?", Focus(["Intel Corporation"], [2022], None)),  # no item known
    ("còn lợi nhuận ròng?", Focus(["Intel Corporation"], [2022, 2021], "revenue")),  # two years: which one?
    ("còn lợi nhuận ròng?", None),
])
def test_what_the_slots_cannot_settle_is_left_to_the_model(question, focus):
    assert fill_from_focus(question, focus, SOURCES, "vi") is None


@pytest.mark.parametrize("question", [
    "còn lợi nhuận?", "còn rủi ro pháp lý thì sao?", "and the legal risks?", "and the segment revenue?", "How is revenue recognized?", "Why did net income fall?",
    "Tại sao doanh thu giảm?", "Which segment had the highest revenue?", "Did revenue grow?", "and who audited it?", "What drove gross profit?", "and?",
])
def test_a_question_with_content_of_its_own_is_never_replaced_by_the_topic(question):
    assert fill_from_focus(question, INTEL_REVENUE, SOURCES, "vi") is None


def test_compared_with_opens_a_follow_up_only_when_there_is_a_topic():
    question = "compared with peers, how did margins do?"
    assert decide(question, SOURCES, 3, []).action not in ("rewrite_followup", "ask_clarify")
    assert decide("compared with the year before?", SOURCES, 3, HIST, INTEL_REVENUE).action == "rewrite_followup"


@pytest.mark.parametrize("question", ["lợi nhuận ròng?", "còn lợi nhuận ròng?", "còn năm 2021?", "còn NVIDIA thì sao?", "so với năm trước?", "compared with the year before?", "năm trước?"])
def test_short_turns_lean_on_the_focus(question):
    assert decide(question, SOURCES, 3, HIST, INTEL_REVENUE).action == "rewrite_followup"


@pytest.mark.parametrize("question", [
    "And what was Intel's net income in FY2021?",  # complete
    "What did Intel report as risks in its FY2022 filing?",
    "What was the company's revenue in its latest filing?",  # long enough and tied to the document
])
def test_complete_questions_stay_new_questions(question):
    assert decide(question, SOURCES, 3, HIST, INTEL_REVENUE).action != "rewrite_followup"


def test_without_a_focus_nothing_changes():
    assert decide("lợi nhuận ròng?", SOURCES, 3, HIST).action != "rewrite_followup"
    assert decide("còn năm 2021?", SOURCES, 3, HIST).action != "rewrite_followup"


def test_a_correction_and_an_outside_company_go_to_the_model():
    assert "correction" in decide("No, I meant NVIDIA", SOURCES, 3, HIST, INTEL_REVENUE).flags
    assert "outside_name" in decide("And Tesla?", SOURCES, 3, HIST, INTEL_REVENUE).flags


def test_the_focus_never_reaches_past_the_selected_documents():
    state = {"document_ids": ["d1"], "fiscal_years": [2022], "metric": "revenue"}
    assert focus_view(state, ["d1", "d3"], [INTC22, NVDA22]).companies == ["Intel Corporation"]
    assert focus_view(state, ["d3"], [NVDA22]) is None
    assert focus_view({}, ["d3"], [NVDA22]) is None


def test_building_the_state():
    years = {"d1": 2022, "d2": 2021}
    assert build_focus("Intel revenue in 2021", ["d1"], years, None) == {"document_ids": ["d1"], "fiscal_years": [2021], "metric": "revenue"}
    assert build_focus("Intel revenue", ["d1", "d2"], years, None)["fiscal_years"] == [2022, 2021]  # no year written: the documents' own
    assert build_focus("Risks of Intel in 2021", ["d1"], years, {"metric": "revenue"})["metric"] == "revenue"  # what is not said is kept
    assert build_focus("anything", [], years, None) is None


# ---------------------------------------------------------------- through the orchestrator (no model: see test_input_policy._orchestrator)
from tests.test_input_policy import NIKE_DOCS, _orchestrator  # noqa: E402

STATE = {"document_ids": ["d2"], "fiscal_years": [2023], "metric": "revenue"}


async def test_a_follow_up_is_answered_without_the_model_and_moves_the_focus(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod

    async def never(q, history):
        raise AssertionError("the model must not be called")

    orch, seen = _orchestrator(NIKE_DOCS, monkeypatch)
    monkeypatch.setattr(orch_mod, "rewrite_followup", never)
    r = await orch.execute_query("còn lợi nhuận ròng?", "nb", document_ids=["d1", "d2"], history=[{"role": "assistant", "content": "a"}], focus_state=STATE)
    assert seen["answers"][0][0] == "Lợi nhuận ròng của NIKE năm 2023 là bao nhiêu?" and r["answer"].startswith("Tôi hiểu câu hỏi là: “Lợi nhuận ròng của NIKE năm 2023")
    assert r["trace"]["followup"]["method"] == "focus"
    assert r["focus"]["metric"] == "net_income" and r["focus"]["fiscal_years"] == [2023]


async def test_a_tagged_file_names_the_company_and_the_topic_only_the_item_and_year(monkeypatch):
    from tests.test_input_policy import _doc

    docs = [_doc("d1", "intc.pdf", company_name="Intel Corporation", fiscal_year=2023, report_type="10-K"), _doc("d2", "nvda.pdf", company_name="NVIDIA Corporation", fiscal_year=2023, report_type="10-K")]
    orch, seen = _orchestrator(docs, monkeypatch)
    state = {"document_ids": ["d1"], "fiscal_years": [2023], "metric": "revenue"}
    await orch.execute_query("lợi nhuận ròng?", "nb", document_ids=["d1", "d2"], history=[{"role": "assistant", "content": "a"}], mentions=["d2"], focus_state=state)
    assert seen["answers"][0][0] == "Lợi nhuận ròng của NVIDIA năm 2023 là bao nhiêu?"


async def test_the_model_receives_the_topic_when_slots_are_not_enough(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod

    calls = []

    async def rewrite(q, history):
        calls.append(history)
        return "What was Nike's net income in FY2023?"

    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    monkeypatch.setattr(orch_mod, "rewrite_followup", rewrite)
    r = await orch.execute_query("No, I meant the net income", "nb", document_ids=["d1", "d2"], history=[{"role": "assistant", "content": "a"}], focus_state=STATE)
    assert calls[0][-1]["role"] == "current topic" and "revenue" in calls[0][-1]["content"]
    assert r["trace"]["followup"]["method"] == "llm"


async def test_a_refused_question_does_not_move_the_focus(monkeypatch):
    orch, _ = _orchestrator(NIKE_DOCS, monkeypatch)
    r = await orch.execute_query("What is the weather in Hanoi today?", "nb", document_ids=["d1", "d2"], focus_state=STATE)
    assert "focus" not in r


async def _ask(monkeypatch, nb, result, query="q"):
    """The chat endpoint with everything around it replaced: what was written, in order."""
    import types

    order = []

    class Chats:
        def __init__(self, db):
            pass

        async def get_messages(self, notebook_id, limit=500):
            return []

        async def set_title(self, notebook_id, title):
            order.append(("title", title))

        async def append_message(self, message):
            order.append(message.role)

        async def set_focus(self, notebook_id, focus):
            order.append(("focus", focus))

    async def answered(self, **kw):
        assert kw["focus_state"] == nb.focus_state
        return result

    async def none(*a, **k):
        return None

    monkeypatch.setattr(chat_api, "ChatRepository", Chats)
    monkeypatch.setattr(chat_api, "require_notebook", lambda *a, **k: _value(nb))
    monkeypatch.setattr(chat_api, "can_chat", lambda *a: True)
    monkeypatch.setattr(chat_api, "ensure_documents_ready", none)
    monkeypatch.setattr(chat_api, "UserRepository", lambda db: types.SimpleNamespace(reserve_quota=_true, consume_quota=none))
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "__init__", lambda self, db, qdrant: None)
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "resolve_scope", none)
    monkeypatch.setattr(chat_api.RAGWorkflowOrchestrator, "execute_query", answered)
    response = await chat_api.handle_user_query(None, chat_api.QueryRequest(notebook_id="nb", query=query, document_ids=["d1"]), "u", None, None)
    return order, response


async def test_the_focus_is_saved_only_after_the_answer_is_stored(monkeypatch):
    from app.modules.notebooks.notebook import NotebookRecord

    nb = NotebookRecord(notebook_id="nb", owner_id="u", title="Intel", focus_state={"metric": "x"}, message_count=1)
    order, _ = await _ask(monkeypatch, nb, {"answer": "ok", "intent": "retrieval_rag", "citations": [], "focus": {"metric": "revenue"}, "trace": {}})
    assert order == ["user", "assistant", ("focus", {"metric": "revenue"})]


async def test_a_greeting_does_not_name_the_chat_but_the_first_searched_question_does(monkeypatch):
    from app.modules.notebooks.notebook import NotebookRecord

    order, response = await _ask(monkeypatch, NotebookRecord(notebook_id="nb", owner_id="u"),
                                 {"answer": "Xin chào!", "intent": "static_reply", "citations": [], "charged": False, "trace": {}}, "bạn ổn không ?")
    assert not any(isinstance(step, tuple) and step[0] == "title" for step in order) and response.title == "Hội thoại mới"
    order, response = await _ask(monkeypatch, NotebookRecord(notebook_id="nb", owner_id="u", message_count=2),  # the greeting came first
                                 {"answer": "6,475", "intent": "retrieval_rag", "citations": [], "charged": True, "trace": {}}, "Doanh thu AMD năm 2018?")
    assert ("title", "Doanh thu AMD năm 2018?") in order and response.title == "Doanh thu AMD năm 2018?"
    order, _ = await _ask(monkeypatch, NotebookRecord(notebook_id="nb", owner_id="u", title="Báo cáo AMD"),  # a title the user chose is kept
                          {"answer": "6,475", "intent": "retrieval_rag", "citations": [], "charged": True, "trace": {}})
    assert not any(isinstance(step, tuple) and step[0] == "title" for step in order)


async def test_a_question_that_is_too_long_is_refused_before_anything_is_stored(monkeypatch):
    from fastapi import HTTPException

    from app.modules.notebooks.notebook import NotebookRecord

    with pytest.raises(HTTPException) as refused:
        await _ask(monkeypatch, NotebookRecord(notebook_id="nb", owner_id="u"), {}, "x" * 4001)
    assert refused.value.status_code == 422 and refused.value.detail == {"code": "question_too_long", "params": {"max": 4000}}


async def _value(v):
    return v


async def _true(*a, **k):
    return True
