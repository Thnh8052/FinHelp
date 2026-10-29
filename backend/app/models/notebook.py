from typing import Any, List, Optional
from pydantic import Field
from app.models.common import BaseSchema, get_utc_now


class NotebookRecord(BaseSchema):
    """Notebook record stored in MongoDB `notebooks` collection."""

    notebook_id: str = Field(..., description="Unique notebook ID (nb_001)")
    user_id: str = Field(..., description="Owner user ID")
    title: str = Field(..., description="Display title of the notebook")
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    document_ids: List[str] = Field(default_factory=list)
    created_at: Any = Field(default_factory=get_utc_now)
    updated_at: Any = Field(default_factory=get_utc_now)
