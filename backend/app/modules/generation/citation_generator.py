from typing import Any, Dict
from app.modules.chat.chat_models import CitationItem

# The evidence pane is for checking numbers against the source, so show the excerpt itself, not a teaser.
SNIPPET_CHARS = 1200


class CitationGenerator:
    """Builds verifiable citation references with exact document provenance."""

    @staticmethod
    def from_retrieved_chunk(chunk: Dict[str, Any], rank_idx: int) -> CitationItem:
        return CitationItem(
            citation_id=f"cite_chunk_{rank_idx}",
            chunk_id=chunk["chunk_id"],
            document_id=chunk["document_id"],
            page=chunk["page"],
            snippet=chunk["content"][:SNIPPET_CHARS],
            score=chunk.get("score"),
        )
