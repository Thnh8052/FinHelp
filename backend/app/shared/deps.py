"""
Module Dependencies & Phân Quyền (FastAPI Dependency Injection & RBAC)
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Trích xuất và giải mã JWT Bearer Token từ Header của HTTP Request.
2. Xác thực danh tính người dùng và kiểm tra tính toàn vẹn của phiên làm việc.
3. Hỗ trợ 2 chế độ:
   - get_optional_user_id: Cho phép cả khách chưa đăng nhập (Guest) và người dùng đăng nhập truy cập.
   - get_current_user_id / get_current_user: Bắt buộc đăng nhập tài khoản.
   Cả hai đều so token với tài khoản trong database (_account_of): đổi mật khẩu hoặc khóa tài khoản có hiệu lực ngay.
4. Kiểm soát phân quyền dựa trên vai trò (Role-Based Access Control - RBAC) với đặc quyền require_admin.
"""

from typing import Optional
from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.error_codes import Code, api_error
from app.infrastructure.database.mongodb import get_database
from app.modules.notebooks.notebook_repo import NotebookRepository
from app.modules.auth.user_repo import UserRepository
from app.modules.notebooks.notebook import NotebookRecord
from app.modules.auth.user import UserRecord

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
SESSION_COOKIE = "finhelp_session"
SESSION_COOKIE_PATH = "/api"
_REMOVE_SESSION_COOKIE = f"{SESSION_COOKIE}=; Max-Age=0; Path={SESSION_COOKIE_PATH}; HttpOnly; SameSite=strict"


async def read_token(request: Request, header_token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    """API clients send the token in a header; a browser keeps it in a cookie that page scripts cannot read."""
    return header_token or request.cookies.get(SESSION_COOKIE)


async def _account_of(token: str, db: AsyncIOMotorDatabase) -> UserRecord:
    """The account a sent token still speaks for. 401 when it is forged, expired, names nobody or predates a password change; 403 when the account is locked.
    A token issued before token_version existed has no "ver": it counts as 0, so nobody is signed out by the upgrade."""
    refused = api_error(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=Code.SESSION_EXPIRED,
        headers={"WWW-Authenticate": "Bearer", "Set-Cookie": _REMOVE_SESSION_COOKIE},  # page scripts cannot remove it: without this the browser could not even continue as a guest
    )
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise refused
    user = await UserRepository(db).get_by_id(claims["sub"]) if claims.get("sub") else None
    if user is None or claims.get("ver", 0) != user.token_version or claims.get("jti") in user.revoked_token_ids:
        raise refused
    if not user.is_active:
        raise api_error(status_code=status.HTTP_403_FORBIDDEN, code=Code.ACCOUNT_LOCKED)
    return user


# ==============================================================================
# HÀM: get_optional_user_id
# Ý NGHĨA: Trích xuất mã user_id nếu có token JWT, hoặc trả về None nếu là Khách dùng thử chưa đăng nhập (Guest).
#          Có gửi token nhưng token không còn hiệu lực thì bị từ chối, để người dùng được yêu cầu đăng nhập lại.
# ==============================================================================
async def get_optional_user_id(
    token: Optional[str] = Depends(read_token),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Optional[str]:
    return (await _account_of(token, db)).user_id if token else None


# ==============================================================================
# HÀM: get_current_user
# Ý NGHĨA: Xác thực BẮT BUỘC: không có token hoặc token không còn hiệu lực thì bị từ chối ngay.
# ĐẦU RA:
#   - UserRecord: Thực thể người dùng đầy đủ bao gồm thông tin Quota, Role, Trạng thái.
# ==============================================================================
async def get_current_user(
    token: Optional[str] = Depends(read_token),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserRecord:
    if not token:
        raise api_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=Code.LOGIN_REQUIRED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _account_of(token, db)


async def get_current_user_id(current_user: UserRecord = Depends(get_current_user)) -> str:
    return current_user.user_id


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
        raise api_error(status_code=status.HTTP_403_FORBIDDEN, code=Code.ADMIN_REQUIRED)
    return current_user


# ==============================================================================
# QUYỀN TRUY CẬP NOTEBOOK (một nơi duy nhất, mọi route dùng chung)
# - owner_type = user: chỉ chủ sở hữu.
# - owner_type = guest (nb_guest_ + 32 ký tự hex ngẫu nhiên, cấp bởi POST /notebooks/guest): mã notebook là chìa khóa của khách.
# - owner_type = system: notebook mẫu, ai cũng xem được, không ai ghi hay hỏi đáp được.
# ==============================================================================
GUEST_PREFIX = "nb_guest_"


def can_access_notebook(nb: NotebookRecord, user_id: Optional[str], write: bool = False) -> bool:
    if nb.owner_type == "guest":
        return True
    if nb.owner_type == "system":
        return not write
    return user_id is not None and nb.owner_id == user_id


async def require_notebook(db: AsyncIOMotorDatabase, notebook_id: str, user_id: Optional[str], write: bool = False) -> NotebookRecord:
    """404 for an unknown notebook, 403 without access. Every route that reads or writes a notebook's data calls this."""
    nb = await NotebookRepository(db).get_by_id(notebook_id)
    if not nb:
        raise api_error(status_code=404, code=Code.NOTEBOOK_NOT_FOUND)
    if not can_access_notebook(nb, user_id, write):
        raise api_error(status_code=403, code=Code.NOTEBOOK_FORBIDDEN)
    return nb


def can_chat(nb: NotebookRecord, user_id: Optional[str]) -> bool:
    """Asking writes to the notebook's conversation: its owner, or a guest in their own guest notebook."""
    return nb.owner_type != "system" and can_access_notebook(nb, user_id, write=True)
