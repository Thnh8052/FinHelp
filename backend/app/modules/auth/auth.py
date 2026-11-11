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

import asyncio
from datetime import datetime, timedelta, timezone
import hmac
import secrets
from typing import Annotated, Any, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from pymongo.errors import DuplicateKeyError

from app.shared.deps import SESSION_COOKIE, SESSION_COOKIE_PATH, get_current_user, read_token
from app.core.config import settings
from app.core.logging import logger
from app.core.security import create_access_token, get_password_hash, verify_password
from app.infrastructure.database.mongodb import get_database
from app.shared.rate_limit import client_ip, enforce, limiter
from app.core.error_codes import Code, api_error
from app.modules.auth.user_repo import UserRepository
from app.modules.auth.user import ADMIN_EMAIL, ADMIN_USERNAME, TIER_SPECS, UserQuota, UserRecord
from app.services.email_service import email_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Guessing limits: wrong passwords per account and per address, reset-code requests and tries (all within RATE_WINDOW seconds)
RATE_WINDOW = 15 * 60
LOGIN_FAILS_PER_ACCOUNT, LOGIN_FAILS_PER_IP = 10, 30
FORGOT_PER_EMAIL, FORGOT_PER_IP, RESET_PER_IP = 3, 10, 20
REGISTER_TAKEN_PER_IP = 10  # refused registrations per address: a taken name is what someone listing the accounts looks for
ACCOUNT_NOT_AVAILABLE = Code.ACCOUNT_NOT_AVAILABLE
MAX_RESET_ATTEMPTS = 5  # wrong codes before an OTP dies; the user must ask for a new one
INVALID_RESET_CODE = Code.INVALID_RESET_CODE  # one answer whether the account is unknown, the code wrong or expired
_NO_ACCOUNT_HASH = get_password_hash(secrets.token_urlsafe(16))  # checked when an account does not exist, so that signing in takes the same time
PASSWORD_MIN_CHARS = 8  # every way of setting a password; the sign-in form takes any length, so older accounts keep working


def _otp_hash(email: str, code: str) -> str:
    """What is stored instead of the code (a 6-digit code has only 900,000 values, so a plain hash would not protect it): keyed with the secret."""
    return hmac.new(settings.SECRET_KEY.encode(), f"{email.strip().lower()}:{code}".encode(), "sha256").hexdigest()


async def _issue_reset_code(db: AsyncIOMotorDatabase, email: str) -> None:
    """Runs after the response: the answer takes the same time and says the same thing whether or not the account exists."""
    repo = UserRepository(db)
    if not await repo.get_by_email(email):
        return
    code = f"{secrets.randbelow(900000) + 100000}"
    await repo.set_reset_token(email, _otp_hash(email, code), datetime.now(timezone.utc) + timedelta(minutes=15))
    if not await asyncio.to_thread(email_service.send_password_reset_otp, email, code) and settings.ENVIRONMENT == "development":
        logger.warning(f"[dev] No email was sent (SendGrid not configured). Reset code for {email}: {code}")  # server log only, never the response


# --- Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    username: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9._-]{3,32}$")]
    password: str = Field(..., min_length=PASSWORD_MIN_CHARS)
    full_name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None


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
    new_password: str = Field(..., min_length=PASSWORD_MIN_CHARS, description="Mật khẩu mới")


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=PASSWORD_MIN_CHARS)


def _start_session(request: Request, response: Response, signed_in: TokenResponse) -> TokenResponse:
    """The browser's copy of the token: a cookie page scripts cannot read, never sent from another site. The body keeps it for API clients."""
    _set_session_cookie(request, response, signed_in.access_token)
    return signed_in


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, path=SESSION_COOKIE_PATH, httponly=True, samesite="strict", secure=request.url.scheme == "https")


def _token_response(user: UserRecord) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.user_id, version=user.token_version),
        user_id=user.user_id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        tier=user.role,
    )


