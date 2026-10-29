"""One-off backfill for documents indexed before 2026-10-27, so they need no re-upload:
  - chunks without `sparse_weights` get BGE-M3 lexical weights from their stored text (dense vectors in Qdrant stay as they are);
  - documents without `metadata.catalog_source` get the catalog (local model, then the paid image fallback when the PDF is still on
    disk and the name / period is unverified, else the rule header), read from their stored chunks rebuilt into pages.
Without --apply it only counts what it would change.
  cd experiments/multidoc_planner/backend && <backend python> scripts/backfill_sparse_catalog.py [--apply]
"""
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db import collections  # noqa: E402
from app.services.ingestion.catalog import needs_vlm, read_catalog, read_catalog_vlm, years_covered  # noqa: E402
from app.services.ingestion.doc_header import extract_document_header  # noqa: E402
from app.services.retrieval.embeddings import DenseEmbeddingService  # noqa: E402


async def catalog_for(doc: dict, pages: list) -> dict:
    header = await read_catalog(pages)
    pdf = Path(doc.get("file_path") or "")
    if needs_vlm(header) and pdf.is_file():
        vlm = await read_catalog_vlm(pdf, pages)
        if vlm is not None and (header is None or len(vlm["catalog_unverified"]) < len(header["catalog_unverified"])):
            header = vlm
    if header is None:
        header = {k: v for k, v in extract_document_header(pages).items() if k != "header"}
        header.update(years_covered=years_covered({p["page_number"]: p["text"] for p in pages}, header.get("period_end") or ""),
                      catalog_source="rule")
    return header


async def main(apply: bool) -> None:
    db = AsyncIOMotorClient(settings.MONGODB_URI)[settings.MONGODB_DB_NAME]
    chunks_col, docs_col = db[collections.CHUNKS_COLLECTION], db[collections.DOCUMENTS_COLLECTION]
    no_sparse = defaultdict(list)
    async for c in chunks_col.find({"$or": [{"sparse_weights": {"$exists": False}}, {"sparse_weights": {}}]}, {"chunk_id": 1, "document_id": 1, "content": 1, "_id": 0}):
        no_sparse[c["document_id"]].append(c)
    no_catalog = [d async for d in docs_col.find({"metadata.catalog_source": {"$exists": False}}, {"_id": 0})]
    print(f"chunks without sparse weights: {sum(map(len, no_sparse.values()))} in {len(no_sparse)} documents; documents without catalog: {len(no_catalog)}")
    if not apply:
        print("dry run: add --apply to write")
        return
    for doc in no_catalog:  # catalog first: it releases the in-process models and borrows the GPU for Ollama
        by_page = defaultdict(list)
        async for c in chunks_col.find({"document_id": doc["document_id"]}, {"page": 1, "chunk_id": 1, "content": 1, "_id": 0}).sort([("page", 1), ("chunk_id", 1)]):
            by_page[c["page"]].append(c["content"])
        pages = [{"page_number": p, "text": "\n\n".join(t)} for p, t in sorted(by_page.items())]
        header = await catalog_for(doc, pages)
        await docs_col.update_one({"document_id": doc["document_id"]}, {"$set": {f"metadata.{k}": v for k, v in header.items()}})
        print(f"catalog {doc['document_id']} ({doc.get('file_name')}): {header.get('company_name')} | {header.get('report_type')} | "
              f"FY{header.get('fiscal_year')} | {header['catalog_source']} | unverified {header.get('catalog_unverified', [])}")
    embedder = DenseEmbeddingService()
    for document_id, chunks in no_sparse.items():
        _, sparse = await embedder.embed_documents_with_sparse([c["content"] for c in chunks])
        for c, w in zip(chunks, sparse):
            await chunks_col.update_one({"chunk_id": c["chunk_id"]}, {"$set": {"sparse_weights": w}})
        print(f"sparse {document_id}: {len(chunks)} chunks")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
