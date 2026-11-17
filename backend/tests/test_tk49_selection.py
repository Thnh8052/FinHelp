"""TK-49, the chunk selection of the planned path chosen by the owner on 17/11/2026 (docs/VERSION_4/TRIED.md TK-35, TK-44, TK-46, TK-49;
docs/VERSION_4/CONFIG_DECISION_2026-11-17.md): a search with the question in every planned document, threshold 0.2, long text chunks also scored by
windows, and one budget of 13,000 tokens counted as the answer call counts them (cl100k + 25 for the excerpt header) instead of a chunk ceiling.
No model, no worker: fakes as in test_multidoc.py."""
import types

import tiktoken

from app.core.config import settings
from app.modules.query_router.planner import PlanItem
from tests.test_multidoc import _planned, _PlannedChunks


def test_the_defaults_are_tk49():
    assert settings.MULTIDOC_REL_THRESHOLD == 0.2
    assert settings.MULTIDOC_PLANNED_MAX_TOKENS == 13000  # the gate and its GATE_MAX_TOKENS are gone (TK-55)
    assert settings.MULTIDOC_MIN_CHUNKS == 60  # the token budget decides, not a chunk count (TK-46)
    assert settings.MULTIDOC_QUESTION_LANE_PER_DOC is True
    assert settings.MULTIDOC_TOKEN_UNIT == "cl100k" and settings.EXCERPT_HEADER_TOKENS == 25
    assert settings.RERANK_WINDOWS_ENABLED is True
    assert (settings.RERANK_WINDOW_MIN_TOKENS, settings.RERANK_WINDOW_WORDS, settings.RERANK_WINDOW_STRIDE) == (600, 200, 150)  # 600: TK-56


def test_windows_cover_the_text_with_overlap_and_end_at_its_end():
    from app.modules.retrieval.hybrid_search import windows

    words = [f"w{i}" for i in range(450)]
    got = windows(" ".join(words), 200, 150)
    assert got[0].split() == words[:200] and got[1].split() == words[150:350] and got[-1].split()[-1] == "w449"
    assert len(got) == 3  # 0-200, 150-350, 300-450
    assert windows("short text", 200, 150) == ["short text"]


def test_excerpt_tokens_count_like_the_answer_call(monkeypatch):
    from app.modules.retrieval.hybrid_search import excerpt_tokens

    text = "Net revenue was $86,392 million in 2022."
    assert excerpt_tokens(text, 999) == len(tiktoken.get_encoding("cl100k_base").encode(text)) + 25
    monkeypatch.setattr(settings, "MULTIDOC_TOKEN_UNIT", "stored")
    assert excerpt_tokens(text, 999) == 999  # the BGE-M3 count stored with the chunk, as before TK-46


async def test_every_planned_document_gets_a_search_with_the_question(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_WINDOWS_ENABLED", False)
    by_document = {"d1": [("a1", 0.9), ("a2", 0.8)], "d2": [("b1", 0.9)], "d3": [("c1", 0.99)]}
    text = {"a1": "revenue a", "a2": "other a", "b1": "revenue b", "c1": "never"}
    svc = _planned(monkeypatch, by_document, text, lambda q, t: 0.9)
    await svc.retrieve_planned("the question", [PlanItem("revenue", ["d1", "d2"])], "nb", ["d1", "d2", "d3"])
    # the plan's searches, then the question in each planned document, then the question over all of them (kept to MULTIDOC_QUESTION_KEEP)
    assert svc.retriever.per_vector == [["d1"], ["d2"], ["d1"], ["d2"], ["d1", "d2"]]
    monkeypatch.setattr(settings, "MULTIDOC_QUESTION_LANE_PER_DOC", False)
    await svc.retrieve_planned("the question", [PlanItem("revenue", ["d1", "d2"])], "nb", ["d1", "d2", "d3"])
    assert svc.retriever.per_vector == [["d1"], ["d2"], ["d1", "d2"]]


async def test_a_plan_search_with_the_question_is_not_repeated(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_WINDOWS_ENABLED", False)
    by_document = {"d1": [("a1", 0.9)], "d2": [("b1", 0.9)]}
    svc = _planned(monkeypatch, by_document, {"a1": "x", "b1": "y"}, lambda q, t: 0.9)
    await svc.retrieve_planned("Q?", [PlanItem("revenue", ["d1", "d2"]), PlanItem("Q?", ["d2"])], "nb", ["d1", "d2"])  # R5 already searched d2 with the question
    assert svc.retriever.per_vector == [["d1"], ["d2"], ["d2"], ["d1"], ["d1", "d2"]]


class _TypedChunks(_PlannedChunks):
    def __init__(self, text, by_document, kinds, counts):
        super().__init__(text, by_document)
        self.kinds, self.counts = kinds, counts

    async def get_chunks_by_ids(self, ids):
        return [types.SimpleNamespace(chunk_id=i, document_id="d", page=1, section=None, chunk_type=self.kinds.get(i, "text"), content=self.text[i],
                                      token_count=self.counts.get(i, 100), concept_ids=[]) for i in ids]


async def test_a_long_text_chunk_is_also_scored_by_its_windows_and_keeps_its_best(monkeypatch):
    long_text = " ".join(["filler"] * 300 + ["headcount", "was", "9,800"] + ["filler"] * 100)
    by_document = {"d1": [("long", 0.9), ("table", 0.8), ("short", 0.7)]}
    text = {"long": long_text, "table": " ".join(["cell"] * 450), "short": "short text"}
    svc = _planned(monkeypatch, by_document, text, lambda q, t: 0.95 if "headcount" in t and len(t.split()) <= 200 else 0.1)
    svc.chunk_repo = _TypedChunks(text, by_document, {"table": "table"}, {"long": 700, "table": 700, "short": 50})  # over RERANK_WINDOW_MIN_TOKENS (600)
    monkeypatch.setattr(settings, "MULTIDOC_QUESTION_LANE_PER_DOC", False)
    chunks = await svc.retrieve_planned("headcount?", [PlanItem("employees", ["d1"])], "nb", ["d1"])
    scored = [t for q, t in svc.reranker.scored if q == "employees"]
    assert any(len(t.split()) <= 200 and "headcount" in t for t in scored)  # a window of the long text chunk was scored
    assert not any(t != text["table"] and set(t.split()) == {"cell"} for t in scored)  # a chunk with a table is scored whole only
    assert chunks[0]["chunk_id"] == "long" and chunks[0]["content"] == long_text  # the best window's score ranks it; the whole chunk is sent
