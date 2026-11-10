"""
Quản Lý Kết Nối & Khởi Tạo Chỉ Mục MongoDB (MongoDB Lifecycle & Indexing)
Tác giả: Vũ Thành - FinAnalyst AI

1. Quản lý vòng đời kết nối Motor Async MongoDB.
2. Tạo các chỉ mục theo đặc tả docs/Version_2/PILLAR_2_MONGODB_SPECIFICATION.md. Chỉ mục unique là ràng buộc dữ liệu, nên tạo
   thất bại thì ứng dụng dừng khởi động thay vì âm thầm chạy thiếu ràng buộc.
3. Cung cấp Dependency `get_database` cho FastAPI Router.
"""

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.collation import Collation
from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.database import collections


class MongoManager:
    """Lớp quản lý kết nối cơ sở dữ liệu MongoDB Async Motor."""

    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    # ==============================================================================
    # HÀM: connect_to_database
    # Ý NGHĨA: Khởi tạo kết nối đến máy chủ MongoDB dựa trên cấu hình MONGODB_URI
    #          và gọi tự động hàm ensure_indexes() để tạo chỉ mục tối ưu truy vấn.
    # ==============================================================================
    @classmethod
    async def connect_to_database(cls) -> None:
        """Khởi tạo Client Motor và tự động kiểm tra/tạo các chỉ mục CSDL."""
        cls.client = AsyncIOMotorClient(settings.MONGODB_URI)
        cls.db = cls.client[settings.MONGODB_DB_NAME]
        logger.info(f"Connected to MongoDB database: '{settings.MONGODB_DB_NAME}'")
        await cls.ensure_indexes()

    # ==============================================================================
    # HÀM: close_database_connection
    # Ý NGHĨA: Đóng kết nối an toàn Connection Pool khi ứng dụng FastAPI tắt (Graceful Shutdown).
    # ==============================================================================
    @classmethod
    async def close_database_connection(cls) -> None:
        """Đóng an toàn MongoDB connection pool khi tắt máy chủ ứng dụng."""
        if cls.client:
            logger.info("Closing MongoDB connection pool...")
            cls.client.close()
            logger.info("MongoDB connection closed.")

    @classmethod
    async def ensure_indexes(cls) -> None:
        """Create every index of the specification; a failure stops the startup (a missing unique index is a missing constraint)."""
        if cls.db is None:
            return
        case_insensitive = Collation(locale="en", strength=2)
        guest_only = {"owner_type": "guest"}
        string_hash = {"file_hash": {"$type": "string"}}

        users = cls.db[collections.USERS_COLLECTION]
        await users.create_index("user_id", unique=True)
        await users.create_index("email", unique=True, collation=case_insensitive)
        await users.create_index("username", unique=True, collation=case_insensitive)
        await users.create_index("reset_token", sparse=True)

        notebooks = cls.db[collections.NOTEBOOKS_COLLECTION]
        await notebooks.create_index("notebook_id", unique=True)
        await notebooks.create_index([("owner_id", 1), ("updated_at", -1)])
        await notebooks.create_index("updated_at", partialFilterExpression=guest_only)  # expiry of guest notebooks

        documents = cls.db[collections.DOCUMENTS_COLLECTION]
        await documents.create_index("document_id", unique=True)
        await documents.create_index([("notebook_id", 1), ("created_at", -1)])
        await documents.create_index([("notebook_id", 1), ("file_hash", 1)], unique=True, partialFilterExpression=string_hash)

        jobs = cls.db[collections.INGESTION_JOBS_COLLECTION]
        await jobs.create_index("job_id", unique=True)
        await jobs.create_index("document_id", unique=True)
        await jobs.create_index([("status", 1), ("queued_at", 1)])

        chunks = cls.db[collections.CHUNKS_COLLECTION]
        await chunks.create_index("chunk_id", unique=True)
        await chunks.create_index([("notebook_id", 1), ("document_id", 1)])
        await chunks.create_index([("document_id", 1), ("chunk_index", 1)])

        messages = cls.db[collections.MESSAGES_COLLECTION]
        await messages.create_index("message_id", unique=True)
        await messages.create_index([("notebook_id", 1), ("message_index", 1)], unique=True)
        logger.info("MongoDB indexes verified successfully.")


# ==============================================================================
# HÀM: get_database
# Ý NGHĨA: FastAPI Dependency cung cấp phiên kết nối AsyncIOMotorDatabase
#          cho các API Router và Repository.
# ĐẦU RA: AsyncIOMotorDatabase
# ==============================================================================
async def get_database() -> AsyncIOMotorDatabase:
    """FastAPI Dependency cung cấp database instance kết nối với MongoDB."""
    if MongoManager.db is None:
        await MongoManager.connect_to_database()
    return MongoManager.db
