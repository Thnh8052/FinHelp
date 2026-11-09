"""
API Router: Quản Lý Không Gian Sổ Tay (Notebook Management)
Tác giả: Vũ Thành - FinAnalyst AI

Một notebook là một đoạn chat: danh sách lịch sử chat chính là danh sách notebook.
1. Lấy danh sách Sổ tay của người dùng đang đăng nhập (GET /api/v1/notebooks).
2. Tạo mới Sổ tay / đoạn chat (POST /api/v1/notebooks).
3. Lấy thông tin chi tiết một Sổ tay (GET /api/v1/notebooks/{notebook_id}).
4. Đổi tiêu đề (PUT /api/v1/notebooks/{notebook_id}).
5. Xóa Sổ tay cùng toàn bộ tài liệu, vector, tệp PDF và tin nhắn (DELETE /api/v1/notebooks/{notebook_id}).
6. Đảm bảo toàn vẹn dữ liệu: chỉ chủ sở hữu mới có quyền sửa, xóa.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.core.logging import logger
from app.shared.deps import GUEST_PREFIX, get_current_user_id, get_optional_user_id, require_notebook
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.notebooks.notebook_repo import NotebookRepository
from app.modules.notebooks.notebook import NotebookRecord
from app.modules.notebooks.purge import has_active_documents, purge_notebook

router = APIRouter(prefix="/notebooks", tags=["Notebooks"])


class CreateNotebookRequest(BaseModel):
    title: Optional[str] = None


class UpdateNotebookRequest(BaseModel):
    title: str


@router.get("", response_model=List[NotebookRecord])
async def list_notebooks(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Các đoạn chat của người dùng, mới dùng nhất lên đầu; tài khoản mới được tạo sẵn một đoạn."""
    repo = NotebookRepository(db)
    notebooks = await repo.get_by_owner(user_id)
    if not notebooks:
        first = NotebookRecord(notebook_id=f"nb_{uuid.uuid4().hex[:8]}", owner_id=user_id)
        await repo.save_notebook(first)
        return [first]
    return notebooks


@router.post("", response_model=NotebookRecord)
async def create_notebook(
    req: CreateNotebookRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Tạo một đoạn chat mới."""
    record = NotebookRecord(notebook_id=f"nb_{uuid.uuid4().hex[:8]}", owner_id=user_id, **({"title": req.title} if req.title else {}))
    await NotebookRepository(db).save_notebook(record)
    return record


# Khách có thể xem notebook của mình (mã notebook là chìa khóa) và mọi người có thể xem notebook mẫu (owner_type = system).
@router.get("/{notebook_id}", response_model=NotebookRecord)
async def get_notebook(
    notebook_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await require_notebook(db, notebook_id, user_id)


# Mỗi khách chưa đăng nhập có một notebook riêng (nb_guest_ + 32 ký tự hex ngẫu nhiên), tự xóa sau 24 giờ không dùng.
@router.post("/guest", response_model=NotebookRecord)
async def create_guest_notebook(db: AsyncIOMotorDatabase = Depends(get_database)):
    key = uuid.uuid4().hex
    record = NotebookRecord(
        notebook_id=f"{GUEST_PREFIX}{key}",
        owner_type="guest",
        owner_id=key,
        title="Không Gian Dùng Thử (Khách Chưa Đăng Nhập)",
    )
    await NotebookRepository(db).save_notebook(record)
    return record


async def _own_notebook(db: AsyncIOMotorDatabase, notebook_id: str, user_id: str) -> NotebookRecord:
    notebook = await NotebookRepository(db).get_by_id(notebook_id)
    if not notebook or notebook.owner_type != "user" or notebook.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy Notebook hoặc không có quyền thao tác")
    return notebook


@router.put("/{notebook_id}")
async def update_notebook(
    notebook_id: str,
    req: UpdateNotebookRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Đổi tiêu đề đoạn chat."""
    await _own_notebook(db, notebook_id, user_id)
    success = await NotebookRepository(db).rename(notebook_id, req.title)
    return {"success": success, "message": "Cập nhật Notebook thành công"}


@router.delete("/{notebook_id}")
async def delete_notebook(
    notebook_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """Xóa đoạn chat cùng toàn bộ tài liệu, vector, tệp PDF và tin nhắn của nó."""
    await _own_notebook(db, notebook_id, user_id)
    if await has_active_documents(db, notebook_id):
        raise HTTPException(status_code=409, detail="Tài liệu trong đoạn chat này đang được xử lý. Vui lòng đợi xử lý xong rồi mới xóa.")
    try:
        await purge_notebook(db, qdrant, notebook_id)
    except Exception as exc:
        logger.error(f"Could not purge notebook {notebook_id}: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=503, detail="Không thể xóa đầy đủ dữ liệu của đoạn chat. Vui lòng thử lại.") from exc
    return {"success": True, "message": "Xóa Notebook thành công"}
