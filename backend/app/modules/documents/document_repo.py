from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.infrastructure.database import collections
from app.shared.base_repo import BaseRepository
from app.shared.common import get_utc_now
from app.modules.documents.document import ACTIVE_STATUSES, DocumentRecord


class DocumentRepository(BaseRepository):
    """Data Access Layer for documents."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.DOCUMENTS_COLLECTION)

    async def get_by_id(self, document_id: str) -> Optional[DocumentRecord]:
        doc = await self.find_one({"document_id": document_id})
        return DocumentRecord(**doc) if doc else None

    async def get_by_notebook(self, notebook_id: str) -> List[DocumentRecord]:
        docs = await self.find_many({"notebook_id": notebook_id}, sort_by=[("created_at", -1)])
        return [DocumentRecord(**doc) for doc in docs]

    async def counts_by_notebook(self, notebook_ids: List[str]) -> Dict[str, Dict[str, int]]:
        """{notebook_id: {document_count, processing_count}} in one query, for the notebook list."""
        pipeline = [
            {"$match": {"notebook_id": {"$in": notebook_ids}}},
            {"$group": {
                "_id": "$notebook_id",
                "document_count": {"$sum": 1},
                "processing_count": {"$sum": {"$cond": [{"$in": ["$status", list(ACTIVE_STATUSES)]}, 1, 0]}},
            }},
        ]
        return {
            row["_id"]: {"document_count": row["document_count"], "processing_count": row["processing_count"]}
            async for row in self.collection.aggregate(pipeline)
        }

    async def update_status(self, document_id: str, status: str) -> bool:
        return await self.update_one({"document_id": document_id}, {"status": status, "updated_at": get_utc_now()})

    async def save_document(self, doc: DocumentRecord) -> str:
        return await self.insert_one(doc.model_dump())

    async def delete_document(self, document_id: str) -> bool:
        return await self.delete_one({"document_id": document_id})
