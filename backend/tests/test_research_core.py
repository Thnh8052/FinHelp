"""Unit tests for the research core (no GPU, no network, no database)."""
import json

import pytest

from app.core.config import settings
from app.services.ingestion.chunker import FinancialChunkerService, parse_blocks
from app.services.llm.llm_client import LLMUnavailableError, chat_completion
from app.services.query_router import decomposer
from app.services.rag_workflow import generator
from app.services.retrieval.fusion import descending_ranks, fuse_with_rerank, rrf_merge


def words(text: str) -> int:
    return len(text.split())


# ---------------------------------------------------------------- fusion
def test_rrf_merge_question_weight_beats_single_subquery():
    # "a" is first for the question (weight 2); "b" is first for one sub-query only
    merged = rrf_merge([["a", "b", "c"], ["b", "c", "a"]], [2.0, 1.0])
    assert merged[0] == "a"
    assert set(merged) == {"a", "b", "c"}


def test_rrf_merge_missing_item_adds_nothing():
    assert rrf_merge([["a", "b"], ["c"]], [1.0, 1.0])[:2] == ["a", "c"]  # a and c both rank 0; b only rank 1


def test_descending_ranks_stable_for_ties():
    assert descending_ranks([0.2, 0.9, 0.2, 0.5]) == [2, 0, 3, 1]


def test_fuse_with_rerank_promotes_reranker_favourite():
    pool = ["p0", "p1", "p2", "p3"]
    # the reranker loves p2 (first-stage position 2): 1/62 + 1/60 beats p0's 1/60 + 1/63
    assert fuse_with_rerank(pool, [0.1, 0.2, 0.99, 0.3]) == ["p2", "p0", "p1", "p3"]


# ---------------------------------------------------------------- chunker
PAGE1 = "## Consolidated Balance Sheets\n\n| Item | 2023 | 2022 |\n| --- | --- | --- |\n| Cash | 10 | 8 |\n| Debt | 5 | 6 |\n\n(1) Cash includes restricted cash.\n"
PAGE2 = "Intro paragraph of the next page that is long enough to be its own unit.\n"


def test_parse_blocks_kinds():
    kinds = [k for k, _ in parse_blocks(PAGE1)]
    assert kinds == ["h", "t", "p"]


def test_chunks_are_page_bounded_and_keep_table_with_title_and_footnote():
    pages = [{"page_number": 7, "text": PAGE1}, {"page_number": 8, "text": PAGE2}]
    chunks = FinancialChunkerService.chunk_document("nb", "doc", pages, count_tokens=words, size=1024)
    assert [c.page for c in chunks] == [7, 8]
    first = chunks[0]
    assert first.chunk_type == "table"
    assert "Consolidated Balance Sheets" in first.content and "| Cash | 10 | 8 |" in first.content
    assert "(1) Cash includes restricted cash." in first.content
    assert first.page_tokens == {"7": first.token_count}
    assert chunks[1].chunk_type == "text" and chunks[1].chunk_id == "doc_chk_0002"


def test_oversized_table_splits_by_rows_and_repeats_header():
    rows = "\n".join(f"| Line {i} | {i} | {i + 1} |" for i in range(60))
    page = {"page_number": 1, "text": f"| Item | 2023 | 2022 |\n| --- | --- | --- |\n{rows}\n"}
    chunks = FinancialChunkerService.chunk_document("nb", "doc", [page], count_tokens=words, size=100)
    assert len(chunks) > 1
    assert all(c.content.startswith("| Item | 2023 | 2022 |") for c in chunks)
    body = "\n".join(c.content for c in chunks)
    assert all(f"| Line {i} |" in body for i in range(60))  # no row lost


def test_blank_pages_are_skipped():
    chunks = FinancialChunkerService.chunk_document("nb", "doc", [{"page_number": 1, "text": "  \n"}], count_tokens=words)
    assert chunks == []


# ---------------------------------------------------------------- generator
CHUNKS = [{"document_id": "doc_1", "page": 12, "content": "Revenue was $10 million."}]


def test_context_format_carries_document_and_page():
    ctx = generator.build_context(CHUNKS)
    assert ctx.startswith("--- Excerpt [1] (Document: doc_1, Page: 12) ---")
    assert "Revenue was $10 million." in ctx


@pytest.mark.parametrize("version,marker", [("v2", "financial analyst"), ("v1", "using ONLY the context excerpts")])
def test_prompt_version_switch(monkeypatch, version, marker):
    monkeypatch.setattr(settings, "GENERATION_PROMPT", version)
    system = generator.build_messages("ctx", "Q?")[0]["content"]
    assert marker in system and generator.REFUSAL in system


@pytest.mark.parametrize("version", ["v2", "v2_one", "v1"])
def test_answer_language_follows_question(monkeypatch, version):
    monkeypatch.setattr(settings, "GENERATION_PROMPT", version)
    en = generator.build_messages("ctx", "What was revenue in FY2023?")
    vi = generator.build_messages("ctx", "Doanh thu năm FY2023 là bao nhiêu?")
    assert "LANGUAGE" not in en[0]["content"] and generator.REFUSAL in en[0]["content"] + en[1]["content"]  # English: measured prompt
    assert "LANGUAGE" in vi[0]["content"] and generator.REFUSAL not in vi[0]["content"] + vi[1]["content"]
    assert generator.REFUSAL_VI in vi[0]["content"] and generator.REFUSAL_VI in vi[1]["content"]
    assert generator.is_refusal("... FINAL ANSWER: " + generator.REFUSAL_VI) and generator.is_refusal(generator.REFUSAL)
    assert not generator.is_refusal("FINAL ANSWER: $10 million")


