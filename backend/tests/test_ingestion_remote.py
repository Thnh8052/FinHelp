"""Bug #7: with a remote GPU a file is indexed as soon as it is parsed, whatever the other queued files are doing."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.modules.ingestion import pipeline as ingestion
from app.modules.ingestion.pipeline import IngestionPipeline, _Job
from app.modules.retrieval import warmup
from app.modules.retrieval.embeddings import REMOTE_DOCUMENT_BATCH, DenseEmbeddingService
from app.modules.retrieval.reranker import QwenRerankerService


def test_an_unreachable_remote_reranker_is_a_runtime_error(monkeypatch):
    """RuntimeError is what every reranker caller already answers from the search order (the user never sees the failure)."""
    monkeypatch.setattr(settings, "REMOTE_GPU_URL", "http://gpu")

    class Down:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "AsyncClient", Down)
    with pytest.raises(RuntimeError):
        asyncio.run(QwenRerankerService().score_pairs([("question", "passage")]))


def _prepared_pipeline(monkeypatch, events):
    monkeypatch.setattr(ingestion.FinancialChunkerService, "chunk_document", staticmethod(lambda *a: ["chunk"]))

    async def extract(pdf_path, document_id, session, info):
        events.append("parse")
        return [{"page_number": 1, "text": "x"}], "docling"

    monkeypatch.setattr(ingestion.PDFParserService, "extract_pages", extract)

    async def status(document_id, value):
        events.append(value)

    class Pipeline(IngestionPipeline):
        def __init__(self):
            self.doc_repo, self.job_repo, self.qdrant = AsyncMock(), AsyncMock(), AsyncMock()
            self.doc_repo.update_status = status

        async def _catalog(self, job):
            pass

    pipeline = Pipeline()
    return pipeline, _Job(pipeline, "job", "doc", "notebook", Path("file.pdf"))


def test_a_remote_file_stays_pending_until_it_has_a_slot(monkeypatch):
    monkeypatch.setattr(settings, "REMOTE_GPU_URL", "http://gpu")
    events = []

    async def scenario():
        slots = asyncio.Semaphore(0)
        monkeypatch.setattr(ingestion, "_REMOTE_SLOTS", slots)
        pipeline, job = _prepared_pipeline(monkeypatch, events)
        task = asyncio.create_task(pipeline._prepare(job, None))
        await asyncio.sleep(0.05)
        waiting = list(events)
        slots.release()
        await asyncio.wait_for(task, timeout=2)
        return waiting

    assert asyncio.run(scenario()) == []
    assert events == ["processing", "parse"]


def test_a_local_file_is_marked_processing_before_its_parse(monkeypatch):
    monkeypatch.setattr(settings, "REMOTE_GPU_URL", None)
    events = []
    pipeline, job = _prepared_pipeline(monkeypatch, events)
    assert asyncio.run(pipeline._prepare(job, None)) is True
    assert events == ["processing", "parse"]


def test_remote_file_is_indexed_without_waiting_for_a_slower_file(monkeypatch):
    monkeypatch.setattr(settings, "REMOTE_GPU_URL", "http://gpu")
    monkeypatch.setattr(ingestion, "warm_models", lambda: asyncio.sleep(0))

    async def scenario():
        events, fast_indexed = [], asyncio.Event()

        class Pipeline(IngestionPipeline):
            def __init__(self):
                pass

            async def _prepare(self, job, session):
                if job.document_id == "slow":
                    await fast_indexed.wait()  # still parsing until the other file is fully done
                events.append(f"parsed {job.document_id}")
                return True

            async def _index(self, job):
                events.append(f"indexed {job.document_id}")
                if job.document_id == "fast":
                    fast_indexed.set()

        pipeline = Pipeline()
        await pipeline.run("job-1", "slow", "notebook", Path("slow.pdf"))
        await pipeline.run("job-2", "fast", "notebook", Path("fast.pdf"))

        async def all_done():
            while len(events) < 4:
                await asyncio.sleep(0.01)

        await asyncio.wait_for(all_done(), timeout=2)
        return events

    assert asyncio.run(scenario()) == ["parsed fast", "indexed fast", "parsed slow", "indexed slow"]


def test_remote_slot_is_held_for_the_parse_only(monkeypatch):
    """The next file parses while the previous one is still embedding: the Docling GPU never idles behind a held slot."""
    monkeypatch.setattr(settings, "REMOTE_GPU_URL", "http://gpu")
    monkeypatch.setattr(ingestion, "warm_models", lambda: asyncio.sleep(0))
    monkeypatch.setattr(ingestion.FinancialChunkerService, "chunk_document", staticmethod(lambda *a: ["chunk"]))

    async def scenario():
        monkeypatch.setattr(ingestion, "_REMOTE_SLOTS", asyncio.Semaphore(1))
        second_parsing, indexed = asyncio.Event(), []

        async def extract(pdf_path, document_id, session, info):
            if document_id == "second":
                second_parsing.set()
            return [{"page_number": 1, "text": "x"}], "docling"

        monkeypatch.setattr(ingestion.PDFParserService, "extract_pages", extract)

        class Pipeline(IngestionPipeline):
            def __init__(self):
                self.doc_repo, self.job_repo, self.qdrant = AsyncMock(), AsyncMock(), AsyncMock()

            async def _catalog(self, job):
                pass

            async def _index(self, job):
                if job.document_id == "first":
                    await second_parsing.wait()  # still embedding until the next file has started its parse
                indexed.append(job.document_id)

        pipeline = Pipeline()
        await pipeline.run("job-1", "first", "notebook", Path("first.pdf"))
        await pipeline.run("job-2", "second", "notebook", Path("second.pdf"))

        async def all_done():
            while len(indexed) < 2:
                await asyncio.sleep(0.01)

        await asyncio.wait_for(all_done(), timeout=2)
        return indexed

    assert sorted(asyncio.run(scenario())) == ["first", "second"]  # with the slot held for the whole file this times out


def test_remote_documents_are_embedded_in_small_batches(monkeypatch):
    monkeypatch.setattr(settings, "REMOTE_GPU_URL", "http://gpu")
    encode = AsyncMock(return_value=([[0.0]], [{}]))
    monkeypatch.setattr(DenseEmbeddingService, "_encode_remote", encode)

    asyncio.run(DenseEmbeddingService().embed_documents_with_sparse(["text"]))

    assert encode.call_args.args[2] == REMOTE_DOCUMENT_BATCH == 16


def test_chunk_tokenizer_is_loaded_at_startup_with_a_remote_gpu_only(monkeypatch):
    loaded = []
    monkeypatch.setattr(warmup, "bge_m3_token_counter", lambda: loaded.append(1))

    monkeypatch.setattr(settings, "REMOTE_GPU_URL", None)
    asyncio.run(warmup.warm_chunk_tokenizer())
    assert loaded == []

    monkeypatch.setattr(settings, "REMOTE_GPU_URL", "http://gpu")
    asyncio.run(warmup.warm_chunk_tokenizer())
    assert loaded == [1]
