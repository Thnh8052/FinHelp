"""One-off migration to the MongoDB V3 schema (docs/Version_2/PILLAR_2_MONGODB_SPECIFICATION.md). Safe to run twice.
  python scripts/migrate_mongo_v3.py --dry-run     # show what would change, write nothing
  python scripts/migrate_mongo_v3.py               # apply, then create the V3 indexes
"""
import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pymongo import MongoClient

from app.core.config import settings

OLD_INDEXES = {"users": ["email_1", "username_1"], "notebooks": ["user_id_1_updated_at_-1"], "messages": ["session_id_1_created_at_1"]}
MUST_BE_EMPTY = ["documents", "chunks", "messages", "ingestion_jobs"]  # the old shape of these has no conversion: stop if any holds data


def main(dry_run: bool) -> int:
    db = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=8000)[settings.MONGODB_DB_NAME]
    say = lambda text: print(("[dry-run] " if dry_run else "") + text)

    blocked = {name: db[name].estimated_document_count() for name in MUST_BE_EMPTY if db[name].estimated_document_count()}
    if blocked:
        print(f"STOP: these collections hold data in the old shape, nothing was changed: {blocked}")
        return 1
    users = list(db.users.find({}))
    for field in ("email", "username"):
        lowered = [u[field].strip().lower() for u in users]
        if len(set(lowered)) != len(lowered):
            print(f"STOP: two accounts differ only by the case of their {field}, nothing was changed.")
            return 1

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    for user in users:
        if "quota" not in user:
            continue
        quota = user["quota"]
        say(f"users: flatten the quota of one account (role={user.get('role')})")
        if not dry_run:
            db.users.update_one({"_id": user["_id"]}, {
                "$set": {
                    "email": user["email"].strip().lower(),
                    "username": user["username"].strip().lower(),
                    "daily_messages_limit": quota.get("daily_messages_limit", 100),
                    "daily_messages_used": quota.get("messages_used_today", 0),
                    "daily_window_start": today,
                    "total_tokens_consumed": quota.get("total_tokens_consumed", 0),
                },
                "$unset": {"quota": ""},
            })

    for notebook in db.notebooks.find({"user_id": {"$exists": True}}):
        guest = notebook["user_id"] == "guest"
        say(f"notebooks: convert the owner of {notebook['notebook_id']}")
        if not dry_run:
            db.notebooks.update_one({"_id": notebook["_id"]}, {
                "$set": {
                    "owner_type": "guest" if guest else "user",
                    "owner_id": notebook["notebook_id"].removeprefix("nb_guest_") if guest else notebook["user_id"],
                    "focus_state": {},
                    "message_count": 0,
                },
                "$unset": {"user_id": "", "description": "", "tags": "", "document_ids": ""},
            })

    for collection, names in OLD_INDEXES.items():
        existing = db[collection].index_information()
        for name in names:
            if name in existing:
                say(f"{collection}: drop the old index {name}")
                if not dry_run:
                    db[collection].drop_index(name)

    if "chat_sessions" in db.list_collection_names():
        say(f"chat_sessions: drop the collection ({db.chat_sessions.estimated_document_count()} record(s))")
        if not dry_run:
            db.chat_sessions.drop()

    if dry_run:
        print("[dry-run] nothing was written.")
        return 0

    from app.infrastructure.database.mongodb import MongoManager

    async def indexes() -> None:
        await MongoManager.connect_to_database()  # creates every V3 index
        await MongoManager.close_database_connection()

    asyncio.run(indexes())
    print("Migration finished.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    sys.exit(main(parser.parse_args().dry_run))
