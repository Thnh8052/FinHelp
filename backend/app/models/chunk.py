from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.common import BaseSchema, get_utc_now


class ChunkPayload(BaseModel):
    """Metadata stored in Qdrant Point payload for hybrid search & filtering."""

    chunk_id: str
    notebook_id: str
    document_id: str
    page: int
    section: Optional[str] = None
    chunk_type: str = Field(default="text", description="'text', 'table', 'footnote', 'header'")
    text_type: str = Field(default="narrative", description="'financial_statement', 'notes', 'auditor_report', 'narrative'")
    concept_ids: List[str] = Field(default_factory=list, description="Associated normalized financial concepts")


class ChunkDocument(BaseSchema):
    """Canonical chunk document stored in MongoDB (source of truth for chunk text)."""

    chunk_id: str = Field(..., description="Unique chunk identifier, e.g. chunk_0042")
    notebook_id: str
    document_id: str
    page: int
    page_end: Optional[int] = None
    section: Optional[str] = None
    chunk_type: str = Field(default="text")
    text_type: str = Field(default="narrative")
    content: str = Field(..., description="Full text/markdown representation of the chunk")
    token_count: Optional[int] = None
    page_tokens: Dict[str, int] = Field(default_factory=dict, description="Tokens per PDF page (exact page for citations)")
    concept_ids: List[str] = Field(default_factory=list)
    sparse_weights: Dict[str, float] = Field(default_factory=dict, description="BGE-M3 lexical weights {token id: weight}; empty for chunks indexed before 2026-10-27")
    table_metadata: Optional[Dict[str, Any]] = None
    flags: List[str] = Field(default_factory=list, description="'suspicious_instruction': the text addresses an assistant (kept, treated as data)")
    bounding_box: Optional[Dict[str, float]] = None
    created_at: Any = Field(default_factory=get_utc_now)
