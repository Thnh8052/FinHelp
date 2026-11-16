"""L2 of docs/Version_2/plans/plan_rag_improvements.md: word counts kept between questions (same chunks, one read per document)."""
from tests.test_multidoc import _planned

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