def test_final_answer_extraction():
    assert generator.final_answer("reasoning... FINAL ANSWER: 42%") == "42%"
    assert generator.final_answer("no marker") == "no marker"


# ---------------------------------------------------------------- LLM client and decomposition
async def test_llm_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", None)
    with pytest.raises(LLMUnavailableError):
        await chat_completion([{"role": "user", "content": "hi"}])


async def test_decompose_keeps_first_three_and_caches(monkeypatch):
    calls = []

    async def fake_chat(messages, **kwargs):
        calls.append(1)
        return json.dumps({"queries": ["a", "b", "c", "d", "e"]})

    decomposer._cache.clear()
    monkeypatch.setattr(decomposer, "chat_completion", fake_chat)
    assert await decomposer.decompose_query("What is gross margin?") == ("What is gross margin?", ["a", "b", "c"])
    assert await decomposer.decompose_query("What is gross margin?") == ("What is gross margin?", ["a", "b", "c"])
    assert len(calls) == 1


async def test_decompose_searches_a_vietnamese_question_in_english(monkeypatch):
    prompts = []

    async def fake_chat(messages, **kwargs):
        prompts.append(messages[1]["content"])
        if "Vietnamese" in prompts[-1]:
            return json.dumps({"question_en": "What is the gross margin?", "queries": ["gross profit net sales"]})
        return json.dumps({"queries": ["gross profit net sales"]})

    decomposer._cache.clear()
    monkeypatch.setattr(decomposer, "chat_completion", fake_chat)
    assert await decomposer.decompose_query("Biên lợi nhuận gộp là bao nhiêu?") == ("What is the gross margin?", ["gross profit net sales"])
    assert await decomposer.decompose_query("What is the gross margin?") == ("What is the gross margin?", ["gross profit net sales"])
    assert "question_en" in prompts[0] and prompts[1] == decomposer.PROMPT.format(q="What is the gross margin?")  # English: measured prompt


async def test_decompose_degrades_to_empty_when_llm_down(monkeypatch):
    async def down(messages, **kwargs):
        raise LLMUnavailableError("down")

    decomposer._cache.clear()
    monkeypatch.setattr(decomposer, "chat_completion", down)
    assert await decomposer.decompose_query("Another question?") == ("Another question?", [])


async def test_decompose_ignores_malformed_json(monkeypatch):
    async def bad(messages, **kwargs):
        return "not json"

    decomposer._cache.clear()
    monkeypatch.setattr(decomposer, "chat_completion", bad)
    assert await decomposer.decompose_query("Third question?") == ("Third question?", [])


# ---------------------------------------------------------------- GPU turn-taking on out-of-memory
def _fake_gpu(monkeypatch):
    from app.services.retrieval import gpu

    released = []
    monkeypatch.setattr(gpu, "_UNLOADERS", {"a": lambda: released.append("a"), "b": lambda: released.append("b")})
    monkeypatch.setattr(gpu, "_swap_mode", False)
    monkeypatch.setattr(gpu, "free_gpu_memory", lambda: None)
    return gpu, released


async def test_gpu_oom_releases_other_model_retries_and_keeps_swapping(monkeypatch):
    gpu, released = _fake_gpu(monkeypatch)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("CUDA out of memory. Tried to allocate 20.00 MiB")
        return "ok"

    assert await gpu.run_on_gpu("a", flaky) == "ok"
    assert released == ["b"] and len(calls) == 2 and gpu._swap_mode is True
    released.clear()
    assert await gpu.run_on_gpu("b", lambda: 1) == 1  # swap mode: the other model is released up-front
    assert released == ["a"]


async def test_gpu_second_oom_and_other_errors_propagate(monkeypatch):
    gpu, _ = _fake_gpu(monkeypatch)

    def always_oom():
        raise RuntimeError("CUDA out of memory")

    def broken():
        raise RuntimeError("something else")

    with pytest.raises(RuntimeError, match="out of memory"):
        await gpu.run_on_gpu("a", always_oom)
    monkeypatch.setattr(gpu, "_swap_mode", False)
    with pytest.raises(RuntimeError, match="something else"):
        await gpu.run_on_gpu("a", broken)
    assert gpu._swap_mode is False


# ---------------------------------------------------------------- fast parser
def test_pymupdf_parser_reads_text(tmp_path):
    fitz = pytest.importorskip("fitz")
    from app.services.ingestion.parser import _pymupdf_pages

    pdf = tmp_path / "t.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Total net sales were 100 million")
    doc.new_page()
    doc.save(str(pdf))
    pages = _pymupdf_pages(pdf)
    assert [p["page_number"] for p in pages] == [1, 2]
    assert "Total net sales were 100 million" in pages[0]["text"]
    assert pages[1]["text"] == ""
