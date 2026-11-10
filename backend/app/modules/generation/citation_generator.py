from typing import Any, Dict
from app.modules.chat.chat_models import CitationItem

# The evidence pane is for checking numbers against the source, so show the excerpt itself, not a teaser.
SNIPPET_CHARS = 1200


def clip_snippet(content: str, limit: int = SNIPPET_CHARS) -> str:
    """At most `limit` characters ending at a line break, so that a row of a Markdown table is never cut in half; a paragraph without
    line breaks is cut at a space. The ellipsis says the excerpt goes on; its blank line keeps it out of the table."""
    if len(content) <= limit:
        return content
    cut = content.rfind("\n", 0, limit + 1)
    if cut <= 0:
        cut = content.rfind(" ", 0, limit + 1)
    return content[: cut if cut > 0 else limit].rstrip() + "\n\n…"


class CitationGenerator:
    """Builds verifiable citation references with exact document provenance."""

    @staticmethod
    def from_retrieved_chunk(chunk: Dict[str, Any], rank_idx: int) -> CitationItem:
        return CitationItem(
            citation_id=f"cite_chunk_{rank_idx}",
            chunk_id=chunk["chunk_id"],
            document_id=chunk["document_id"],
            page=chunk["page"],
            snippet=clip_snippet(chunk["content"]),
            score=chunk.get("score"),
        )
