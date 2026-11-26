"""O2-b (docs/VERSION_4/ADMIN_INGESTION_PLAN_2026-11-26.md 2): a document uploaded while the catalog model was down keeps the rule fallback's catalog
(catalog_source "rule"), which named a non-SEC statement an "earnings release". Housekeeping reads its catalog again with the model once the model
answers, from the page text kept in its chunks. Never a document the owner confirmed or edited. Fakes: no database, no model."""
from app.modules.ingestion import recatalog

RULE_DOC = {"document_id": "d1", "status": "ready", "metadata": {"catalog_source": "rule", "report_type": "earnings release", "company_name": "Enablence"}}


class Collection:
    def __init__(self, rows):
        self.rows, self.updates, self.queries = rows, [], []

    def find(self, query, projection=None):
        self.queries.append(query)
        rows = self.rows

        class Cursor:
            def sort(self, *a):
                return self

            def limit(self, n):
                return self

            async def to_list(self, n):
                return rows
        return Cursor()

    async def update_one(self, query, update):
        self.updates.append((query, update))


def db(docs, chunks):
    return {"documents": Collection(docs), "chunks": Collection(chunks)}


CHUNKS = [{"document_id": "d1", "page": 1, "chunk_index": 0, "content": "ENABLENCE TECHNOLOGIES INC.\nConsolidated Financial Statements"},
          {"document_id": "d1", "page": 2, "chunk_index": 1, "content": "Independent auditor's report"},
          {"document_id": "d1", "page": 1, "chunk_index": 2, "content": "For the years ended June 30, 2026 and 2025"}]


async def test_a_rule_catalog_is_read_again_by_the_model_from_the_chunks(monkeypatch):
    seen = {}

    async def model(pages):
        seen["pages"] = pages
        return {"company_name": "Enablence Technologies Inc.", "report_type": "annual financial statements", "fiscal_year": 2026,
                "catalog_source": "api", "catalog_unverified": []}

    monkeypatch.setattr(recatalog, "read_catalog", model)
    d = db([RULE_DOC], CHUNKS)
    assert await recatalog.recatalog_rule_documents(d) == 1
    assert seen["pages"] == [{"page_number": 1, "text": "ENABLENCE TECHNOLOGIES INC.\nConsolidated Financial Statements\n\nFor the years ended June 30, 2026 and 2025"},
                             {"page_number": 2, "text": "Independent auditor's report"}]
    query, update = d["documents"].updates[0]
    assert query == {"document_id": "d1", "metadata.catalog_source": "rule"}  # not if the owner edited it meanwhile
    assert update["metadata.report_type"] == "annual financial statements" and update["metadata.catalog_source"] == "api"
    q = d["documents"].queries[0]
    assert q["metadata.catalog_source"] == "rule" and q["metadata.catalog_confirmed"] == {"$ne": True} and q["status"] == "ready"


async def test_nothing_changes_while_the_model_is_still_down_or_reads_no_company(monkeypatch):
    async def down(pages):
        return None

    monkeypatch.setattr(recatalog, "read_catalog", down)
    d = db([RULE_DOC], CHUNKS)
    assert await recatalog.recatalog_rule_documents(d) == 0 and d["documents"].updates == []

    async def nameless(pages):
        return {"company_name": None, "report_type": "other", "catalog_source": "api", "catalog_unverified": ["entity"]}

    monkeypatch.setattr(recatalog, "read_catalog", nameless)
    assert await recatalog.recatalog_rule_documents(d) == 0 and d["documents"].updates == []


async def test_off_when_the_catalog_model_is_turned_off(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "CATALOG_ENABLED", False)
    d = db([RULE_DOC], CHUNKS)
    assert await recatalog.recatalog_rule_documents(d) == 0 and d["documents"].queries == []
