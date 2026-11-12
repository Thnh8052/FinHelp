from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict


def get_utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class BaseSchema(BaseModel):
    """Base schema with common Pydantic configuration."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
