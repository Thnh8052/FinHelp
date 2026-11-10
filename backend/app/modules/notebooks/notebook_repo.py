"""
Data Access Layer (Repository) cho Sổ Tay (Notebooks) trong MongoDB
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Quản lý không gian làm việc (một notebook là một đoạn chat) trong MongoDB collection `notebooks`.
2. Tạo mới, truy vấn theo chủ sở hữu, đổi tiêu đề và xóa sổ tay.
3. Hỗ trợ cách ly dữ liệu đa người dùng (Multi-tenant data isolation) theo owner_id.
"""

from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.infrastructure.database import collections
from app.shared.base_repo import BaseRepository
from app.shared.common import get_utc_now
from app.modules.notebooks.notebook import NotebookRecord


class NotebookRepository(BaseRepository):
    """Lớp xử lý dữ liệu Sổ tay (Notebook Repository) kết nối MongoDB collection `notebooks`."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.NOTEBOOKS_COLLECTION)

    async def get_by_id(self, notebook_id: str) -> Optional[NotebookRecord]:
        doc = await self.find_one({"notebook_id": notebook_id})
        return NotebookRecord(**doc) if doc else None

    async def get_by_owner(self, owner_id: str) -> List[NotebookRecord]:
        """The owner's notebooks, the most recently used first."""
        docs = await self.find_many({"owner_id": owner_id}, sort_by=[("updated_at", -1)])
        return [NotebookRecord(**doc) for doc in docs]

    async def save_notebook(self, notebook: NotebookRecord) -> str:
        return await self.insert_one(notebook.model_dump())

    async def rename(self, notebook_id: str, title: str) -> bool:
        return await self.update_one({"notebook_id": notebook_id}, {"title": title, "updated_at": get_utc_now()})

    async def touch(self, notebook_id: str) -> bool:
        """Mark activity: orders the chat list and postpones the expiry of a guest notebook."""
        return await self.update_one({"notebook_id": notebook_id}, {"updated_at": get_utc_now()})

    async def delete_notebook(self, notebook_id: str) -> bool:
        return await self.delete_one({"notebook_id": notebook_id})
