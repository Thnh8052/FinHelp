"""L2 and L4 of docs/Version_3/plan_rag_improvements.md: word counts kept between questions (same chunks, one read per document) and the safety net run beside the main search."""
import asyncio

from tests.test_multidoc import _doc, _orchestrator, _planned

from app.modules.chat import retrieval_step
from app.modules.query_router.planner import PlanItem
from app.modules.retrieval.term_cache import TERMS, TermCountCache


async def test_word_counts_are_read_once_per_document_and_give_the_same_chunks(monkeypatch):
    by_document = {"d1": [("a1", 0.9), ("a2", 0.8)], "d2": [("b1", 0.9)]}
    text = {"a1": "revenue a", "a2": "other", "b1": "revenue b"}
    svc = _planned(monkeypatch, by_document, text, lambda q, t: 0.9 if "revenue" in t else 0.1)
    first = await svc.retrieve_planned("q", [PlanItem("revenue", ["d1"])], "nb", ["d1", "d2"])
    assert svc.chunk_repo.reads == [["d1"]]
    await svc.retrieve_planned("q", [PlanItem("revenue", ["d1", "d2"])], "nb", ["d1", "d2"])
    assert svc.chunk_repo.reads == [["d1"], ["d2"]]  # d1 came from memory
    again = await svc.retrieve_planned("q", [PlanItem("revenue", ["d1"])], "nb", ["d1", "d2"])
    assert svc.chunk_repo.reads == [["d1"], ["d2"]] and [c["chunk_id"] for c in again] == [c["chunk_id"] for c in first]
    TERMS.drop("d1")  # what ChunkRepository.delete_by_document does
    await svc.retrieve_planned("q", [PlanItem("revenue", ["d1"])], "nb", ["d1", "d2"])
    assert svc.chunk_repo.reads[-1] == ["d1"]


def test_term_cache_forgets_the_least_recently_used_document_and_ignores_empty_ones():
    from collections import Counter

    cache = TermCountCache(max_chunks=5)
    entry = lambda n: {f"c{i}": (Counter(a=1), 10) for i in range(n)}
    cache.put("d1", entry(3))
    cache.put("d2", entry(2))
    assert cache.get("d1") is not None  # d1 is now the most recent
    cache.put("d3", entry(2))  # 7 chunks: d2, the least recent, leaves
    assert cache.get("d2") is None and cache.get("d1") is not None and cache.get("d3") is not None
    cache.put("d4", {})
    assert cache.get("d4") is None
    cache.put("big", entry(9))  # one document larger than the limit still stays alone
    assert cache.get("big") is not None and cache.get("d1") is None
    cache.drop("big")
    assert cache._chunks == 0


async def test_the_net_runs_beside_the_main_search_and_drops_what_the_main_search_holds(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod

    docs = [_doc("d1", "a.pdf", company_name="Coca-Cola", fiscal_year=2022), _doc("d2", "b.pdf", company_name="PepsiCo", fiscal_year=2022)]
    order = []

    class FakeSearch:
        async def prescore(self, *a):
            return None

        async def retrieve_planned(self, question, plan, notebook_id, scope_ids):
            order.append("main start")
            await asyncio.sleep(0.05)
            order.append("main end")
            return [{"chunk_id": "c1", "document_id": "d1", "page": 1, "content": "x" * 400, "chunk_type": "table", "score": 1.0}]

        async def safety_net(self, question, plan_queries, notebook_id, document_ids, exclude, kept_document_ids=None):
            order.append("net start")
            await asyncio.sleep(0.01)
            order.append("net end")
            dup = {"chunk_id": "c1", "document_id": "d1", "page": 1, "content": "x", "chunk_type": "table", "score": 0.9}
            new = {"chunk_id": "n2", "document_id": "d2", "page": 5, "content": "pepsi", "chunk_type": "table", "score": 0.8}
            return [(dup, 100), (new, 100)]

    async def plan_one(query, catalog):
        return [PlanItem("net revenues", ["d1"])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", plan_one)
    monkeypatch.setattr(orch_mod.settings, "NET_ENABLED", True)
    orch = _orchestrator(docs)
    orch.hybrid_search = FakeSearch()
    found = await orch.retrieve("Compare Coca-Cola and PepsiCo revenue in 2022", "nb", docs)
    assert order.index("net start") < order.index("main end")  # started before the main search finished
    assert [c["chunk_id"] for c in found.retrieved] == ["c1", "n2"] and found.routing == "planner+net"
