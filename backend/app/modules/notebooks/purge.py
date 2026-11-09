"""Complete removal of a document or a notebook: one place, shared by the delete endpoints and the expiry of guest notebooks."""
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.database import collections
from app.infrastructure.storage.local_fs import StorageService
from app.modules.documents.document import ACTIVE_STATUSES, DocumentRecord
from app.modules.documents.document_repo import DocumentRepository
from app.modules.ingestion.chunk_repo import ChunkRepository
from app.modules.ingestion.ingestion_job_repo import IngestionJobRepository
from app.modules.notebooks.notebook_repo import NotebookRepository

GUEST_LIFETIME = timedelta(hours=24)


async def purge_document(db: AsyncIOMotorDatabase, qdrant: AsyncQdrantClient, document: DocumentRecord) -> None:
    """Vectors and files first, the document record last: if a step fails the record stays, so the deletion can be retried."""
    if await qdrant.collection_exists(settings.QDRANT_COLLECTION_NAME):
        await qdrant.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document.document_id))])
            ),
            wait=True,
        )
    await StorageService().delete_document_files(document.notebook_id, document.document_id, document.file_path)
    await ChunkRepository(db).delete_by_document(document.document_id)
    await IngestionJobRepository(db).delete_by_document(document.document_id)
    await DocumentRepository(db).delete_document(document.document_id)


async def purge_notebook(db: AsyncIOMotorDatabase, qdrant: AsyncQdrantClient, notebook_id: str) -> None:
    """Every document with its vectors and files, the messages, then the notebook itself."""
    for document in await DocumentRepository(db).get_by_notebook(notebook_id):
        await purge_document(db, qdrant, document)
    await db[collections.MESSAGES_COLLECTION].delete_many({"notebook_id": notebook_id})
    StorageService().delete_notebook_folder(notebook_id)
    await NotebookRepository(db).delete_notebook(notebook_id)


async def has_active_documents(db: AsyncIOMotorDatabase, notebook_id: str) -> bool:
    return any(d.status in ACTIVE_STATUSES for d in await DocumentRepository(db).get_by_notebook(notebook_id))


async def purge_expired_guests(db: AsyncIOMotorDatabase, qdrant: AsyncQdrantClient) -> int:
    """Remove guest notebooks unused for 24 hours. Not a MongoDB TTL index: that deletes only the notebook row and orphans the rest."""
    cutoff = datetime.now(timezone.utc) - GUEST_LIFETIME
    expired = db[collections.NOTEBOOKS_COLLECTION].find({"owner_type": "guest", "updated_at": {"$lt": cutoff}}, {"notebook_id": 1})
    removed = 0
    async for notebook in expired:
        try:
            if not await has_active_documents(db, notebook["notebook_id"]):
                await purge_notebook(db, qdrant, notebook["notebook_id"])
                removed += 1
        except Exception as exc:  # the next round retries: the notebook row is removed last
            logger.warning(f"Could not purge guest notebook {notebook['notebook_id']}: {type(exc).__name__}: {exc}")
    return removed
