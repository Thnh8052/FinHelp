import asyncio
from app.db.qdrant import QdrantManager
from app.core.logging import logger


async def main():
    logger.info("Initializing Qdrant collections and payload indexes...")
    await QdrantManager.connect_to_qdrant()
    await QdrantManager.ensure_collection()
    await QdrantManager.close_qdrant_connection()
    logger.info("Qdrant initialization finished.")


if __name__ == "__main__":
    asyncio.run(main())
