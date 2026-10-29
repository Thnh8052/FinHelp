from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.common import BaseSchema, get_utc_now


class CitationItem(BaseModel):
    """Citation back-reference for grounding assistant statements."""

    citation_id: str
    chunk_id: str
    document_id: str
    page: int
    table_id: Optional[str] = None
    row_label: Optional[str] = None
    column_label: Optional[str] = None
    snippet: str
    score: Optional[float] = None
    cited: Optional[bool] = None  # whether the answer writes this excerpt's [n]; None when unknown (older messages, multi-question answers)


class MessageRecord(BaseSchema):
    """Chat message stored in MongoDB `messages` collection."""

    message_id: str
    session_id: str
    role: str = Field(..., description="'user', 'assistant', 'system'")
    content: str
    citations: List[CitationItem] = Field(default_factory=list)
    trace_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Input policy decision, retrieval plan, sub-queries, retrieved pages"
    )
    created_at: Any = Field(default_factory=get_utc_now)


class ChatSessionRecord(BaseSchema):
    """Chat session stored in MongoDB `chat_sessions` collection."""

    session_id: str
    notebook_id: str
    user_id: str
    title: str = "Hội thoại mới"
    created_at: Any = Field(default_factory=get_utc_now)
    updated_at: Any = Field(default_factory=get_utc_now)
