from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.common import BaseSchema, get_utc_now


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
# Alias tương thích ngược nếu bản ghi cũ lưu 'free'
TIER_SPECS["free"] = TIER_SPECS["user"]


class UserQuota(BaseModel):
    """Mô hình quản lý Hạn mức người dùng: no login (1 doc, 2 msgs) vs login (5 docs/notebook)."""

    tier: str = Field(default="user", description="'guest' (no login) hoặc 'user' (login)")
    daily_messages_limit: int = Field(default=100, description="Giới hạn số tin nhắn / lượt hỏi mỗi ngày")
    messages_used_today: int = Field(default=0, description="Số tin nhắn đã sử dụng trong ngày")
    max_upload_documents: int = Field(default=5, description="Số tài liệu tối đa tải lên mỗi Notebook (Giới hạn: 5)")
    max_file_size_mb: int = Field(default=20, description="Dung lượng tối đa mỗi file PDF/Excel (20MB)")
    total_tokens_consumed: int = Field(default=0, description="Tổng token AI đã sử dụng qua các API")
    total_cost_usd: float = Field(default=0.0, description="Ước tính chi phí API đã tiêu thụ (USD)")



class UserRecord(BaseSchema):
    """User account record stored in MongoDB `users` collection."""

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

    # Quota & Hạn mức tính năng mở khóa kiểu ChatGPT / Claude
    quota: UserQuota = Field(default_factory=UserQuota)

    is_active: bool = True
    created_at: Any = Field(default_factory=get_utc_now)
    updated_at: Optional[Any] = None
    last_login_at: Optional[Any] = None

    # Khôi phục mật khẩu (Forgot/Reset Password)
    reset_token: Optional[str] = None
    reset_token_expires_at: Optional[Any] = None

