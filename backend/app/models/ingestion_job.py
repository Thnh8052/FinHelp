from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.common import BaseSchema, get_utc_now


class IngestionJobRecord(BaseSchema):
    """Job tracking record in MongoDB `ingestion_jobs` collection."""

    job_id: str = Field(..., description="Unique job ID (job_001)")
    document_id: str
    notebook_id: str
    status: str = Field(
        default="pending",
        description="'pending', 'parsing', 'chunking', 'indexing_qdrant', 'completed', 'failed'"
    )
    progress_percent: int = 0
    total_pages: int = 0
    processed_pages: int = 0
    extracted_chunks_count: int = 0
    error_log: Optional[str] = None
    retry_count: int = 0
    timings: Dict[str, float] = Field(default_factory=dict)  # seconds: queue_wait, parse (docling_start_s / convert_s / postprocess_s), catalog, chunk, embed_load, embed, persist, total
    created_at: Any = Field(default_factory=get_utc_now)
    completed_at: Optional[Any] = None
