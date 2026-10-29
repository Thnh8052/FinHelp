"""
API Router: Quản Lý Không Gian Sổ Tay (Notebook Management)
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Lấy danh sách Sổ tay của người dùng đang đăng nhập (GET /api/v1/notebooks).
2. Tạo mới Sổ tay phân tích tài chính (POST /api/v1/notebooks).
3. Lấy thông tin chi tiết một Sổ tay (GET /api/v1/notebooks/{notebook_id}).
4. Chỉnh sửa tiêu đề và mô tả của Sổ tay (PUT /api/v1/notebooks/{notebook_id}).
5. Xóa Sổ tay phân tích (DELETE /api/v1/notebooks/{notebook_id}).
6. Đảm bảo toàn vẹn dữ liệu: chỉ chủ sở hữu sổ tay (user_id) mới có quyền xem, sửa, xóa.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.api.v1.deps import GUEST_PREFIX, get_current_user_id, get_optional_user_id, require_notebook
from app.db.mongodb import get_database
from app.db.repositories.notebook_repo import NotebookRepository
from app.models.notebook import NotebookRecord

router = APIRouter(prefix="/notebooks", tags=["Notebooks"])


# --- Schemas ---

class CreateNotebookRequest(BaseModel):
    title: str
    description: str | None = None
    tags: List[str] = []


class UpdateNotebookRequest(BaseModel):
    title: str | None = None
    description: str | None = None


# --- Endpoints ---

# ==============================================================================
# HÀM: list_notebooks
# Ý NGHĨA: Lấy toàn bộ danh sách các Sổ tay (Notebooks) thuộc sở hữu của người dùng đang đăng nhập.
# ĐẦU VÀO:
#   - user_id: Lấy từ JWT Token đã xác thực.
#   - db: Kết nối MongoDB Motor.
# ĐẦU RA:
#   - List[NotebookRecord]: Danh sách các sổ tay sắp xếp theo thời gian cập nhật mới nhất.
# ==============================================================================
@router.get("", response_model=List[NotebookRecord])
async def list_notebooks(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lấy danh sách các Sổ tay của người dùng hiện tại từ MongoDB."""
    repo = NotebookRepository(db)
    nbs = await repo.get_by_user(user_id)
    if not nbs:
        default_nb = NotebookRecord(
            notebook_id=f"nb_{user_id}_{uuid.uuid4().hex[:6]}",
            user_id=user_id,
            title="Phân Tích Báo Cáo Tài Chính",
            description="Không gian phân tích báo cáo tài chính doanh nghiệp",
            tags=["Báo cáo tài chính"],
        )
        await repo.save_notebook(default_nb)
        return [default_nb]
    return nbs


# ==============================================================================
# HÀM: create_notebook
# Ý NGHĨA: Tạo một Sổ tay phân tích tài chính mới với mã định danh duy nhất (nb_xxxxxxxx)
#          và gán quyền sở hữu cho người dùng đang gửi request.
# ĐẦU VÀO:
#   - req (CreateNotebookRequest): title, description, tags.
#   - user_id: Người dùng đăng nhập.
# ĐẦU RA:
#   - NotebookRecord: Bản ghi Sổ tay vừa tạo thành công.
# ==============================================================================
@router.post("", response_model=NotebookRecord)
async def create_notebook(
    req: CreateNotebookRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Tạo mới một Sổ tay phân tích tài chính trong MongoDB."""
    repo = NotebookRepository(db)
    nb_id = f"nb_{uuid.uuid4().hex[:8]}"
    record = NotebookRecord(
        notebook_id=nb_id,
        user_id=user_id,
        title=req.title,
        description=req.description,
        tags=req.tags,
    )
    await repo.save_notebook(record)
    return record


# ==============================================================================
# HÀM: get_notebook
# Ý NGHĨA: Truy vấn thông tin chi tiết của một Sổ tay theo notebook_id.
#          Cho phép khách xem sổ tay mẫu (nb_sec_*) hoặc sổ tay dùng thử (nb_guest_*).
# ĐẦU VÀO:
#   - notebook_id: Mã định danh sổ tay.
#   - user_id: Lấy tùy chọn từ JWT (None nếu là Guest).
# ĐẦU RA:
#   - NotebookRecord hoặc lỗi 404 nếu không tìm thấy.
# ==============================================================================
@router.get("/{notebook_id}", response_model=NotebookRecord)
async def get_notebook(
    notebook_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lấy thông tin chi tiết một Sổ tay theo ID."""
    return await require_notebook(db, notebook_id, user_id)


# ==============================================================================
# HÀM: create_guest_notebook
# Ý NGHĨA: Cấp cho mỗi khách chưa đăng nhập một notebook riêng (nb_guest_ + 32 ký tự hex ngẫu nhiên).
#          Mã notebook là chìa khóa của khách (frontend lưu trong trình duyệt); khách này không thấy tài liệu
#          và hội thoại của khách khác.
# ==============================================================================
@router.post("/guest", response_model=NotebookRecord)
async def create_guest_notebook(db: AsyncIOMotorDatabase = Depends(get_database)):
    record = NotebookRecord(
        notebook_id=f"{GUEST_PREFIX}{uuid.uuid4().hex}",
        user_id="guest",
        title="Không Gian Dùng Thử (Khách Chưa Đăng Nhập)",
    )
    await NotebookRepository(db).save_notebook(record)
    return record


# ==============================================================================
# HÀM: update_notebook
# Ý NGHĨA: Chỉnh sửa tiêu đề (title) hoặc mô tả (description) của Sổ tay.
#          Kiểm tra quyền sở hữu trước khi cập nhật dữ liệu vào MongoDB.
# ĐẦU VÀO:
#   - notebook_id: Mã sổ tay cần cập nhật.
#   - req (UpdateNotebookRequest): title mới, description mới.
#   - user_id: Người dùng gửi yêu cầu.
# ĐẦU RA:
#   - JSON thông báo trạng thái cập nhật thành công.
# ==============================================================================
@router.put("/{notebook_id}")
async def update_notebook(
    notebook_id: str,
    req: UpdateNotebookRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Cập nhật tiêu đề hoặc mô tả của Sổ tay."""
    repo = NotebookRepository(db)
    nb = await repo.get_by_id(notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy Notebook hoặc không có quyền chỉnh sửa")
    success = await repo.update_notebook(notebook_id, title=req.title, description=req.description)
    return {"success": success, "message": "Cập nhật Notebook thành công"}


# ==============================================================================
# HÀM: delete_notebook
# Ý NGHĨA: Xóa Sổ tay khỏi cơ sở dữ liệu MongoDB.
#          Kiểm tra quyền sở hữu trước khi xóa.
# ĐẦU VÀO:
#   - notebook_id: Mã sổ tay cần xóa.
#   - user_id: Người dùng gửi yêu cầu.
# ĐẦU RA:
#   - JSON thông báo kết quả xóa thành công.
# ==============================================================================
@router.delete("/{notebook_id}")
async def delete_notebook(
    notebook_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Xóa Sổ tay khỏi MongoDB."""
    repo = NotebookRepository(db)
    nb = await repo.get_by_id(notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy Notebook hoặc không có quyền xóa")
    success = await repo.delete_notebook(notebook_id)
    return {"success": success, "message": "Xóa Notebook thành công"}
