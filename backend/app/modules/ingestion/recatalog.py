"""Catalogs read by the rule fallback, read again by the model (O2-b, docs/VERSION_4/ADMIN_INGESTION_PLAN_2026-11-26.md 2).

When the catalog model cannot be reached at upload, pipeline._catalog keeps the rule header (doc_header.py, catalog_source "rule"): it knows SEC forms
and once named non-SEC statements "earnings release". The housekeeping round asks the model again for a few such documents, from the page text kept
in their chunks (the parsed pages are not stored). A document the owner confirmed or edited is never touched, and nothing changes while the model
is still down or reads no company name."""
from typing import Any, Dict, List

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.database import collections
from app.modules.ingestion.catalog import read_catalog

PER_ROUND = 5  # documents a housekeeping round reads again (one model call each)


def pages_from_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[{"page_number", "text"}] in page order, each page's chunks in their document order."""
    by_page: Dict[int, List[str]] = {}
    for c in sorted(chunks, key=lambda c: c.get("chunk_index", 0)):
        by_page.setdefault(int(c["page"]), []).append(c.get("content") or "")
    return [{"page_number": p, "text": "\n\n".join(parts)} for p, parts in sorted(by_page.items())]


async def recatalog_rule_documents(db) -> int:
    """Read again up to PER_ROUND rule catalogs; the number replaced."""
    if not settings.CATALOG_ENABLED:
        return 0
    docs = await db[collections.DOCUMENTS_COLLECTION].find(
        {"status": "ready", "metadata.catalog_source": "rule", "metadata.catalog_confirmed": {"$ne": True}}, {"document_id": 1}
    ).sort("created_at", 1).limit(PER_ROUND).to_list(PER_ROUND)
    done = 0
    for doc in docs:
        chunks = await db[collections.CHUNKS_COLLECTION].find({"document_id": doc["document_id"]}, {"page": 1, "chunk_index": 1, "content": 1}).to_list(None)
        header = await read_catalog(pages_from_chunks(chunks))
        if header is None:  # the model is still down: try again next round
            break
        if not header.get("company_name"):
            continue
        await db[collections.DOCUMENTS_COLLECTION].update_one(
            {"document_id": doc["document_id"], "metadata.catalog_source": "rule"},  # the owner may have edited it while the model read
            {f"metadata.{k}": v for k, v in header.items()},
        )
        done += 1
        logger.info(f"Catalog of {doc['document_id']} read again by the model (was the rule fallback)")
    return done
