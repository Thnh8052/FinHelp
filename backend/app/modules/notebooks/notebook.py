from typing import Any, Dict
from pydantic import Field
from app.shared.common import BaseSchema, get_utc_now

GUEST_TITLE = "Không Gian Dùng Thử (Khách Chưa Đăng Nhập)"  # a guest notebook's title until its first searched question names it
UNTITLED_TITLE = "Hội thoại mới"
UNTITLED = {UNTITLED_TITLE, GUEST_TITLE}  # titles nobody chose
TITLE_CHARS = 40


def shown_title(title: str) -> str:
    """The title the interface receives: empty for one nobody chose, so the interface names it in the user's language."""
    return "" if title in UNTITLED else title


def title_from_question(query: str) -> str:
    """A chat named after its first question: at most TITLE_CHARS, cut between words and marked with an ellipsis."""
    query = " ".join(query.split())
    if len(query) <= TITLE_CHARS:
        return query
    head = query[:TITLE_CHARS]
    return (head.rsplit(" ", 1)[0] if " " in head else head).rstrip(" ,.;:") + "…"


class NotebookRecord(BaseSchema):
    """Notebook record stored in MongoDB `notebooks` collection. One notebook is one conversation: its documents and messages point to it."""

    notebook_id: str = Field(..., description="Unique notebook ID (nb_001)")
    owner_type: str = Field(default="user", description="'user', 'guest' or 'system' (read-only sample)")
    owner_id: str = Field(..., description="user_id, the random part of a guest notebook id, or 'system'")
    title: str = UNTITLED_TITLE
    focus_state: Dict[str, Any] = Field(default_factory=dict)  # {active_ticker, fiscal_year, last_metric}: what the conversation is about (F4)
    message_count: int = 0  # atomic counter that gives each message its message_index
    created_at: Any = Field(default_factory=get_utc_now)
    updated_at: Any = Field(default_factory=get_utc_now)
