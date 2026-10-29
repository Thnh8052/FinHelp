from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.chunk import ChunkDocument


class ChunkRepository(BaseRepository):
    """Data Access Layer for chunks in MongoDB.

    MongoDB acts as the single source of truth for text content.
    Qdrant only indexes embeddings and returns chunk_ids upon retrieval.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.CHUNKS_COLLECTION)

    async def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[ChunkDocument]:
        """Fetch chunks matching the specified list of chunk_ids, preserving rank order."""
        if not chunk_ids:
            return []

        query = {"chunk_id": {"$in": chunk_ids}}
        docs = await self.find_many(query, limit=len(chunk_ids))

        # Map to preserve Qdrant rank order
        doc_map: Dict[str, ChunkDocument] = {
            doc["chunk_id"]: ChunkDocument(**doc) for doc in docs if "chunk_id" in doc
        }
        return [doc_map[cid] for cid in chunk_ids if cid in doc_map]

    async def get_sparse_weights(self, chunk_ids: List[str]) -> Dict[str, Tuple[Dict[str, float], int]]:
        """{chunk_id: (lexical weights, token count)} without the text: the hybrid search scores every chunk of the searched documents."""
        if not chunk_ids:
            return {}
        cursor = self.collection.find({"chunk_id": {"$in": chunk_ids}}, {"chunk_id": 1, "sparse_weights": 1, "token_count": 1, "_id": 0})
        return {d["chunk_id"]: (d.get("sparse_weights") or {}, d.get("token_count") or 0) async for d in cursor}

    async def get_chunks_by_document(
        self, document_id: str, page: Optional[int] = None
    ) -> List[ChunkDocument]:
        """Get all chunks for a document or specific page."""
        query = {"document_id": document_id}
        if page is not None:
            query["page"] = page
        docs = await self.find_many(query, sort_by=[("page", 1), ("chunk_id", 1)])
        return [ChunkDocument(**doc) for doc in docs]

    async def save_chunks(self, chunks: List[ChunkDocument]) -> List[str]:
        """Bulk save chunk documents."""
        data = [chunk.model_dump() for chunk in chunks]
        return await self.insert_many(data)

    async def delete_by_document(self, document_id: str) -> int:
        result = await self.collection.delete_many({"document_id": document_id})
        return result.deleted_count