async def _authenticate(repo: UserRepository, identifier: str, password: str, ip: str) -> TokenResponse:
    """Password login by email or username: the same check for the form and the JSON endpoint, no account has another way in.
    Wrong passwords are counted per account (not per spelling of it) and per address; past the limit even the right password is refused."""
    user = await repo.get_by_email_or_username(identifier)
    account, address = f"login:account:{user.user_id if user else identifier.strip().lower()}", f"login:ip:{ip}"
    enforce(account, LOGIN_FAILS_PER_ACCOUNT, RATE_WINDOW)
    enforce(address, LOGIN_FAILS_PER_IP, RATE_WINDOW)
    # Counted before the check, which waits in a worker thread (bcrypt takes a few hundred ms): otherwise guesses sent together would all pass the limit
    limiter.record(account)
    limiter.record(address)
    matches = await asyncio.to_thread(verify_password, password, user.hashed_password if user else _NO_ACCOUNT_HASH)
    if not user or not matches:
        raise api_error(status_code=status.HTTP_401_UNAUTHORIZED, code=Code.INVALID_CREDENTIALS)
    limiter.clear(account)  # not a wrong guess after all
    limiter.forget_latest(address)
    if not user.is_active:
        raise api_error(status_code=status.HTTP_403_FORBIDDEN, code=Code.ACCOUNT_LOCKED)
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
async def register(request: Request, response: Response, req: RegisterRequest, background: BackgroundTasks, db: AsyncIOMotorDatabase = Depends(get_database)):
    """Đăng ký tài khoản người dùng mới vào MongoDB (role='user', tối đa 5 tài liệu/notebook)."""
    attempts = f"register:ip:{client_ip(request)}"
    enforce(attempts, REGISTER_TAKEN_PER_IP, RATE_WINDOW)
    limiter.record(attempts)  # counted before the lookups: registrations sent together cannot pass the limit; a success takes it back below
    repo = UserRepository(db)
    reserved = req.username.lower() == ADMIN_USERNAME or req.email.lower() == ADMIN_EMAIL  # the admin's names, even before it exists
    if reserved or await repo.get_by_email(req.email) or await repo.get_by_username(req.username):
        raise api_error(status_code=400, code=ACCOUNT_NOT_AVAILABLE)

    user_id = f"usr_{uuid.uuid4().hex[:8]}"
    user = UserRecord(
        user_id=user_id,
        email=req.email,
        username=req.username,
        hashed_password=await asyncio.to_thread(get_password_hash, req.password),
        full_name=req.full_name or req.username,
        role="user",
    )
    try:
        await repo.save_user(user)
    except DuplicateKeyError:  # two registrations raced past the checks above; the unique indexes refused the second
        raise api_error(status_code=400, code=ACCOUNT_NOT_AVAILABLE)
    limiter.forget_latest(attempts)
    # Sent after the response, in a worker thread: SendGrid's wait must not stop the server for everyone
    background.add_task(email_service.send_account_confirmation, to_email=user.email, username=user.username, full_name=user.full_name)
    return _start_session(request, response, _token_response(user))


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
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Đăng nhập chuẩn OAuth2 (hỗ trợ cả username hoặc email qua trường username)."""
    return _start_session(request, response, await _authenticate(UserRepository(db), form_data.username, form_data.password, client_ip(request)))


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
    request: Request,
    response: Response,
    req: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Đăng nhập bằng JSON payload tiện lợi cho giao diện Frontend Web/SPA."""
    return _start_session(request, response, await _authenticate(UserRepository(db), req.identifier, req.password, client_ip(request)))


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
#   - JSON thông báo gửi thành công. Mã OTP chỉ đi qua email, không bao giờ nằm trong phản hồi.
# ==============================================================================
@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    req: ForgotPasswordRequest,
    background: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Tạo mã OTP 6 số để khôi phục mật khẩu (lưu vào MongoDB kèm thời hạn 15 phút)."""
    email, address = f"forgot:email:{req.email.strip().lower()}", f"forgot:ip:{client_ip(request)}"
    enforce(email, FORGOT_PER_EMAIL, RATE_WINDOW)  # counted for unknown emails too: the answer does not tell which exist
    enforce(address, FORGOT_PER_IP, RATE_WINDOW)
    limiter.record(email)
    limiter.record(address)
    background.add_task(_issue_reset_code, db, req.email)
    return {"success": True}


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
    request: Request,
    req: ResetPasswordRequest,
    background: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Xác thực mã OTP và cập nhật mật khẩu mới trong MongoDB. Mỗi OTP chỉ được thử MAX_RESET_ATTEMPTS lần."""
    address = f"reset:ip:{client_ip(request)}"
    enforce(address, RESET_PER_IP, RATE_WINDOW)
    limiter.record(address)
    repo = UserRepository(db)
    user = await repo.use_reset_attempt(req.email, MAX_RESET_ATTEMPTS)  # None: unknown email, no code pending, or all tries used
    if not user:
        raise api_error(status_code=400, code=INVALID_RESET_CODE)

    if not hmac.compare_digest(user.reset_token or "", _otp_hash(req.email, req.otp_code.strip())):
        raise api_error(status_code=400, code=INVALID_RESET_CODE)

    expires_at = user.reset_token_expires_at
    if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not expires_at or datetime.now(timezone.utc) > expires_at:
        raise api_error(status_code=400, code=INVALID_RESET_CODE)

    new_hash = await asyncio.to_thread(get_password_hash, req.new_password)
    await repo.update_password(user.user_id, new_hash)
    background.add_task(email_service.send_password_changed_notification, to_email=user.email, full_name=user.full_name or user.username)

    return {"success": True}


# ==============================================================================
# FUNCTION: change_password
# ==============================================================================
@router.post("/change-password")
async def change_password(
    request: Request,
    response: Response,
    req: ChangePasswordRequest,
    background: BackgroundTasks,
    current_user: UserRecord = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Change password for the authenticated user."""
    if not await asyncio.to_thread(verify_password, req.old_password, current_user.hashed_password):
        raise api_error(status_code=400, code=Code.WRONG_CURRENT_PASSWORD)

    repo = UserRepository(db)
    new_hash = await asyncio.to_thread(get_password_hash, req.new_password)
    await repo.update_password(current_user.user_id, new_hash)
    background.add_task(email_service.send_password_changed_notification, to_email=current_user.email, full_name=current_user.full_name or current_user.username)

    # Older tokens have just stopped working: this device gets a new one and stays signed in
    token = create_access_token(current_user.user_id, version=current_user.token_version + 1)
    _set_session_cookie(request, response, token)
    return {"success": True, "access_token": token}


# ==============================================================================
# FUNCTION: logout
# ==============================================================================
@router.post("/logout")
async def logout(
    response: Response,
    token: Optional[str] = Depends(read_token),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """End this session on the server: a copy of the token stops working, the account's other devices stay signed in."""
    response.delete_cookie(SESSION_COOKIE, path=SESSION_COOKIE_PATH, httponly=True, samesite="strict")
    try:
        claims = jwt.decode(token or "", settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:  # nothing valid to end: the browser is signed out either way
        return {"success": True}
    if claims.get("sub") and claims.get("jti"):
        await UserRepository(db).revoke_token(claims["sub"], claims["jti"])
    return {"success": True}
