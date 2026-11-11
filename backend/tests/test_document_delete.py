"""Deletion of a source must be authorized and remove every derived record."""
import pytest
from fastapi import HTTPException

from app.shared import deps
from app.modules.documents import documents as documents_api
from app.modules.documents.document import DocumentRecord
from app.modules.notebooks import purge
from app.modules.notebooks.notebook import NotebookRecord


GUEST_NOTEBOOK = "nb_guest_" + "d" * 32


def _document(notebook_id: str) -> DocumentRecord:
    return DocumentRecord(
        document_id="doc_delete",
        notebook_id=notebook_id,
        file_name="report.pdf",
        file_size_bytes=42,
        file_path="storage/pdfs/unused/report.pdf",
        status="ready",
    )


def _setup(monkeypatch, notebook: NotebookRecord, caller: str | None):
    state = {"document": _document(notebook.notebook_id), "caller": caller, "chunks": [], "jobs": [], "files": []}

    class Notebooks:
        def __init__(self, db):
            pass

        async def get_by_id(self, notebook_id):
            return notebook if notebook_id == notebook.notebook_id else None

    class Documents:
        def __init__(self, db):
            pass

        async def get_by_id(self, document_id):
            document = state["document"]
            return document if document and document_id == document.document_id else None

        async def update_one(self, _query, _changes):
            return True

        async def delete_document(self, document_id):
            if state["document"] and state["document"].document_id == document_id:
                state["document"] = None
                return True
            return False

    class Chunks:
        def __init__(self, db):
            pass

        async def delete_by_document(self, document_id):
            state["chunks"].append(document_id)
            return 3

    class Jobs:
        def __init__(self, db):
            pass

        async def delete_by_document(self, document_id):
            state["jobs"].append(document_id)
            return 1

    class Storage:
        async def delete_document_files(self, notebook_id, document_id, file_path):
            state["files"].append((notebook_id, document_id, file_path))

    class Qdrant:
        async def collection_exists(self, _collection):
            return True

        async def delete(self, **kwargs):
            state["vector_delete"] = kwargs

    monkeypatch.setattr(deps, "NotebookRepository", Notebooks)
    monkeypatch.setattr(documents_api, "DocumentRepository", Documents)
    monkeypatch.setattr(purge, "DocumentRepository", Documents)
    monkeypatch.setattr(purge, "ChunkRepository", Chunks)
    monkeypatch.setattr(purge, "IngestionJobRepository", Jobs)
    monkeypatch.setattr(purge, "StorageService", Storage)

    return state, Qdrant()


async def test_owner_deletes_document_file_chunks_job_and_vectors(monkeypatch):
    notebook = NotebookRecord(notebook_id="nb_alice", owner_id="alice", title="Alice")
    state, qdrant = _setup(monkeypatch, notebook, "alice")

    response = await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=qdrant)

    assert response["document_id"] == "doc_delete"
    assert state["document"] is None
    assert state["files"] == [("nb_alice", "doc_delete", "storage/pdfs/unused/report.pdf")]
    assert state["chunks"] == ["doc_delete"] and state["jobs"] == ["doc_delete"]
    assert state["vector_delete"]["wait"] is True


async def test_the_pdf_response_accepts_vietnamese_names_and_can_be_cached(monkeypatch, tmp_path):
    notebook = NotebookRecord(notebook_id="nb_alice", owner_id="alice", title="Alice")
    state, _ = _setup(monkeypatch, notebook, "alice")
    state["document"].file_name = "Báo cáo tổng hợp quý 3.pdf"
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    class Storage:
        def get_pdf_path(self, *_):
            return pdf

    monkeypatch.setattr(documents_api, "StorageService", Storage)

    response = await documents_api.get_document_file("doc_delete", db=None, user_id="alice")

    assert response.headers["content-disposition"].startswith("inline; filename*=utf-8''")
    assert "max-age" in response.headers["cache-control"]
    assert response.headers["vary"] == "Authorization"  # the address is the same for everyone: a signed-out browser must not reopen it from its cache


async def test_guest_deletes_its_own_document(monkeypatch):
    notebook = NotebookRecord(notebook_id=GUEST_NOTEBOOK, owner_type="guest", owner_id="g", title="Khách")
    state, qdrant = _setup(monkeypatch, notebook, None)

    await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=qdrant)
    assert state["document"] is None


@pytest.mark.parametrize("status", ["pending", "processing"])
async def test_a_document_being_processed_cannot_be_deleted(monkeypatch, status):
    notebook = NotebookRecord(notebook_id="nb_alice", owner_id="alice", title="Alice")
    state, qdrant = _setup(monkeypatch, notebook, "alice")
    state["document"].status = status

    with pytest.raises(HTTPException) as exc:
        await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=qdrant)
    assert exc.value.status_code == 409
    assert state["document"] is not None and state["files"] == [] and state["chunks"] == []


async def test_a_failed_document_can_be_deleted(monkeypatch):
    notebook = NotebookRecord(notebook_id="nb_alice", owner_id="alice", title="Alice")
    state, qdrant = _setup(monkeypatch, notebook, "alice")
    state["document"].status = "failed"

    await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=qdrant)
    assert state["document"] is None


async def test_a_missing_collection_skips_the_vector_delete_but_removes_the_rest(monkeypatch):
    notebook = NotebookRecord(notebook_id="nb_alice", owner_id="alice", title="Alice")
    state, _ = _setup(monkeypatch, notebook, "alice")

    class NoCollection:
        async def collection_exists(self, _collection):
            return False

        async def delete(self, **kwargs):
            raise AssertionError("no collection: nothing to delete")

    await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=NoCollection())
    assert state["document"] is None and state["chunks"] == ["doc_delete"]


async def test_a_failed_ingestion_removes_the_chunks_and_vectors_it_wrote():
    """The failure path deletes vectors the same way a document deletion does: waiting until Qdrant has removed them."""
    from pathlib import Path
    from unittest.mock import AsyncMock

    from app.modules.ingestion.pipeline import IngestionPipeline, _Job

    calls = {}

    class Chunks:
        async def delete_by_document(self, document_id):
            calls["chunks"] = document_id

    class Qdrant:
        async def collection_exists(self, _collection):
            return True

        async def delete(self, **kwargs):
            calls["vectors"] = kwargs

    class Pipeline(IngestionPipeline):
        def __init__(self):
            self.doc_repo, self.job_repo, self.chunk_repo, self.qdrant = AsyncMock(), AsyncMock(), Chunks(), Qdrant()

    pipeline = Pipeline()
    await pipeline._fail(_Job(pipeline, "job_x", "doc_x", "nb_alice", Path("x.pdf")), ValueError("parse failed"))

    assert calls["chunks"] == "doc_x"
    assert calls["vectors"]["wait"] is True
    assert calls["vectors"]["points_selector"].filter.must[0].match.value == "doc_x"
    pipeline.job_repo.fail.assert_awaited_once()
    assert pipeline.doc_repo.update_one.await_args.args[1]["status"] == "failed"


async def test_other_user_cannot_delete_someone_elses_document(monkeypatch):
    notebook = NotebookRecord(notebook_id="nb_alice", owner_id="alice", title="Alice")
    state, qdrant = _setup(monkeypatch, notebook, "bob")

    with pytest.raises(HTTPException) as exc:
        await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=qdrant)
    assert exc.value.status_code == 403
    assert state["document"] is not None
    assert state["files"] == [] and state["chunks"] == [] and state["jobs"] == []
