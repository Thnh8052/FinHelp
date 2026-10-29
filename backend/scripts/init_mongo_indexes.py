import asyncio
from app.db.mongodb import MongoManager
from app.core.logging import logger


async def main():
    logger.info("Initializing MongoDB indexes...")
    await MongoManager.connect_to_database()
    await MongoManager.ensure_indexes()
    await MongoManager.close_database_connection()
    logger.info("MongoDB index initialization finished.")


if __name__ == "__main__":
    asyncio.run(main())
