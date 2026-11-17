"""Multi-step questions (docs/VERSION_4/ROADMAP_V4.md 3.3, measured 17/11 in experiments/scripts/agentic): the whole message goes to the planner
(MULTIDOC_WHOLE_MESSAGE) and a question whose second part depends on the first is answered in at most two steps (MULTIHOP_ENABLED, configuration C2).
Both flags are off by default: then everything behaves as before. No network, no GPU, no database."""
import asyncio
import json

import pytest

from app.core.config import settings
from app.modules.chat import retrieval_step
from app.modules.query_router import bridge, planner
from app.modules.query_router import input_policy as policy
from app.modules.query_router.input_policy import SourceInfo, decide
from app.modules.query_router.planner import CatalogEntry, PlanItem

KO22 = SourceInfo("The Coca-Cola Company", "10-K", 2022, None, "The Coca-Cola Company | 10-K | FY2022")
PEP22 = SourceInfo("PepsiCo, Inc", "10-K", 2022, None, "PepsiCo, Inc | 10-K | FY2022")
CATALOG = [CatalogEntry("d1", "The Coca-Cola Company", "10-K", "FY2022", "ko.pdf"), CatalogEntry("d2", "PepsiCo, Inc", "10-K", "FY2022", "pep.pdf")]
SEQUENTIAL = "Which of Coca-Cola and PepsiCo had the highest revenue in 2022, and what was its net income?"
INDEPENDENT = "What was Coca-Cola's revenue in 2022? What was PepsiCo's net income in 2022?"


@pytest.fixture
def flags(monkeypatch):
    def set_flags(whole=False, multihop=False):
        monkeypatch.setattr(settings, "MULTIDOC_WHOLE_MESSAGE", whole)
        monkeypatch.setattr(settings, "MULTIHOP_ENABLED", multihop)
    return set_flags


# ---------------------------------------------------------------- input rules
def test_flags_off_keep_todays_split_and_refusal(flags):
    flags()
    assert decide(INDEPENDENT, [KO22, PEP22], 2).action == "split_questions"
    assert decide(SEQUENTIAL, [KO22, PEP22], 2).action == "not_supported_yet"


def test_whole_message_goes_to_the_planner_over_several_sources_only(flags):
    flags(whole=True)
    assert decide(INDEPENDENT, [KO22, PEP22], 2).action == "proceed"
    assert decide("What was Coca-Cola's revenue in 2022? What was its net income in 2022?".replace("its", "Coca-Cola's"), [KO22], 1).action == "split_questions"


def test_sequential_question_is_no_longer_refused_over_several_sources(flags):
    flags(multihop=True)
    assert decide(SEQUENTIAL, [KO22, PEP22], 2).action == "proceed"
    assert decide(SEQUENTIAL, [KO22], 1).action == "not_supported_yet"  # one source: the single-filing path has no planner, the refusal stays


def test_names_an_item_tells_a_lookup_from_a_bare_comparison():
    assert policy.names_an_item("what was that company's worldwide headcount?")
    assert policy.names_an_item("lợi nhuận ròng năm 2021 của công ty đó là bao nhiêu?")
    assert not policy.names_an_item("Which was highest?")
    assert not policy.names_an_item("which was higher?")


# ---------------------------------------------------------------- planner prompt
def test_multihop_prompt_adds_one_rule_and_the_then_field_only():
    assert '"then"' not in planner.PROMPT  # the measured prompt is unchanged
    extra = planner.PROMPT_MULTIHOP
    assert extra.count("- Dependent part:") == 1
    assert extra.index("- Several periods:") < extra.index("- Dependent part:") < extra.index("- Report type:")
    assert '{{"plan": [{{"query": "...", "doc_ids": ["..."]}}], "then": "..."}}' in extra
    assert extra.format(catalog="x", q="y")  # still a valid template


async def test_plan_with_then_reads_the_dependent_part(monkeypatch):
    planner._cache.clear()
    seen = {}

    async def fake(messages, **kwargs):
        seen["prompt"] = messages[1]["content"]
        return json.dumps({"plan": [{"query": "income statement total revenues", "doc_ids": ["doc01", "doc02"]}], "then": "what was its net income?"})

    monkeypatch.setattr(planner, "chat_completion", fake)
    plan, then = await planner.plan_with_then(SEQUENTIAL, CATALOG)
    assert [(p.query, p.document_ids) for p in plan] == [("income statement total revenues", ["d1", "d2"])]
    assert then == "what was its net income?" and "- Dependent part:" in seen["prompt"]


