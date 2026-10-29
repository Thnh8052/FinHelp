"""
Module Dependencies & Phân Quyền (FastAPI Dependency Injection & RBAC)
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Trích xuất và giải mã JWT Bearer Token từ Header của HTTP Request.
2. Xác thực danh tính người dùng và kiểm tra tính toàn vẹn của phiên làm việc.
3. Hỗ trợ 2 chế độ:
   - get_optional_current_user: Cho phép cả khách chưa đăng nhập (Guest) và người dùng đăng nhập truy cập.
   - get_current_user_id / get_current_user: Bắt buộc đăng nhập tài khoản.
4. Kiểm soát phân quyền dựa trên vai trò (Role-Based Access Control - RBAC) với đặc quyền require_admin.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.db.mongodb import get_database
from app.db.repositories.notebook_repo import NotebookRepository
from app.db.repositories.user_repo import UserRepository
from app.models.chat import ChatSessionRecord
from app.models.notebook import NotebookRecord
from app.models.user import UserRecord

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ==============================================================================
# HÀM: get_optional_current_user
# Ý NGHĨA: Phân loại truy cập linh hoạt: Nếu có Token hợp lệ thì trả về thông tin UserRecord;
#          nếu không có Token hoặc Token hết hạn thì trả về None (coi là Khách vãng lai - Guest).
# ĐẦU VÀO:
#   - token: Chuỗi Bearer JWT Token từ Authorization Header (nếu có).
#   - db: Kết nối Async Motor Database MongoDB.
# ĐẦU RA:
#   - Optional[UserRecord]: Bản ghi người dùng trong MongoDB hoặc None.
# ==============================================================================
async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Optional[UserRecord]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
        repo = UserRepository(db)
        return await repo.get_by_id(user_id)
    except JWTError:
        return None


# ==============================================================================
# HÀM: get_optional_user_id
# Ý NGHĨA: Trích xuất mã user_id nếu có token JWT hợp lệ, hoặc trả về None nếu là
#          Khách dùng thử chưa đăng nhập (Guest). Không gây lỗi 401.
# ĐẦU VÀO:
#   - token: Chuỗi Bearer JWT Token từ Authorization Header (nếu có).
# ĐẦU RA:
#   - Optional[str]: Mã user_id hoặc None.
# ==============================================================================
async def get_optional_user_id(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None



# ==============================================================================
# HÀM: get_current_user_id
# Ý NGHĨA: Xác thực BẮT BUỘC mã JWT. Nếu không có token hoặc token không hợp lệ,
#          hàm sẽ trả về lỗi HTTP 401 Unauthorized ngay lập tức. Nếu hợp lệ, trả về user_id.
# ĐẦU VÀO:
#   - token: Chuỗi Bearer JWT Token từ Header.
# ĐẦU RA:
#   - str: Mã user_id của người dùng đang đăng nhập.
# ==============================================================================
async def get_current_user_id(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu đăng nhập để sử dụng tính năng này",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Phiên làm việc không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception


# ==============================================================================
# HÀM: get_current_user
# Ý NGHĨA: Lấy toàn bộ thực thể tài khoản người dùng (UserRecord) từ MongoDB thông qua user_id.
#          Đồng thời đảm bảo tài khoản vẫn tồn tại và hợp lệ trong cơ sở dữ liệu.
# ĐẦU VÀO:
#   - user_id: Mã định danh người dùng (tiêm từ hàm get_current_user_id).
#   - db: Kết nối Async Motor Database MongoDB.
# ĐẦU RA:
#   - UserRecord: Thực thể người dùng đầy đủ bao gồm thông tin Quota, Role, Trạng thái.
# ==============================================================================
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserRecord:
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản không tồn tại trong hệ thống",
        )
    return user


# ==============================================================================
# HÀM: require_admin
# Ý NGHĨA: Cổng kiểm tra đặc quyền Quản trị viên (Admin RBAC Gate). Nếu người dùng
#          không có vai trò role == 'admin', hàm sẽ chặn lại với mã lỗi HTTP 403 Forbidden.
# ĐẦU VÀO:
#   - current_user: Thực thể người dùng đang đăng nhập.
# ĐẦU RA:
#   - UserRecord: Bản ghi quản trị viên hợp lệ.
# ==============================================================================
async def require_admin(
    current_user: UserRecord = Depends(get_current_user),
) -> UserRecord:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chức năng yêu cầu đặc quyền Quản trị viên (Admin)",
        )
    return current_user


# ==============================================================================
# QUYỀN TRUY CẬP NOTEBOOK / PHIÊN CHAT (một nơi duy nhất, mọi route dùng chung)
# - Chủ sở hữu: đọc + ghi.
# - Notebook khách (nb_guest_ + 32 ký tự hex ngẫu nhiên, cấp bởi POST /notebooks/guest): mã notebook là chìa khóa của khách.
# - Notebook mẫu nb_sec_*: chỉ đọc (xem tài liệu); hỏi đáp cần đăng nhập để phiên chat không bị chia sẻ giữa các khách.
# ==============================================================================
GUEST_PREFIX = "nb_guest_"
GUEST_KEY_LEN = 32
SAMPLE_PREFIX = "nb_sec_"


def is_guest_notebook(nb: NotebookRecord) -> bool:
    return nb.user_id == "guest" and nb.notebook_id.startswith(GUEST_PREFIX) and len(nb.notebook_id) >= len(GUEST_PREFIX) + GUEST_KEY_LEN


def can_access_notebook(nb: NotebookRecord, user_id: Optional[str], write: bool = False) -> bool:
    if user_id and nb.user_id == user_id:
        return True
    if is_guest_notebook(nb):
        return True
    return not write and nb.notebook_id.startswith(SAMPLE_PREFIX)


async def require_notebook(db: AsyncIOMotorDatabase, notebook_id: str, user_id: Optional[str], write: bool = False) -> NotebookRecord:
    """404 for an unknown notebook, 403 without access. Every route that reads or writes a notebook's data calls this."""
    nb = await NotebookRepository(db).get_by_id(notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Không tìm thấy Notebook")
    if not can_access_notebook(nb, user_id, write):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập Notebook này")
    return nb


def can_chat(nb: NotebookRecord, user_id: Optional[str]) -> bool:
    """Asking questions writes a session: the owner, or a guest in their own guest notebook."""
    return bool(user_id and nb.user_id == user_id) or is_guest_notebook(nb)


def session_owner(user_id: Optional[str]) -> str:
    return user_id or "guest"


def owns_session(session: ChatSessionRecord, user_id: Optional[str]) -> bool:
    return session.user_id == session_owner(user_id)
