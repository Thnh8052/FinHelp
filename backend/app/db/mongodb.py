"""
Quản Lý Kết Nối & Khởi Tạo Chỉ Mục MongoDB (MongoDB Lifecycle & Indexing)
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Quản lý vòng đời kết nối Motor Async MongoDB (kết nối khi ứng dụng khởi động, đóng pool khi tắt).
2. Tự động khởi tạo và kiểm tra các Chỉ mục (Indexes) đơn lẻ và phức hợp (Compound Indexes)
   trên toàn bộ các collection:
   - users: Chỉ mục unique trên user_id, email, username; chỉ mục thưa (sparse) trên reset_token.
   - notebooks: Chỉ mục unique trên notebook_id; chỉ mục kết hợp [user_id, updated_at].
   - documents: Chỉ mục kết hợp [notebook_id, created_at].
   - chunks: Chỉ mục unique trên chunk_id; chỉ mục kết hợp [notebook_id, document_id].
   - chat_sessions: Chỉ mục unique trên session_id; chỉ mục kết hợp [notebook_id, user_id, updated_at].
   - messages: Chỉ mục unique trên message_id; chỉ mục kết hợp [session_id, created_at].
   - ingestion_jobs: Chỉ mục unique trên job_id.
3. Cung cấp Dependency `get_database` cho FastAPI Router.
"""

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings
from app.core.logging import logger
from app.db import collections


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
        logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}...")
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

    # ==============================================================================
    # HÀM: ensure_indexes
    # Ý NGHĨA: Đảm bảo toàn bộ các chỉ mục duy nhất (unique) và chỉ mục kết hợp (compound)
    #          được thiết lập chuẩn xác nhằm tối ưu hóa tốc độ truy vấn và ngăn chặn trùng lặp dữ liệu.
    # ==============================================================================
    @classmethod
    async def ensure_indexes(cls) -> None:
        """Tạo các Index duy nhất và Compound Index tối ưu hóa truy vấn trên các Collection."""
        if cls.db is None:
            return

        try:
            # Collection users: Đảm bảo user_id, email, username là duy nhất
            await cls.db[collections.USERS_COLLECTION].create_index("user_id", unique=True)
            await cls.db[collections.USERS_COLLECTION].create_index("email", unique=True)
            await cls.db[collections.USERS_COLLECTION].create_index("username", unique=True)
            await cls.db[collections.USERS_COLLECTION].create_index("reset_token", sparse=True)

            # Collection notebooks: Sắp xếp và truy vấn nhanh theo user_id và thời gian cập nhật
            await cls.db[collections.NOTEBOOKS_COLLECTION].create_index("notebook_id", unique=True)
            await cls.db[collections.NOTEBOOKS_COLLECTION].create_index(
                [("user_id", 1), ("updated_at", -1)]
            )

            # Collection documents: Truy vấn nhanh danh sách tài liệu theo notebook
            await cls.db[collections.DOCUMENTS_COLLECTION].create_index(
                [("notebook_id", 1), ("created_at", -1)]
            )

            # Collection chunks: Truy vấn đoạn văn bản theo chunk_id và tài liệu
            await cls.db[collections.CHUNKS_COLLECTION].create_index(
                [("chunk_id", 1)], unique=True
            )
            await cls.db[collections.CHUNKS_COLLECTION].create_index(
                [("notebook_id", 1), ("document_id", 1)]
            )

            # Collection chat_sessions & messages: Tối ưu tải lịch sử chat theo notebook và session
            await cls.db[collections.CHAT_SESSIONS_COLLECTION].create_index("session_id", unique=True)
            await cls.db[collections.CHAT_SESSIONS_COLLECTION].create_index(
                [("notebook_id", 1), ("user_id", 1), ("updated_at", -1)]
            )
            await cls.db[collections.MESSAGES_COLLECTION].create_index("message_id", unique=True)
            await cls.db[collections.MESSAGES_COLLECTION].create_index(
                [("session_id", 1), ("created_at", 1)]
            )

            # Collection ingestion_jobs: Theo dõi tiến độ trích xuất tài liệu
            await cls.db[collections.INGESTION_JOBS_COLLECTION].create_index("job_id", unique=True)
            logger.info("MongoDB indexes verified successfully.")
        except Exception as exc:
            logger.warning(f"Could not verify MongoDB indexes: {exc}")


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
