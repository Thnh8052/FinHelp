import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import settings
from app.core.exceptions import IngestionError
from app.core.logging import logger
from app.db import collections
from app.db.qdrant import QdrantManager
from app.db.repositories.chunk_repo import ChunkRepository
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.ingestion_job_repo import IngestionJobRepository
from app.services.ingestion.chunker import FinancialChunkerService
from app.services.ingestion.catalog import needs_vlm, read_catalog, read_catalog_vlm, years_covered
from app.services.ingestion.doc_header import company_candidates, extract_document_header
from app.services.ingestion.parser import DoclingSession, PDFParserService
from app.services.query_router.input_policy import instruction_like
from app.services.retrieval.embeddings import DenseEmbeddingService
from app.services.retrieval.gpu import run_on_gpu
from app.services.retrieval.reranker import QwenRerankerService
from app.services.retrieval.warmup import warm_models

UPSERT_BATCH = 64


@dataclass
class _Job:
    pipeline: "IngestionPipeline"
    job_id: str
    document_id: str
    notebook_id: str
    pdf_path: Path
    queued: float = field(default_factory=time.perf_counter)
    pages: List[Dict[str, Any]] = field(default_factory=list)
    engine: str = ""
    chunks: list = field(default_factory=list)
    catalog: Optional[asyncio.Task] = None
    timings: Dict[str, float] = field(default_factory=dict)  # seconds per stage, stored on the job record


# One worker drains the uploads in batches (Docling and the embedding model share one small GPU):
# phase 1 parses every queued file with ONE Docling worker (models loaded once; files uploaded meanwhile join the batch) while the
# catalog of each parsed file is read through the API; phase 2 ends Docling and embeds the batch with BGE-M3 loaded once.
_QUEUE: Optional[asyncio.Queue] = None
_WORKER: Optional[asyncio.Task] = None


async def _drain() -> None:
    while _QUEUE is not None and not _QUEUE.empty():
        batch: List[_Job] = []
        session = DoclingSession(settings.ARTIFACTS_STORAGE_DIR / "docling_session.log") if settings.PARSER_ENGINE == "docling" else None
        if session is not None:  # Docling needs the whole card: the resident models go (they reload once in phase 2)
            DenseEmbeddingService.unload()
            QwenRerankerService.unload()
        try:
            while not _QUEUE.empty():
                job = _QUEUE.get_nowait()
                if await job.pipeline._prepare(job, session):
                    batch.append(job)
        finally:
            if session is not None:
                await asyncio.to_thread(session.close)
        for job in batch:
            await job.pipeline._index(job)
        logger.info(f"Ingestion batch of {len(batch)} file(s) done.")
    await warm_models()  # the next question should not pay the model load


