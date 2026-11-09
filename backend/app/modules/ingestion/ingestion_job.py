from typing import Any, Dict, Optional
from pydantic import Field
from app.shared.common import BaseSchema, get_utc_now


class IngestionJobRecord(BaseSchema):
    """Job tracking record in MongoDB `ingestion_jobs` collection (one job per document)."""

    job_id: str = Field(..., description="Unique job ID (job_001)")
    document_id: str
    notebook_id: str
    worker_id: Optional[str] = None
    status: str = Field(default="pending", description="'pending', 'processing', 'completed', 'failed'")
    stage: str = Field(default="docling", description="'docling', 'chunking', 'embedding', 'indexing'")
    progress_percent: int = 0
    extracted_chunks_count: int = 0
    error_log: Optional[str] = None
    timings: Dict[str, float] = Field(default_factory=dict)  # seconds: queue_wait, parse (docling_start_s / convert_s / postprocess_s), catalog, chunk, embed_load, embed, persist, total
    queued_at: Any = Field(default_factory=get_utc_now)
    started_at: Optional[Any] = None
    finished_at: Optional[Any] = None
    updated_at: Any = Field(default_factory=get_utc_now)  # moves at every stage: a job that stops moving is failed by fail_stalled