def test_an_empty_plan_with_an_empty_then_is_still_a_valid_empty_plan():
    assert planner.chose_nothing('{"plan": []}') and planner.chose_nothing('{"plan": [], "then": ""}')
    assert not planner.chose_nothing('{"plan": [], "then": "x"}')


# ---------------------------------------------------------------- the intermediate call
CHUNKS = [{"chunk_id": "c1", "document_id": "d1", "document_label": "The Coca-Cola Company | 10-K | FY2022", "page": 60, "content": "Net operating revenues 43,004"},
          {"chunk_id": "c2", "document_id": "d2", "document_label": "PepsiCo, Inc | 10-K | FY2022", "page": 70, "content": "Net revenue 86,392"}]


async def test_bridge_maps_short_ids_and_keeps_a_result_its_excerpts_back(monkeypatch):
    async def fake(messages, **kwargs):
        return json.dumps({"found": "PepsiCo, Inc.", "citations": [2], "question": "What was PepsiCo's net income in 2022?",
                           "plan": [{"query": "income statement net income", "doc_ids": ["doc02", "ghost"]}]})

    monkeypatch.setattr(bridge, "chat_completion", fake)
    out = await bridge.continue_plan(SEQUENTIAL, "what was its net income?", CHUNKS, CATALOG)
    assert out.found == "PepsiCo, Inc." and out.citations == [2] and out.question.startswith("What was PepsiCo")
    assert [(p.query, p.document_ids) for p in out.plan] == [("income statement net income", ["d2"])]


async def test_bridge_result_not_shown_by_its_cited_excerpts_is_dropped(monkeypatch):
    async def fake(messages, **kwargs):  # names PepsiCo but cites only a Coca-Cola excerpt
        return json.dumps({"found": "PepsiCo", "citations": [1], "question": "q", "plan": [{"query": "net income", "doc_ids": ["doc02"]}]})

    monkeypatch.setattr(bridge, "chat_completion", fake)
    assert await bridge.continue_plan(SEQUENTIAL, "what was its net income?", CHUNKS, CATALOG) is None


@pytest.mark.parametrize("reply", ["not json", json.dumps({"found": "", "citations": [], "question": "", "plan": []})])
async def test_bridge_without_a_result_returns_none(monkeypatch, reply):
    async def fake(messages, **kwargs):
        return reply

    monkeypatch.setattr(bridge, "chat_completion", fake)
    assert await bridge.continue_plan(SEQUENTIAL, "what was its net income?", CHUNKS, CATALOG) is None


async def test_bridge_past_its_deadline_returns_none(monkeypatch):
    async def slow(messages, **kwargs):
        await asyncio.sleep(5)
        return "{}"

    monkeypatch.setattr(bridge, "chat_completion", slow)
    monkeypatch.setattr(settings, "MULTIHOP_BRIDGE_TIMEOUT_SECONDS", 0.05)
    assert await bridge.continue_plan(SEQUENTIAL, "what was its net income?", CHUNKS, CATALOG) is None


async def test_bridge_when_the_model_is_down_returns_none(monkeypatch):
    from app.modules.generation.llm_client import LLMUnavailableError

    async def down(messages, **kwargs):
        raise LLMUnavailableError("LLM_UNAVAILABLE")

    monkeypatch.setattr(bridge, "chat_completion", down)
    assert await bridge.continue_plan(SEQUENTIAL, "what was its net income?", CHUNKS, CATALOG) is None


def test_writer_note_names_the_result_and_its_excerpts():
    note = bridge.writer_note({"found": "PepsiCo, Inc.", "citations": [2, 5]})
    assert "PepsiCo, Inc." in note and "[2], [5]" in note and "Check it against those excerpts" in note
    assert bridge.writer_note({}) is None


# ---------------------------------------------------------------- the search with two steps
def _docs():
    from app.modules.documents.document import DocumentMetadata, DocumentRecord

    return [DocumentRecord(document_id=i, notebook_id="nb", file_name=f"{i}.pdf", file_size_bytes=1, file_path="p", status="ready",
                           metadata=DocumentMetadata(company_name=c, fiscal_year=2022, report_type="10-K")) for i, c in (("d1", "The Coca-Cola Company"), ("d2", "PepsiCo, Inc"))]


