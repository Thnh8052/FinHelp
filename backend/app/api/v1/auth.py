"""
API Router: Xác Thực & Quản Lý Người Dùng (Authentication & RBAC)
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Đăng ký tài khoản mới (POST /api/v1/auth/register).
2. Đăng nhập hệ thống chuẩn OAuth2 Form (POST /api/v1/auth/login) và JSON (POST /api/v1/auth/login-json).
3. Lấy thông tin tài khoản hiện tại kèm Hạn mức Quota còn lại (GET /api/v1/auth/me).
4. Quy trình khôi phục mật khẩu qua mã OTP 6 số (POST /forgot-password & POST /reset-password).
5. Đổi mật khẩu cho người dùng đang đăng nhập (POST /change-password).
(Các endpoint của Quản trị viên nằm ở admin.py.)
"""

from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.mongodb import get_database
from app.db.repositories.user_repo import UserRepository
from app.models.user import TIER_SPECS, UserQuota, UserRecord

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    identifier: str = Field(..., description="Email hoặc Username của người dùng")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    full_name: Optional[str] = None
    role: str = "user"
    tier: str = "user"


class UserProfileResponse(BaseModel):
    user_id: str
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    role: str
    quota: UserQuota
    is_active: bool
    created_at: Any = None
    last_login_at: Any = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., description="Mã OTP 6 chữ số")
    new_password: str = Field(..., min_length=6, description="Mật khẩu mới")


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


def _token_response(user: UserRecord) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.user_id),
        user_id=user.user_id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        tier=user.quota.tier,
    )


async def _authenticate(repo: UserRepository, identifier: str, password: str) -> TokenResponse:
    """Password login by email or username: the same check for the form and the JSON endpoint, no account has another way in."""
    user = await repo.get_by_email_or_username(identifier)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập / Email hoặc mật khẩu không chính xác",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản hiện đang bị tạm khóa",
        )
    await repo.update_last_login(user.user_id)
    return _token_response(user)


# --- Endpoints ---

# ==============================================================================
# HÀM: get_all_tiers
# Ý NGHĨA: Trả về danh mục chính sách hạn mức của hệ thống (Guest vs User) để
#          Frontend hiển thị bảng so sánh quyền lợi người dùng.
# ĐẦU RA: JSON chứa định nghĩa chi tiết của 2 gói "guest" và "user".
# ==============================================================================
@router.get("/tiers")
async def get_all_tiers():
    """Danh mục chính sách hạn mức: Chưa đăng nhập (1 tài liệu) vs Đã đăng nhập (5 tài liệu/notebook)."""
    return {"success": True, "tiers": TIER_SPECS}


# ==============================================================================
# HÀM: get_guest_quota
# Ý NGHĨA: Cung cấp thông tin hạn mức dùng thử cho khách chưa đăng nhập (tối đa 1 tài liệu, không giới hạn số câu hỏi)
#          giúp giao diện kiểm soát số lượt truy vấn mà không làm lộ tên model hay backend logic.
# ĐẦU RA: JSON mô tả hạn mức dùng thử dành cho khách.
# ==============================================================================
@router.get("/guest-quota")
async def get_guest_quota():
    """Hạn mức dùng thử cho khách chưa đăng nhập (1 tài liệu)."""
    guest_spec = TIER_SPECS["guest"]
    return {
        "is_authenticated": False,
        "tier": "guest",
        "max_upload_documents": guest_spec["max_upload_documents"],
        "max_file_size_mb": guest_spec["max_file_size_mb"],
        "cost_description": guest_spec["cost_description"],
    }


# ==============================================================================
# HÀM: register
# Ý NGHĨA: Đăng ký tài khoản người dùng mới. Kiểm tra trùng lặp email và username trong MongoDB,
#          băm mật khẩu an toàn bằng bcrypt, tạo hồ sơ tài khoản và cấp JWT Token đăng nhập ngay.
# ĐẦU VÀO:
#   - req (RegisterRequest): email, username, password, full_name.
#   - db: Kết nối MongoDB Motor.
# ĐẦU RA:
#   - TokenResponse: access_token, user_id, thông tin cơ bản của người dùng.
# ==============================================================================
@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    """Đăng ký tài khoản người dùng mới vào MongoDB (role='user', tối đa 5 tài liệu/notebook)."""
    repo = UserRepository(db)
    if await repo.get_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email này đã được sử dụng")
    if await repo.get_by_username(req.username):
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")

    user_id = f"usr_{uuid.uuid4().hex[:8]}"
    user = UserRecord(
        user_id=user_id,
        email=req.email,
        username=req.username,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name or req.username,
        role="user",
    )
    await repo.save_user(user)
    return _token_response(user)


