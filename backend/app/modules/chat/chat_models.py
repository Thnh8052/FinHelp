from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.shared.common import BaseSchema, get_utc_now


class CitationItem(BaseModel):
    """Citation back-reference for grounding assistant statements."""

    citation_id: str
    chunk_id: str
    document_id: str
    page: int
    table_id: Optional[str] = None
    snippet: str
    score: Optional[float] = None
    cited: Optional[bool] = None  # whether the answer writes this excerpt's [n]; None when unknown (older messages, multi-question answers)
    may_be_misread: bool = False  # the excerpt's page failed the table check at upload (chunk flag "table_check"): the interface says to check the page
    read_from_image: bool = False  # the page's text was recognised from its image (chunk flag "ocr"): the interface says to compare with the page
    from_figure: bool = False  # the excerpt holds figures read from a chart or picture (chunk flag "figure"): the interface says so
    picture_unread: bool = False  # a picture on the excerpt's page could not be read (chunk flag "picture_unread"): the interface says so


class MessageRecord(BaseSchema):
    """Chat message stored in MongoDB `messages` collection."""

    message_id: str
    notebook_id: str
    message_index: int = 0  # given by ChatRepository.append_message: 0, 1, 2... within the notebook
    role: str = Field(..., description="'user', 'assistant', 'system'")
    content: str
    citations: List[CitationItem] = Field(default_factory=list)
    trace_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Input policy decision, retrieval plan, sub-queries, retrieved pages"
    )
    token_usage: Dict[str, int] = Field(default_factory=dict)  # {prompt_tokens, completion_tokens, total_tokens} of the whole request
    latency_ms: Optional[int] = None
    model_used: Optional[str] = None
    user_rating: Optional[int] = None  # -1: the user reported wrong figures (PUT /chat/messages/{nb}/{id}/flag)
    rated_at: Optional[Any] = None  # when user_rating last changed: the admin review list shows the newest reports first
    created_at: Any = Field(default_factory=get_utc_now)
