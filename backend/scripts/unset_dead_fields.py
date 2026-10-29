"""One-off cleanup (2026-10-28): drop fields the models no longer have from records written before they were removed.
The app reads these records fine without it (Pydantic ignores unknown fields); this only tidies the stored documents.
  python scripts/unset_dead_fields.py
"""
import asyncio
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.collections import INGESTION_JOBS_COLLECTION, NOTEBOOKS_COLLECTION, USERS_COLLECTION
from app.db.mongodb import MongoManager
from app.core.logging import logger

DEAD_FIELDS = {
    USERS_COLLECTION: ["quota.provider_source", "quota.default_model", "quota.allowed_models"],
    NOTEBOOKS_COLLECTION: ["settings"],
    INGESTION_JOBS_COLLECTION: ["extracted_facts_count"],
}


async def main():
    await MongoManager.connect_to_database()
    for collection, fields in DEAD_FIELDS.items():
        result = await MongoManager.db[collection].update_many(
            {"$or": [{f: {"$exists": True}} for f in fields]}, {"$unset": {f: "" for f in fields}}
        )
        logger.info(f"{collection}: removed {fields} from {result.modified_count} record(s).")
    await MongoManager.close_database_connection()


if __name__ == "__main__":
    asyncio.run(main())
