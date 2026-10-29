from typing import Any, Dict, List
from app.models.chat import CitationItem

# The evidence pane is for checking numbers against the source, so show the excerpt itself, not a teaser.
SNIPPET_CHARS = 1200


class CitationGenerator:
    """Builds verifiable citation references with exact document provenance."""

    @staticmethod
    def from_financial_evidence(
        document_id: str,
        evidence_dict: Dict[str, Any],
        raw_label: str,
        value: str,
    ) -> CitationItem:
        page = evidence_dict.get("page", 1)
        row = evidence_dict.get("row_label", raw_label)
        col = evidence_dict.get("column_label", "")
        table = evidence_dict.get("table_id", "")

        snippet = f"{row} | {col}: {value}" if col else f"{row}: {value}"

        return CitationItem(
            citation_id=f"cite_fact_{page}_{table}",
            chunk_id=table or f"doc_{document_id}_p{page}",
            document_id=document_id,
            page=page,
            table_id=table,
            row_label=row,
            column_label=col,
            snippet=snippet,
        )

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
