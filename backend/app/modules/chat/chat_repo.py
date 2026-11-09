"""
Data Access Layer (Repository) cho Lịch Sử Tin Nhắn trong MongoDB
Tác giả: Vũ Thành - FinAnalyst AI

Mỗi notebook là một đoạn chat: tin nhắn gắn trực tiếp với notebook_id và được đánh số thứ tự bằng message_index.
"""

from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from app.infrastructure.database import collections
from app.shared.base_repo import BaseRepository
from app.shared.common import get_utc_now
from app.modules.chat.chat_models import MessageRecord


class ChatRepository(BaseRepository):
    """Lớp xử lý dữ liệu Tin nhắn kết nối MongoDB collection `messages`."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.MESSAGES_COLLECTION)
        self.notebooks = db[collections.NOTEBOOKS_COLLECTION]

    async def get_messages(self, notebook_id: str, limit: int = 500) -> List[MessageRecord]:
        """The latest `limit` messages, oldest first."""
        docs = await self.find_many({"notebook_id": notebook_id}, sort_by=[("message_index", -1)], limit=limit)
        return [MessageRecord(**doc) for doc in reversed(docs)]

    async def append_message(self, message: MessageRecord) -> str:
        """Number the message with the notebook's atomic counter; the same update marks the notebook as just used."""
        notebook = await self.notebooks.find_one_and_update(
            {"notebook_id": message.notebook_id},
            {"$inc": {"message_count": 1}, "$set": {"updated_at": get_utc_now()}},
            projection={"message_count": 1},
            return_document=ReturnDocument.AFTER,
        )
        message.message_index = notebook["message_count"] - 1
        return await self.insert_one(message.model_dump())

    async def set_title(self, notebook_id: str, title: str) -> None:
        await self.notebooks.update_one({"notebook_id": notebook_id}, {"$set": {"title": title}})
