import asyncio
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.db.mongodb import MongoManager

async def main():
    await MongoManager.connect_to_database()
    if MongoManager.db is None:
        print("MongoDB connection failed! db is None")
        return
    print("Database connected:", MongoManager.db.name)
    collections = await MongoManager.db.list_collection_names()
    print("Collections:", collections)
    users = await MongoManager.db.users.find({}, {"hashed_password": 0}).to_list(100)
    print("Found users count:", len(users))
    for u in users:
        print("User:", u.get("username"), "| role:", u.get("role"), "| full_name:", u.get("full_name"))

if __name__ == "__main__":
    asyncio.run(main())
