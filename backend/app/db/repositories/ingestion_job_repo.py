from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.ingestion_job import IngestionJobRecord


class IngestionJobRepository(BaseRepository):
    """Data Access Layer for tracking background ingestion jobs."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.INGESTION_JOBS_COLLECTION)

    async def get_by_id(self, job_id: str) -> Optional[IngestionJobRecord]:
        doc = await self.find_one({"job_id": job_id})
        return IngestionJobRecord(**doc) if doc else None

    async def update_progress(
        self,
        job_id: str,
        status: str,
        progress_percent: int,
        error_log: Optional[str] = None,
    ) -> bool:
        update: dict = {
            "status": status,
            "progress_percent": progress_percent,
        }
        if error_log:
            update["error_log"] = error_log
        return await self.update_one({"job_id": job_id}, update)

    async def save_job(self, job: IngestionJobRecord) -> str:
        return await self.insert_one(job.model_dump())

    async def delete_by_document(self, document_id: str) -> int:
        result = await self.collection.delete_many({"document_id": document_id})
        return result.deleted_count
