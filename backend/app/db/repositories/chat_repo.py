"""
Data Access Layer (Repository) cho Phiên Chat & Lịch Sử Tin Nhắn trong MongoDB
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Quản lý các phiên hội thoại (Chat Sessions) trong MongoDB collection `chat_sessions`.
2. Lưu trữ toàn bộ tin nhắn hỏi - đáp kèm trích dẫn (Citations) và thông tin trace
   trong collection `messages`.
3. Hỗ trợ xóa phiên hội thoại kèm tính năng Cascade Delete (dọn dẹp toàn bộ tin nhắn liên quan).
4. Đổi tiêu đề phiên chat tự động hoặc theo yêu cầu người dùng.
"""

from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.chat import ChatSessionRecord, MessageRecord


class ChatRepository(BaseRepository):
    """Lớp xử lý dữ liệu Phiên chat & Tin nhắn (Chat Repository) kết nối MongoDB."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.CHAT_SESSIONS_COLLECTION)
        self.messages_collection = db[collections.MESSAGES_COLLECTION]

    # ==============================================================================
    # HÀM: get_session
    # Ý NGHĨA: Tìm kiếm bản ghi phiên hội thoại trong MongoDB theo session_id.
    # ĐẦU VÀO: session_id (str)
    # ĐẦU RA: ChatSessionRecord hoặc None
    # ==============================================================================
    async def get_session(self, session_id: str) -> Optional[ChatSessionRecord]:
        doc = await self.find_one({"session_id": session_id})
        return ChatSessionRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: get_sessions_by_notebook
    # Ý NGHĨA: Lấy danh sách toàn bộ phiên hội thoại thuộc một sổ tay (notebook_id),
    #          sắp xếp theo thời gian cập nhật gần nhất (updated_at giảm dần).
    # ĐẦU VÀO: notebook_id (str)
    # ĐẦU RA: List[ChatSessionRecord]
    # ==============================================================================
    async def get_sessions_by_notebook(self, notebook_id: str) -> List[ChatSessionRecord]:
        docs = await self.find_many({"notebook_id": notebook_id}, sort_by=[("updated_at", -1)])
        return [ChatSessionRecord(**doc) for doc in docs]

    # ==============================================================================
    # HÀM: get_messages
    # Ý NGHĨA: Lấy danh sách tin nhắn của một phiên hội thoại từ collection `messages`,
    #          sắp xếp theo thời gian tạo tăng dần (created_at tăng dần) để hiển thị luồng hội thoại liên tục.
    # ĐẦU VÀO: session_id (str), limit (int = 50)
    # ĐẦU RA: List[MessageRecord]
    # ==============================================================================
    async def get_messages(self, session_id: str, limit: int = 50) -> List[MessageRecord]:
        cursor = self.messages_collection.find({"session_id": session_id}).sort("created_at", 1).limit(limit)
        items = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            items.append(MessageRecord(**doc))
        return items

    # ==============================================================================
    # HÀM: append_message
    # Ý NGHĨA: Chèn thêm một tin nhắn mới (User hoặc Assistant) vào collection `messages`.
    # ĐẦU VÀO: message (MessageRecord)
    # ĐẦU RA: str (ID của tin nhắn vừa lưu)
    # ==============================================================================
    async def append_message(self, message: MessageRecord) -> str:
        res = await self.messages_collection.insert_one(message.model_dump())
        return str(res.inserted_id)

    # ==============================================================================
    # HÀM: save_session
    # Ý NGHĨA: Lưu bản ghi phiên hội thoại mới vào collection `chat_sessions`.
    # ĐẦU VÀO: session (ChatSessionRecord)
    # ĐẦU RA: str (ID của phiên hội thoại)
    # ==============================================================================
    async def save_session(self, session: ChatSessionRecord) -> str:
        return await self.insert_one(session.model_dump())

    # ==============================================================================
    # HÀM: delete_session
    # Ý NGHĨA: Xóa phiên hội thoại và thực hiện Cascade Delete (xóa sạch toàn bộ tin nhắn
    #          có session_id tương ứng trong collection `messages`).
    # ĐẦU VÀO: session_id (str)
    # ĐẦU RA: bool (True nếu xóa thành công)
    # ==============================================================================
    async def delete_session(self, session_id: str) -> bool:
        await self.messages_collection.delete_many({"session_id": session_id})
        return await self.delete_one({"session_id": session_id}) > 0

    # ==============================================================================
    # HÀM: update_session_title
    # Ý NGHĨA: Đổi tiêu đề hiển thị của phiên hội thoại trong danh sách lịch sử chat.
    # ĐẦU VÀO: session_id (str), new_title (str)
    # ĐẦU RA: bool
    # ==============================================================================
    async def update_session_title(self, session_id: str, new_title: str) -> bool:
        return await self.update_one({"session_id": session_id}, {"title": new_title}) > 0
