from typing import Any, Dict
from pydantic import Field
from app.shared.common import BaseSchema, get_utc_now


class NotebookRecord(BaseSchema):
    """Notebook record stored in MongoDB `notebooks` collection. One notebook is one conversation: its documents and messages point to it."""

    notebook_id: str = Field(..., description="Unique notebook ID (nb_001)")
    owner_type: str = Field(default="user", description="'user', 'guest' or 'system' (read-only sample)")
    owner_id: str = Field(..., description="user_id, the random part of a guest notebook id, or 'system'")
    title: str = "Hội thoại mới"
    focus_state: Dict[str, Any] = Field(default_factory=dict)  # {active_ticker, fiscal_year, last_metric}: what the conversation is about (F4)
    message_count: int = 0  # atomic counter that gives each message its message_index
    created_at: Any = Field(default_factory=get_utc_now)
    updated_at: Any = Field(default_factory=get_utc_now)
