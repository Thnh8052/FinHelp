"""A document the user tagged (@file, or ticked in the answer's chooser) is searched even when the plan leaves it out (UI check 17/11: Amazon was ticked,
the planner wrote queries for Costco only, Amazon got no search and the answer said its excerpts were "not found"). Like R5 for a named document: one
search with the question."""
from app.core.config import settings
from app.modules.chat import retrieval_step
from app.modules.query_router.planner import PlanItem
from tests.test_no_gate import _doc


class Search:
    def __init__(self):
        self.plan = None

    async def retrieve_planned(self, question, plan, notebook_id, scope_ids, **kwargs):
        self.plan = list(plan)
        return [{"chunk_id": f"c_{d}", "document_id": d, "page": 1, "content": "x", "score": 0.5} for p in plan for d in p.document_ids]


async def _run(monkeypatch, forced):
    async def plan(query, catalog):
        return [PlanItem("net sales", ["d1"])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", plan)
    monkeypatch.setattr(settings, "MULTIDOC_ENABLED", True)
    search = Search()
    found = await retrieval_step.retrieve_for_scope(search, "What was the latest revenue?", "nb",
                                                    [_doc("d1", "Costco", 2015), _doc("d2", "Amazon", 2018), _doc("d3", "Walmart", 2015)], forced)
    return search, found


async def test_a_tagged_document_the_plan_leaves_out_gets_a_search_with_the_question(monkeypatch):
    search, found = await _run(monkeypatch, ["d1", "d2"])
    assert PlanItem("What was the latest revenue?", ["d2"]) in search.plan
    assert found.missing == []


async def test_without_tags_the_plan_is_kept_as_the_planner_wrote_it(monkeypatch):
    search, _ = await _run(monkeypatch, None)
    assert search.plan == [PlanItem("net sales", ["d1"])]
