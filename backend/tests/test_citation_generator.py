"""The excerpt shown as evidence must stay valid Markdown."""
from app.modules.generation.citation_generator import SNIPPET_CHARS, CitationGenerator, clip_snippet


def _table(rows: int) -> str:
    return "\n".join(["| Item | 2023 | 2022 |", "| --- | --- | --- |"] + [f"| Revenue line {i} | 1,234 | 5,678 |" for i in range(rows)])


def test_a_short_excerpt_is_unchanged():
    assert clip_snippet("| a |\n| - |\n| 1 |") == "| a |\n| - |\n| 1 |"


def test_a_long_table_keeps_only_whole_rows():
    clipped = clip_snippet(_table(200))
    body, ellipsis = clipped.rsplit("\n\n", 1)
    assert ellipsis == "…" and len(body) <= SNIPPET_CHARS
    assert all(line.startswith("|") and line.endswith("|") and line.count("|") == 4 for line in body.split("\n"))


def test_a_paragraph_without_line_breaks_is_cut_between_words():
    text = "word " * 400
    body = clip_snippet(text).rsplit("\n\n", 1)[0]
    assert set(body.split(" ")) == {"word"}


def test_text_without_any_break_is_still_limited():
    assert clip_snippet("x" * 5000) == "x" * SNIPPET_CHARS + "\n\n…"


def test_citations_use_the_clipped_excerpt():
    chunk = {"chunk_id": "c", "document_id": "d", "page": 1, "content": _table(200)}
    assert CitationGenerator.from_retrieved_chunk(chunk, 1).snippet == clip_snippet(_table(200))