class IngestionPipeline:
    """End-to-end ingestion: parse (Docling + postprocess) -> chunk (st1024) -> BGE-M3 embeddings -> MongoDB + Qdrant, in batches
    (see _drain), with the seconds of every stage on the job record."""

    @staticmethod
    async def fail_interrupted(db: AsyncIOMotorDatabase) -> int:
        """Ingestion runs inside the API process, so a restart kills it mid-way. Mark such documents/jobs failed at
        startup instead of leaving them 'processing' forever (the UI would poll them for ever)."""
        unfinished = {"status": {"$nin": ["completed", "failed"]}}
        jobs = db[collections.INGESTION_JOBS_COLLECTION]
        stuck = [j["document_id"] async for j in jobs.find(unfinished, {"document_id": 1})]
        if stuck:
            await jobs.update_many(unfinished, {"$set": {"status": "failed", "error_log": "Interrupted by a server restart."}})
            await db[collections.DOCUMENTS_COLLECTION].update_many(
                {"document_id": {"$in": stuck}},
                {"$set": {"parsing_status": "failed", "indexing_status": "failed",
                          "error_message": "Quá trình xử lý bị gián đoạn do máy chủ khởi động lại. Vui lòng tải lên lại."}},
            )
        return len(stuck)

    def __init__(self, db: AsyncIOMotorDatabase, qdrant: AsyncQdrantClient):
        self.db = db
        self.qdrant = qdrant
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = ChunkRepository(db)
        self.job_repo = IngestionJobRepository(db)
        self.dense_service = DenseEmbeddingService()

    async def run(self, job_id: str, document_id: str, notebook_id: str, pdf_path: Path) -> None:
        """Queue the document for the batch worker (see _drain) and return."""
        global _QUEUE, _WORKER
        if _QUEUE is None:
            _QUEUE = asyncio.Queue()
        await _QUEUE.put(_Job(self, job_id, document_id, notebook_id, pdf_path))
        if _WORKER is None or _WORKER.done():
            _WORKER = asyncio.create_task(_drain())

    async def _fail(self, job: _Job, exc: Exception) -> None:
        if not await self._document_is_active(job.document_id):
            # The user deleted this source while a parser/embedding task was running.
            # The delete endpoint already removed its persisted state.
            return
        logger.error(f"Ingestion job {job.job_id} failed: {exc!r}", exc_info=True)
        if job.catalog is not None and not job.catalog.done():
            job.catalog.cancel()
        await self._cleanup(job.document_id)
        await self.job_repo.update_progress(job.job_id, "failed", 0, error_log=repr(exc)[:1000])
        await self.doc_repo.update_status(job.document_id, "failed", "failed")
        reason = str(exc) if isinstance(exc, (ValueError, IngestionError)) else "Hệ thống gặp lỗi khi xử lý tài liệu."
        await self.doc_repo.update_one({"document_id": job.document_id}, {"error_message": reason[:500]})

    async def _document_is_active(self, document_id: str) -> bool:
        document = await self.doc_repo.get_by_id(document_id)
        return bool(document and document.parsing_status != "deleting" and document.indexing_status != "deleting")

    async def _stop_if_deleted(self, job: _Job) -> bool:
        """Stop a queued/running ingestion before it can recreate deleted data."""
        if await self._document_is_active(job.document_id):
            return False
        if job.catalog is not None and not job.catalog.done():
            job.catalog.cancel()
        return True

    async def _prepare(self, job: _Job, session: Optional[DoclingSession]) -> bool:
        """Phase 1: parse (the batch's Docling worker), start the catalog call, chunk. False when the document failed."""
        try:
            if await self._stop_if_deleted(job):
                return False
            job.timings["queue_wait"] = round(time.perf_counter() - job.queued, 2)
            # 0. Fail in seconds, not after minutes of parsing, if the vector store is unreachable or lacks the collection.
            if not await self.qdrant.collection_exists(settings.QDRANT_COLLECTION_NAME):
                await QdrantManager.ensure_collection()
                if not await self.qdrant.collection_exists(settings.QDRANT_COLLECTION_NAME):
                    raise IngestionError("Kho vector chưa sẵn sàng.")
            # 1. Parsing
            await self.job_repo.update_progress(job.job_id, "parsing", 20)
            t0, info = time.perf_counter(), {}
            job.pages, job.engine = await PDFParserService.extract_pages(job.pdf_path, job.document_id, session, info)
            if await self._stop_if_deleted(job):
                return False
            job.timings["parse"] = round(time.perf_counter() - t0, 2)
            job.timings.update({f"docling_{k}": v for k, v in info.items()})  # start_s (model load, first file only), convert_s, postprocess_s
            await self.job_repo.update_one({"job_id": job.job_id}, {"total_pages": len(job.pages), "processed_pages": len(job.pages)})
            # 1b. Catalog: the API call runs while the next file parses
            job.catalog = asyncio.create_task(self._catalog(job))
            # 2. Chunking (CPU-bound: tokenizer)
            await self.job_repo.update_progress(job.job_id, "chunking", 40)
            t0 = time.perf_counter()
            job.chunks = await asyncio.to_thread(FinancialChunkerService.chunk_document, job.notebook_id, job.document_id, job.pages)
            if await self._stop_if_deleted(job):
                return False
            job.timings["chunk"] = round(time.perf_counter() - t0, 2)
            if not job.chunks:
                raise ValueError("Không trích xuất được nội dung văn bản từ tài liệu (có thể là bản scan).")
            return True
        except Exception as exc:
            await self._fail(job, exc)
            return False

    async def _catalog(self, job: _Job) -> None:
        """Catalog line (company, aliases, document type, period, years with figures), read from the text: the multi-document
        planner, the routing and the period rules tell documents apart by it. CATALOG_BACKEND first (catalog.py); when it is missing
        or its name / period is unverified, the image fallback; without either the rule header (SEC covers). Best effort: a document
        whose catalog cannot be read still works (the catalog form asks the user)."""
        t0 = time.perf_counter()
        pages = job.pages
        try:
            header = await read_catalog(pages)
            if needs_vlm(header):
                vlm = await read_catalog_vlm(job.pdf_path, pages)
                if vlm is not None and (header is None or len(vlm["catalog_unverified"]) < len(header["catalog_unverified"])
                                        or (not header.get("company_name") and vlm.get("company_name"))):
                    header = vlm
            if header is None:
                header = {k: v for k, v in (await asyncio.to_thread(extract_document_header, pages)).items() if k != "header"}
                header.update(years_covered=years_covered({int(p["page_number"]): p.get("text") or "" for p in pages}, header.get("period_end") or ""),
                              catalog_source="rule")
            header["name_candidates"] = await asyncio.to_thread(company_candidates, pages)  # the choices of the catalog form
            await self.doc_repo.update_one({"document_id": job.document_id}, {f"metadata.{k}": v for k, v in header.items()})
        except Exception as exc:
            logger.warning(f"Document catalog not extracted for {job.document_id}: {type(exc).__name__}: {str(exc)[:120]}")
        job.timings["catalog"] = round(time.perf_counter() - t0, 2)

    async def _index(self, job: _Job) -> None:
        """Phase 2: embeddings (BGE-M3 loaded once for the batch), MongoDB + Qdrant, completion."""
        try:
            if await self._stop_if_deleted(job):
                return
            chunks, document_id, job_id = job.chunks, job.document_id, job.job_id
            t0 = time.perf_counter()
            if job.catalog is not None:
                await job.catalog
            if await self._stop_if_deleted(job):
                return
            job.timings["catalog_wait"] = round(time.perf_counter() - t0, 2)
            # 3. Embeddings (all before any write, so a failure leaves nothing half-indexed)
            await self.job_repo.update_progress(job_id, "indexing_qdrant", 60)
            if DenseEmbeddingService._model is None:
                t0 = time.perf_counter()
                await run_on_gpu("embedder", DenseEmbeddingService._get_model)
                job.timings["embed_load"] = round(time.perf_counter() - t0, 2)
            t0 = time.perf_counter()
            vectors, sparse = await self.dense_service.embed_documents_with_sparse([c.content for c in chunks])
            if await self._stop_if_deleted(job):
                return
            job.timings["embed"] = round(time.perf_counter() - t0, 2)
            for chunk, weights in zip(chunks, sparse):
                chunk.sparse_weights = weights
            for chunk in chunks:  # indirect prompt injection: kept as content, flagged for the trace and the answer prompt
                if instruction_like(chunk.content):
                    chunk.flags = ["suspicious_instruction"]
            # 4. Persist: MongoDB is the source of truth for text, Qdrant only holds vectors + filters
            t0 = time.perf_counter()
            await self.chunk_repo.save_chunks(chunks)
            if await self._stop_if_deleted(job):
                await self._cleanup(document_id)
                return
            await self.job_repo.update_progress(job_id, "indexing_qdrant", 85)
            points = [
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, c.chunk_id)),
                    vector=vec,
                    payload={
                        "chunk_id": c.chunk_id,
                        "notebook_id": c.notebook_id,
                        "document_id": c.document_id,
                        "page": c.page,
                        "chunk_type": c.chunk_type,
                        "text_type": c.text_type,
                        "concept_ids": c.concept_ids,
                    },
                )
                for c, vec in zip(chunks, vectors)
            ]
            for start in range(0, len(points), UPSERT_BATCH):
                if await self._stop_if_deleted(job):
                    await self._cleanup(document_id)
                    return
                await self.qdrant.upsert(
                    collection_name=settings.QDRANT_COLLECTION_NAME, points=points[start:start + UPSERT_BATCH], wait=True
                )
            if await self._stop_if_deleted(job):
                await self._cleanup(document_id)
                return
            job.timings["persist"] = round(time.perf_counter() - t0, 2)
            job.timings["total"] = round(time.perf_counter() - job.queued, 2)
            # 5. Complete
            await self.doc_repo.update_one(
                {"document_id": document_id},
                {"page_count": len(job.pages), "parsing_engine": job.engine, "updated_at": datetime.now(timezone.utc)},
            )
            await self.job_repo.update_one(
                {"job_id": job_id},
                {"extracted_chunks_count": len(chunks), "completed_at": datetime.now(timezone.utc), "timings": job.timings},
            )
            await self.job_repo.update_progress(job_id, "completed", 100)
            await self.doc_repo.update_status(document_id, "completed", "completed")
            logger.info(f"Ingestion job {job_id}: {len(job.pages)} pages, {len(chunks)} chunks, engine={job.engine}, timings={job.timings}")
        except Exception as exc:
            await self._fail(job, exc)

    async def _cleanup(self, document_id: str) -> None:
        """Remove whatever a failed run already wrote so a retry starts clean."""
        try:
            await self.db[collections.CHUNKS_COLLECTION].delete_many({"document_id": document_id})
            await self.qdrant.delete(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points_selector=models.FilterSelector(
                    filter=models.Filter(must=[models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=document_id))])
                ),
            )
        except Exception as exc:
            logger.warning(f"Cleanup after failed ingestion of {document_id} was incomplete: {exc}")
