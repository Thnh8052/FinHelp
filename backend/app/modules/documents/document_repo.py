from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.infrastructure.database import collections
from app.shared.base_repo import BaseRepository
from app.shared.common import get_utc_now
from app.modules.documents.document import DocumentRecord


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

    async def update_status(self, document_id: str, status: str) -> bool:
        return await self.update_one({"document_id": document_id}, {"status": status, "updated_at": get_utc_now()})

    async def save_document(self, doc: DocumentRecord) -> str:
        return await self.insert_one(doc.model_dump())

    async def delete_document(self, document_id: str) -> bool:
        return await self.delete_one({"document_id": document_id})
