"""
Data Access Layer (Repository) cho Sổ Tay (Notebooks) trong MongoDB
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Quản lý không gian làm việc (Notebook / Project workspace) của người dùng trong MongoDB collection `notebooks`.
2. Tạo mới, truy vấn theo người dùng, cập nhật tiêu đề/mô tả và xóa sổ tay.
3. Hỗ trợ cách ly dữ liệu đa người dùng (Multi-tenant data isolation) theo user_id.
"""

from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.notebook import NotebookRecord


class NotebookRepository(BaseRepository):
    """Lớp xử lý dữ liệu Sổ tay (Notebook Repository) kết nối MongoDB collection `notebooks`."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.NOTEBOOKS_COLLECTION)

    # ==============================================================================
    # HÀM: get_by_id
    # Ý NGHĨA: Truy vấn bản ghi Sổ tay trong MongoDB theo mã định danh duy nhất notebook_id.
    # ĐẦU VÀO: notebook_id (str)
    # ĐẦU RA: NotebookRecord hoặc None
    # ==============================================================================
    async def get_by_id(self, notebook_id: str) -> Optional[NotebookRecord]:
        doc = await self.find_one({"notebook_id": notebook_id})
        return NotebookRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: get_by_user
    # Ý NGHĨA: Lấy danh sách toàn bộ sổ tay thuộc quyền sở hữu của một người dùng,
    #          sắp xếp theo thời gian cập nhật gần nhất (updated_at giảm dần).
    # ĐẦU VÀO: user_id (str)
    # ĐẦU RA: List[NotebookRecord]
    # ==============================================================================
    async def get_by_user(self, user_id: str) -> List[NotebookRecord]:
        docs = await self.find_many({"user_id": user_id}, sort_by=[("updated_at", -1)])
        return [NotebookRecord(**doc) for doc in docs]

    # ==============================================================================
    # HÀM: save_notebook
    # Ý NGHĨA: Lưu bản ghi Sổ tay mới vào MongoDB collection `notebooks`.
    # ĐẦU VÀO: notebook (NotebookRecord)
    # ĐẦU RA: str (ID bản ghi vừa chèn)
    # ==============================================================================
    async def save_notebook(self, notebook: NotebookRecord) -> str:
        return await self.insert_one(notebook.model_dump())

    # ==============================================================================
    # HÀM: update_notebook
    # Ý NGHĨA: Cập nhật tiêu đề hoặc mô tả của sổ tay phân tích tài chính.
    # ĐẦU VÀO: notebook_id (str), title (Optional[str]), description (Optional[str])
    # ĐẦU RA: bool (True nếu cập nhật thành công)
    # ==============================================================================
    async def update_notebook(
        self, notebook_id: str, title: Optional[str] = None, description: Optional[str] = None
    ) -> bool:
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
        if not update_data:
            return False
        return await self.update_one({"notebook_id": notebook_id}, update_data) > 0

    # ==============================================================================
    # HÀM: delete_notebook
    # Ý NGHĨA: Xóa sổ tay khỏi cơ sở dữ liệu MongoDB theo notebook_id.
    # ĐẦU VÀO: notebook_id (str)
    # ĐẦU RA: bool (True nếu xóa thành công)
    # ==============================================================================
    async def delete_notebook(self, notebook_id: str) -> bool:
        return await self.delete_one({"notebook_id": notebook_id}) > 0
