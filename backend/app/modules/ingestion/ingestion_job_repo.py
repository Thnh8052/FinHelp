from typing import Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.infrastructure.database import collections
from app.shared.base_repo import BaseRepository
from app.shared.common import get_utc_now
from app.modules.ingestion.ingestion_job import IngestionJobRecord


class IngestionJobRepository(BaseRepository):
    """Data Access Layer for tracking background ingestion jobs."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.INGESTION_JOBS_COLLECTION)

    async def get_by_id(self, job_id: str) -> Optional[IngestionJobRecord]:
        doc = await self.find_one({"job_id": job_id})
        return IngestionJobRecord(**doc) if doc else None

    async def start(self, job_id: str, worker_id: str) -> bool:
        now = get_utc_now()
        return await self.update_one({"job_id": job_id}, {"status": "processing", "worker_id": worker_id, "started_at": now, "updated_at": now})

    async def update_progress(self, job_id: str, stage: str, progress_percent: int) -> bool:
        return await self.update_one({"job_id": job_id}, {"stage": stage, "progress_percent": progress_percent, "updated_at": get_utc_now()})

    async def finish(self, job_id: str, chunks: int, timings: Dict[str, float]) -> bool:
        now = get_utc_now()
        return await self.update_one(
            {"job_id": job_id},
            {"status": "completed", "progress_percent": 100, "extracted_chunks_count": chunks, "timings": timings, "finished_at": now, "updated_at": now},
        )

    async def fail(self, job_id: str, error_log: str) -> bool:
        now = get_utc_now()
        return await self.update_one(
            {"job_id": job_id}, {"status": "failed", "progress_percent": 0, "error_log": error_log, "finished_at": now, "updated_at": now}
        )

    async def save_job(self, job: IngestionJobRecord) -> str:
        return await self.insert_one(job.model_dump())

    async def delete_by_document(self, document_id: str) -> int:
        result = await self.collection.delete_many({"document_id": document_id})
        return result.deleted_count