# ==============================================================================
# HÀM: login
# Ý NGHĨA: Đăng nhập chuẩn OAuth2 Password Request Form (tương thích Swagger Docs và thư viện OAuth2).
#          Hỗ trợ nhập username hoặc email vào trường `username`.
# ĐẦU VÀO:
#   - form_data (OAuth2PasswordRequestForm): username, password.
# ĐẦU RA:
#   - TokenResponse: Bearer JWT Access Token.
# ==============================================================================
@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Đăng nhập chuẩn OAuth2 (hỗ trợ cả username hoặc email qua trường username)."""
    return await _authenticate(UserRepository(db), form_data.username, form_data.password)


# ==============================================================================
# HÀM: login_json
# Ý NGHĨA: Đăng nhập thông qua JSON Body (thích hợp cho ứng dụng Single Page App - React Frontend).
#          Người dùng có thể điền username hoặc email vào trường `identifier`.
# ĐẦU VÀO:
#   - req (LoginRequest): identifier, password.
# ĐẦU RA:
#   - TokenResponse: Bearer JWT Access Token.
# ==============================================================================
@router.post("/login-json", response_model=TokenResponse)
async def login_json(
    req: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Đăng nhập bằng JSON payload tiện lợi cho giao diện Frontend Web/SPA."""
    return await _authenticate(UserRepository(db), req.identifier, req.password)


# ==============================================================================
# HÀM: get_me
# Ý NGHĨA: Lấy thông tin hồ sơ chi tiết và hạn mức truy vấn còn lại của tài khoản đang đăng nhập.
# ĐẦU VÀO:
#   - current_user: Thực thể UserRecord xác thực từ JWT Bearer Token.
# ĐẦU RA:
#   - UserProfileResponse: email, username, họ tên, vai trò, chi tiết hạn mức Quota.
# ==============================================================================
@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: UserRecord = Depends(get_current_user)):
    """Lấy thông tin hồ sơ & Hạn mức Quota còn lại của người dùng đang đăng nhập."""
    return UserProfileResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        quota=current_user.quota,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )


# ==============================================================================
# HÀM: forgot_password
# Ý NGHĨA: Khởi tạo quy trình khôi phục mật khẩu. Sinh mã OTP 6 số ngẫu nhiên, lưu vào MongoDB
#          kèm thời gian hết hạn 15 phút.
# ĐẦU VÀO:
#   - req (ForgotPasswordRequest): email của người dùng.
# ĐẦU RA:
#   - JSON thông báo gửi thành công kèm otp_debug (phục vụ môi trường kiểm thử trực tiếp).
# ==============================================================================
@router.post("/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Tạo mã OTP 6 số để khôi phục mật khẩu (lưu vào MongoDB kèm thời hạn 15 phút)."""
    repo = UserRepository(db)
    user = await repo.get_by_email(req.email)
    if not user:
        return {
            "success": True,
            "message": "Nếu email tồn tại trong hệ thống, mã xác thực OTP đã được gửi đến hòm thư.",
        }

    otp_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    await repo.set_reset_token(req.email, otp_code, expires_at)
    response = {"success": True, "message": "Mã xác thực OTP đã được gửi đến email của bạn."}
    if settings.ENVIRONMENT == "development":  # no mail is sent yet: the code is shown only while developing, never to a real caller
        response["otp_debug"] = otp_code
    return response


# ==============================================================================
# HÀM: reset_password
# Ý NGHĨA: Xác thực mã OTP 6 số và cập nhật mật khẩu mới vào cơ sở dữ liệu MongoDB.
#          Kiểm tra thời hạn hiệu lực của mã OTP trước khi cập nhật.
# ĐẦU VÀO:
#   - req (ResetPasswordRequest): email, otp_code, new_password.
# ĐẦU RA:
#   - JSON thông báo đặt lại mật khẩu thành công.
# ==============================================================================
@router.post("/reset-password")
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Xác thực mã OTP và cập nhật mật khẩu mới trong MongoDB."""
    repo = UserRepository(db)
    user = await repo.get_by_email(req.email)
    if not user:
        raise HTTPException(status_code=400, detail="Yêu cầu không hợp lệ")

    if not user.reset_token or user.reset_token != req.otp_code:
        raise HTTPException(status_code=400, detail="Mã xác thực OTP không chính xác")

    if user.reset_token_expires_at:
        now_utc = datetime.now(timezone.utc)
        expires_at = user.reset_token_expires_at
        if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now_utc > expires_at:
            raise HTTPException(status_code=400, detail="Mã xác thực OTP đã hết hạn")

    new_hash = get_password_hash(req.new_password)
    await repo.update_password(user.user_id, new_hash)

    return {
        "success": True,
        "message": "Đặt lại mật khẩu thành công! Bạn có thể đăng nhập ngay với mật khẩu mới.",
    }


# ==============================================================================
# HÀM: change_password
# Ý NGHĨA: Cho phép người dùng đang đăng nhập đổi mật khẩu tài khoản của mình.
#          Yêu cầu nhập đúng mật khẩu cũ trước khi đổi mật khẩu mới.
# ĐẦU VÀO:
#   - req (ChangePasswordRequest): old_password, new_password.
#   - current_user: Bản ghi người dùng xác thực từ JWT.
# ĐẦU RA:
#   - JSON thông báo đổi mật khẩu thành công.
# ==============================================================================
@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Đổi mật khẩu cho tài khoản đang đăng nhập."""
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")

    repo = UserRepository(db)
    new_hash = get_password_hash(req.new_password)
    await repo.update_password(current_user.user_id, new_hash)

    return {"success": True, "message": "Đổi mật khẩu thành công"}
