"""The notebook list of the Hub page and the rules of renaming (no database: repositories are faked)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.infrastructure.database.mongodb import get_database
from app.modules.notebooks import notebooks as notebooks_api
from app.modules.notebooks.notebook import NotebookRecord
from app.shared.deps import get_current_user_id

OWNED = NotebookRecord(notebook_id="nb_a", owner_id="alice", title="A")
OTHER = NotebookRecord(notebook_id="nb_b", owner_id="bob", title="B")


@pytest.fixture
def client(monkeypatch):
    renamed = []

    class Notebooks:
        def __init__(self, db):
            pass

        async def get_by_owner(self, owner_id):
            return [n for n in (OWNED, OTHER) if n.owner_id == owner_id]

        async def get_by_id(self, notebook_id):
            return {n.notebook_id: n for n in (OWNED, OTHER)}.get(notebook_id)

        async def rename(self, notebook_id, title):
            renamed.append((notebook_id, title))
            return True

    class Documents:
        def __init__(self, db):
            pass

        async def counts_by_notebook(self, ids):
            return {"nb_a": {"document_count": 3, "processing_count": 1}}

    monkeypatch.setattr(notebooks_api, "NotebookRepository", Notebooks)
    monkeypatch.setattr(notebooks_api, "DocumentRepository", Documents)
    app = FastAPI()
    app.include_router(notebooks_api.router)
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_current_user_id] = lambda: "alice"
    c = TestClient(app)
    c.renamed = renamed
    return c


def test_the_list_carries_the_counts_of_each_notebook(client):
    assert [(n["notebook_id"], n["document_count"], n["processing_count"]) for n in client.get("/notebooks").json()] == [("nb_a", 3, 1)]


def test_a_title_is_trimmed_before_saving(client):
    assert client.put("/notebooks/nb_a", json={"title": "  VNM 2023  "}).status_code == 200
    assert client.renamed == [("nb_a", "VNM 2023")]


@pytest.mark.parametrize("title", ["", "   ", "x" * 121])
def test_an_empty_or_overlong_title_is_refused(client, title):
    assert client.put("/notebooks/nb_a", json={"title": title}).status_code == 422
    assert client.renamed == []


def test_someone_elses_notebook_cannot_be_renamed(client):
    assert client.put("/notebooks/nb_b", json={"title": "mine"}).status_code == 404
