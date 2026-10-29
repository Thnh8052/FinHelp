"""Deletion of a source must be authorized and remove every derived record."""
import pytest
from fastapi import HTTPException

from app.api.v1 import deps, documents as documents_api
from app.models.document import DocumentRecord
from app.models.notebook import NotebookRecord


GUEST_NOTEBOOK = "nb_guest_" + "d" * 32


def _document(notebook_id: str) -> DocumentRecord:
    return DocumentRecord(
        document_id="doc_delete",
        notebook_id=notebook_id,
        file_name="report.pdf",
        file_size_bytes=42,
        file_path="storage/pdfs/unused/report.pdf",
        parsing_status="completed",
        indexing_status="completed",
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
    monkeypatch.setattr(documents_api, "ChunkRepository", Chunks)
    monkeypatch.setattr(documents_api, "IngestionJobRepository", Jobs)
    monkeypatch.setattr(documents_api, "StorageService", Storage)

    return state, Qdrant()


async def test_owner_deletes_document_file_chunks_job_and_vectors(monkeypatch):
    notebook = NotebookRecord(notebook_id="nb_alice", user_id="alice", title="Alice")
    state, qdrant = _setup(monkeypatch, notebook, "alice")

    response = await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=qdrant)

    assert response["document_id"] == "doc_delete"
    assert state["document"] is None
    assert state["files"] == [("nb_alice", "doc_delete", "storage/pdfs/unused/report.pdf")]
    assert state["chunks"] == ["doc_delete"] and state["jobs"] == ["doc_delete"]
    assert state["vector_delete"]["wait"] is True


async def test_guest_deletes_its_own_document(monkeypatch):
    notebook = NotebookRecord(notebook_id=GUEST_NOTEBOOK, user_id="guest", title="Khách")
    state, qdrant = _setup(monkeypatch, notebook, None)

    await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=qdrant)
    assert state["document"] is None


async def test_other_user_cannot_delete_someone_elses_document(monkeypatch):
    notebook = NotebookRecord(notebook_id="nb_alice", user_id="alice", title="Alice")
    state, qdrant = _setup(monkeypatch, notebook, "bob")

    with pytest.raises(HTTPException) as exc:
        await documents_api.delete_document("doc_delete", user_id=state["caller"], db=None, qdrant=qdrant)
    assert exc.value.status_code == 403
    assert state["document"] is not None
    assert state["files"] == [] and state["chunks"] == [] and state["jobs"] == []
