from typing import Any, Dict, List, Optional
from pydantic import Field
from app.shared.common import BaseSchema, get_utc_now


class ChunkDocument(BaseSchema):
    """Canonical chunk document stored in MongoDB (source of truth for chunk text)."""

    chunk_id: str = Field(..., description="Unique chunk identifier, e.g. chunk_0042")
    notebook_id: str
    document_id: str
    chunk_index: int = Field(0, description="Position of the chunk in its document (0, 1, 2...)")
    page: int
    section: Optional[str] = None
    chunk_type: str = Field(default="text")
    text_type: str = Field(default="narrative")
    content: str = Field(..., description="Full text/markdown representation of the chunk")
    token_count: Optional[int] = None
    sparse_weights: Dict[str, float] = Field(default_factory=dict, description="BGE-M3 lexical weights {token id: weight}; empty for chunks indexed before 2026-10-27")
    table_metadata: Optional[Dict[str, Any]] = None
    flags: List[str] = Field(default_factory=list, description="'suspicious_instruction': the text addresses an assistant (kept, treated as data)")
    embedding_model: Optional[str] = None
    created_at: Any = Field(default_factory=get_utc_now)
