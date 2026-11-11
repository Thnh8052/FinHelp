from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.shared.common import BaseSchema, get_utc_now


# Bảng cấu hình hạn mức tài nguyên: Chưa đăng nhập (Guest) vs Đã đăng nhập (User)
TIER_SPECS = {
    "guest": {
        "tier_name": "Chưa đăng nhập (Khách dùng thử)",
        "max_upload_documents": 1,
        "max_file_size_mb": 5,
        "cost_description": "Chế độ dùng thử (Tối đa 1 tài liệu)",
    },
    "user": {
        "tier_name": "Đã đăng nhập (Thành viên)",
        "daily_messages_limit": 100,
        "max_upload_documents": 5,
        "max_file_size_mb": 20,
        "cost_description": "Không gian phân tích (Tối đa 5 tài liệu / 1 Notebook)",
    },
    "admin": {
        "tier_name": "Quản Trị Viên (Full Quyền)",
        "daily_messages_limit": 10000,
        "max_upload_documents": 50,
        "max_file_size_mb": 100,
        "cost_description": "Toàn quyền quản trị, không giới hạn tài liệu & câu hỏi",
    },
}


def tier_spec(role: Optional[str]) -> dict:
    """The limits of an account by its role; None is a guest."""
    return TIER_SPECS["guest"] if role is None else TIER_SPECS.get(role, TIER_SPECS["user"])


def today_utc() -> datetime:
    """00:00 UTC of the current day: the start of the daily question window."""
    return get_utc_now().replace(hour=0, minute=0, second=0, microsecond=0)


class UserQuota(BaseModel):
    """Hạn mức trả về cho giao diện. Không lưu trong MongoDB: các giới hạn tra từ TIER_SPECS theo role, số đếm nằm trên UserRecord."""

    tier: str = "user"
    daily_messages_limit: int = 100
    messages_used_today: int = 0
    max_upload_documents: int = 5
    max_file_size_mb: int = 20
    total_tokens_consumed: int = 0


class UserRecord(BaseSchema):
    """User account record stored in MongoDB `users` collection (registered accounts only, guests are never stored here)."""

    user_id: str = Field(..., description="Unique user ID (usr_001)")
    email: EmailStr
    username: str
    hashed_password: str
    full_name: Optional[str] = None

    # Phân quyền SaaS: chỉ phân chia 'user' (người dùng ứng dụng) và 'admin' (quản trị viên)
    role: str = Field(
        default="user",
        description="'admin' (quản trị, xem performance, chi phí API, quản lý user) hoặc 'user' (sử dụng tính năng mở khóa)",
    )

    # Hạn mức theo ngày: daily_window_start là 00:00 UTC của ngày đang đếm; sang ngày mới thì đếm lại (consume_quota)
    daily_messages_limit: int = TIER_SPECS["user"]["daily_messages_limit"]
    daily_messages_used: int = 0
    daily_window_start: Any = Field(default_factory=today_utc)
    total_tokens_consumed: int = 0

    is_active: bool = True
    token_version: int = 0  # moves when the password changes: every token issued before that stops working
    revoked_token_ids: List[str] = Field(default_factory=list)  # tokens ended one by one (sign-out); the newest few are enough, the others have expired
    created_at: Any = Field(default_factory=get_utc_now)
    updated_at: Optional[Any] = None
    last_login_at: Optional[Any] = None

    # Khôi phục mật khẩu (Forgot/Reset Password)
    reset_token: Optional[str] = None  # keyed hash of the OTP (auth.py: _otp_hash), never the code itself
    reset_token_expires_at: Optional[Any] = None
    reset_attempts: int = 0  # codes tried against the current OTP; it dies after MAX_RESET_ATTEMPTS

    @field_validator("email", "username", mode="before")
    @classmethod
    def _lowercase(cls, value: Any) -> Any:
        """One account per name whatever its case: A@x.com and a@x.com are the same person."""
        return value.strip().lower() if isinstance(value, str) else value

    def messages_used_today(self) -> int:
        """The counter of the current day: a window from an earlier day counts as nothing used yet."""
        start = self.daily_window_start
        if start.tzinfo is None:  # MongoDB returns naive UTC datetimes
            start = start.replace(tzinfo=timezone.utc)
        return self.daily_messages_used if start >= today_utc() else 0

    @property
    def quota(self) -> UserQuota:
        spec = tier_spec(self.role)
        return UserQuota(
            tier=self.role,
            daily_messages_limit=self.daily_messages_limit,
            messages_used_today=self.messages_used_today(),
            max_upload_documents=spec["max_upload_documents"],
            max_file_size_mb=spec["max_file_size_mb"],
            total_tokens_consumed=self.total_tokens_consumed,
        )
