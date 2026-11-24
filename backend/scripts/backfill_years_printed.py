"""One-off backfill (24/11, TRIED DV-15): documents read before the period rule used every printed year get `metadata.years_printed` from their
stored chunks, so the rule needs no re-upload. Until then such a document keeps the old rule (the years heading its tables).
Without --apply it only counts. It refuses any database but the dev one unless --real is given (the real database needs the owner's yes).
  cd backend && .venv/Scripts/python.exe scripts/backfill_years_printed.py --env .env.dev [--apply] [--real]
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def years_from_chunks(chunks: list) -> list:
    """catalog.years_printed over the report's pages rebuilt from its chunks."""
    from app.modules.ingestion.catalog import years_printed
    pages = defaultdict(list)
    for c in chunks:
        pages[int(c.get("page") or 0)].append(c.get("content") or "")
    return years_printed({p: "\n\n".join(t) for p, t in pages.items()})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, help="env file whose MONGODB_URI / MONGODB_DB_NAME are used (.env.dev)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--real", action="store_true", help="allow a database other than datn_dev")
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(BACKEND / args.env, override=True)
    from pymongo import MongoClient
    from app.core.config import settings
    from app.infrastructure.database import collections
    if settings.MONGODB_DB_NAME != "datn_dev" and not args.real:
        sys.exit(f"refusing to write to '{settings.MONGODB_DB_NAME}': pass --real only with the owner's yes")
    db = MongoClient(settings.MONGODB_URI)[settings.MONGODB_DB_NAME]
    docs, chunks = db[collections.DOCUMENTS_COLLECTION], db[collections.CHUNKS_COLLECTION]
    todo = list(docs.find({"$or": [{"metadata.years_printed": {"$exists": False}}, {"metadata.years_printed": []}]}, {"document_id": 1, "file_name": 1, "_id": 0}))
    print(f"database {settings.MONGODB_DB_NAME}: {len(todo)} documents without printed years")
    for d in todo:
        years = years_from_chunks(list(chunks.find({"document_id": d["document_id"]}, {"page": 1, "content": 1, "_id": 0})))
        print(f"  {d['document_id']} {d.get('file_name')}: {len(years)} years, {years[:3]} ... {years[-3:]}")
        if args.apply and years:
            docs.update_one({"document_id": d["document_id"]}, {"$set": {"metadata.years_printed": years}})
    print("written" if args.apply else "dry run: add --apply to write")


if __name__ == "__main__":
    main()