class FakeSearch:
    def __init__(self):
        self.planned, self.multi = [], []

    async def retrieve_planned(self, question, plan, notebook_id, scope_ids, **kwargs):
        self.planned.append((question, [(p.query, p.document_ids) for p in plan]))
        if len(self.planned) == 1:
            return [dict(c) for c in CHUNKS]
        return [dict(CHUNKS[1]), {"chunk_id": "c3", "document_id": "d2", "page": 71, "content": "Net income 8,910"}]

    async def retrieve_multi_doc(self, plan, notebook_id, scope_ids, limit=None):
        self.multi.append([(p.query, p.document_ids) for p in plan])
        return [{"chunk_id": f"m{len(self.multi)}", "document_id": plan[0].document_ids[0], "page": 1, "content": "x"}]

    async def retrieve_by_content(self, query, notebook_id, ids, year_ids):
        self.multi.append([(query, "r4")])
        return []


async def test_two_steps_search_the_dependent_part_and_append_new_chunks(flags, monkeypatch):
    flags(multihop=True)

    async def plan(q, catalog):
        return [PlanItem("total revenues", ["d1", "d2"])], "what was its net income?"

    async def cont(question, then, chunks, catalog):
        assert [c["chunk_id"] for c in chunks] == ["c1", "c2"]
        return bridge.Bridge("PepsiCo, Inc.", [2], "What was PepsiCo's net income in 2022?", [PlanItem("net income", ["d2"])])

    monkeypatch.setattr(retrieval_step, "plan_with_then", plan)
    monkeypatch.setattr(retrieval_step, "continue_plan", cont)
    search = FakeSearch()
    found = await retrieval_step.retrieve_for_scope(search, SEQUENTIAL, "nb", _docs())
    assert search.planned[1] == ("What was PepsiCo's net income in 2022?", [("net income", ["d2"])])
    assert [c["chunk_id"] for c in found.retrieved] == ["c1", "c2", "c3"]  # first step's excerpts keep their numbers, the new one follows
    assert found.hop["found"] == "PepsiCo, Inc." and found.hop["citations"] == [2] and found.hop["added"] == 1


async def test_a_bare_comparison_in_then_makes_no_intermediate_call(flags, monkeypatch):
    flags(multihop=True)

    async def plan(q, catalog):
        return [PlanItem("total revenues", ["d1", "d2"])], "Which was higher?"

    async def never(*a):
        raise AssertionError("no intermediate call for a comparison")

    monkeypatch.setattr(retrieval_step, "plan_with_then", plan)
    monkeypatch.setattr(retrieval_step, "continue_plan", never)
    search = FakeSearch()
    found = await retrieval_step.retrieve_for_scope(search, "Which had higher revenue in 2022, Coca-Cola or PepsiCo? Which was higher?", "nb", _docs())
    assert len(search.planned) == 1 and found.hop.get("skipped") == "no item to look up"


async def test_an_unsettled_first_step_keeps_the_first_search_only(flags, monkeypatch):
    flags(multihop=True)

    async def plan(q, catalog):
        return [PlanItem("total revenues", ["d1", "d2"])], "what was its net income?"

    async def nothing(*a):
        return None

    monkeypatch.setattr(retrieval_step, "plan_with_then", plan)
    monkeypatch.setattr(retrieval_step, "continue_plan", nothing)
    search = FakeSearch()
    found = await retrieval_step.retrieve_for_scope(search, SEQUENTIAL, "nb", _docs())
    assert len(search.planned) == 1 and [c["chunk_id"] for c in found.retrieved] == ["c1", "c2"] and found.hop.get("skipped") == "first step not settled"


async def test_flag_off_never_asks_for_then(flags, monkeypatch):
    flags()

    async def plan(q, catalog):
        return [PlanItem("total revenues", ["d1", "d2"])]

    async def never(*a):
        raise AssertionError("the C2 prompt is not used with the flag off")

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", plan)
    monkeypatch.setattr(retrieval_step, "plan_with_then", never)
    found = await retrieval_step.retrieve_for_scope(FakeSearch(), SEQUENTIAL, "nb", _docs())
    assert found.hop == {}


# ---------------------------------------------------------------- the code net when the planner gives nothing
async def test_whole_message_without_a_plan_routes_each_part_by_code(flags, monkeypatch):
    flags(whole=True)

    async def no_plan(q, catalog):
        return []

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", no_plan)
    search = FakeSearch()
    found = await retrieval_step.retrieve_for_scope(search, INDEPENDENT, "nb", _docs())
    assert search.multi == [[("What was Coca-Cola's revenue in 2022?", ["d1"])], [("What was PepsiCo's net income in 2022?", ["d2"])]]
    assert found.routing == "r5" and [c["chunk_id"] for c in found.retrieved] == ["m1", "m2"]
