"""
Data Access Layer (Repository) cho Người Dùng & Hạn Mức trong MongoDB
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Tương tác trực tiếp với MongoDB collection `users`.
2. Truy vấn người dùng theo ID, Email, Username hoặc cả hai.
3. Quản lý trạng thái xác thực: cập nhật mật khẩu, ghi nhận lần đăng nhập cuối, mã OTP reset token.
4. Quản lý hạn mức Quota: đếm số câu hỏi theo ngày và cộng dồn lượng tokens tiêu thụ.
5. Cung cấp dữ liệu thống kê tổng hợp (aggregation) cho màn hình Admin Dashboard.
"""

from typing import Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from app.infrastructure.database import collections
from app.shared.base_repo import BaseRepository
from app.shared.common import get_utc_now
from app.modules.auth.user import TIER_SPECS, UserRecord, today_utc


class UserRepository(BaseRepository):
    """Lớp xử lý dữ liệu người dùng (User Repository) kết nối MongoDB collection `users`."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.USERS_COLLECTION)

    # ==============================================================================
    # HÀM: get_by_id
    # Ý NGHĨA: Tìm kiếm thông tin người dùng trong MongoDB dựa trên mã định danh user_id.
    # ĐẦU VÀO: user_id (str)
    # ĐẦU RA: UserRecord (nếu tìm thấy) hoặc None
    # ==============================================================================
    async def get_by_id(self, user_id: str) -> Optional[UserRecord]:
        doc = await self.find_one({"user_id": user_id})
        return UserRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: get_by_email
    # Ý NGHĨA: Tìm kiếm tài khoản dựa trên địa chỉ email (phục vụ đăng ký kiểm tra trùng lặp và quên mật khẩu).
    # ĐẦU VÀO: email (str)
    # ĐẦU RA: UserRecord (nếu tìm thấy) hoặc None
    # ==============================================================================
    async def get_by_email(self, email: str) -> Optional[UserRecord]:
        doc = await self.find_one({"email": email.strip().lower()})
        return UserRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: get_by_username
    # Ý NGHĨA: Tìm kiếm tài khoản dựa trên tên đăng nhập username (kiểm tra tính duy nhất khi tạo tài khoản).
    # ĐẦU VÀO: username (str)
    # ĐẦU RA: UserRecord (nếu tìm thấy) hoặc None
    # ==============================================================================
    async def get_by_username(self, username: str) -> Optional[UserRecord]:
        doc = await self.find_one({"username": username.strip().lower()})
        return UserRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: get_by_email_or_username
    # Ý NGHĨA: Tìm kiếm tài khoản hỗ trợ người dùng đăng nhập bằng cả email hoặc username tùy ý.
    # ĐẦU VÀO: identifier (str) - có thể là email hoặc username
    # ĐẦU RA: UserRecord (nếu tìm thấy) hoặc None
    # ==============================================================================
    async def get_by_email_or_username(self, identifier: str) -> Optional[UserRecord]:
        identifier = identifier.strip().lower()
        doc = await self.find_one({"$or": [{"email": identifier}, {"username": identifier}]})
        return UserRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: save_user
    # Ý NGHĨA: Lưu bản ghi tài khoản người dùng mới vào MongoDB collection `users`.
    # ĐẦU VÀO: user (UserRecord)
    # ĐẦU RA: str (ID bản ghi chèn thành công)
    # ==============================================================================
    async def save_user(self, user: UserRecord) -> str:
        return await self.insert_one(user.model_dump())

    # ==============================================================================
    # HÀM: update_password
    # Ý NGHĨA: Cập nhật mật khẩu băm mới cho tài khoản và tự động xóa mã reset_token tạm thời.
    # ĐẦU VÀO: user_id (str), new_hashed_password (str)
    # ĐẦU RA: bool (True nếu cập nhật thành công)
    # ==============================================================================
    async def update_password(self, user_id: str, new_hashed_password: str) -> bool:
        updated = await self.update_one(
            {"user_id": user_id},
            {
                "hashed_password": new_hashed_password,
                "reset_token": None,
                "reset_token_expires_at": None,
                "reset_attempts": 0,
                "updated_at": get_utc_now(),
            },
        )
        return updated > 0

    # ==============================================================================
    # HÀM: update_last_login
    # Ý NGHĨA: Ghi nhận mốc thời gian UTC mà người dùng đăng nhập thành công vào hệ thống.
    # ĐẦU VÀO: user_id (str)
    # ĐẦU RA: bool
    # ==============================================================================
    async def update_last_login(self, user_id: str) -> bool:
        updated = await self.update_one(
            {"user_id": user_id},
            {"last_login_at": get_utc_now()},
        )
        return updated > 0

    # ==============================================================================
    # HÀM: set_reset_token
    # Ý NGHĨA: Lưu mã băm của OTP khôi phục mật khẩu kèm thời hạn, và đặt lại số lần thử về 0.
    # ĐẦU VÀO: email (str), reset_token (str: mã băm, không phải mã OTP), expires_at (datetime)
    # ĐẦU RA: bool
    # ==============================================================================
    async def set_reset_token(self, email: str, reset_token: str, expires_at: Any) -> bool:
        updated = await self.update_one(
            {"email": email.strip().lower()},
            {
                "reset_token": reset_token,
                "reset_token_expires_at": expires_at,
                "reset_attempts": 0,
                "updated_at": get_utc_now(),
            },
        )
        return updated > 0

    # ==============================================================================
    # HÀM: use_reset_attempt
    # Ý NGHĨA: Tính một lần thử mã OTP và trả về tài khoản; một lệnh nguyên tử nên các yêu cầu đồng thời không vượt được giới hạn.
    # ĐẦU RA: UserRecord, hoặc None khi không có OTP đang chờ hoặc đã hết lượt thử
    # ==============================================================================
    async def use_reset_attempt(self, email: str, max_attempts: int) -> Optional[UserRecord]:
        doc = await self.collection.find_one_and_update(
            {"email": email.strip().lower(), "reset_token": {"$ne": None}, "reset_attempts": {"$lt": max_attempts}},
            {"$inc": {"reset_attempts": 1}},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        return UserRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: update_profile
    # Ý NGHĨA: Cập nhật thông tin cá nhân (họ tên hiển thị) của người dùng.
    # ĐẦU VÀO: user_id (str), full_name (Optional[str])
    # ĐẦU RA: bool
    # ==============================================================================
    async def update_profile(
        self, user_id: str, full_name: Optional[str] = None
    ) -> bool:
        update_data = {"updated_at": get_utc_now()}
        if full_name is not None:
            update_data["full_name"] = full_name

        updated = await self.update_one({"user_id": user_id}, update_data)
        return updated > 0

    # ==============================================================================
    # HÀM: list_users
    # Ý NGHĨA: Phân trang danh sách người dùng cho màn hình quản trị Admin.
    # ĐẦU VÀO: limit (int), skip (int)
    # ĐẦU RA: List[UserRecord]
    # ==============================================================================
    async def list_users(self, limit: int = 50, skip: int = 0) -> List[UserRecord]:
        docs = await self.find_many({}, limit=limit, skip=skip, sort_by=[("created_at", -1)])
        return [UserRecord(**d) for d in docs]

    # ==============================================================================
    # HÀM: check_quota / consume_quota
    # Ý NGHĨA: Hai điểm duy nhất của hạn mức: kiểm tra trước khi trả lời và ghi nhận sau khi trả lời.
    #          Khi đổi sang hạn mức theo token chỉ cần sửa ở đây.
    # ==============================================================================
    async def check_quota(self, user_id: str) -> bool:
        """True while the account may still ask today."""
        user = await self.get_by_id(user_id)
        return user is not None and user.messages_used_today() < user.daily_messages_limit

    async def consume_quota(self, user_id: str, messages: int = 1, tokens: int = 0) -> bool:
        """Count one request in a single atomic update; the first request of a new UTC day restarts the daily counter."""
        today = today_utc()
        new_day = {"$lt": ["$daily_window_start", today]}
        updated = await self.collection.update_one(
            {"user_id": user_id},
            [{
                "$set": {
                    "daily_messages_used": {"$cond": [new_day, messages, {"$add": ["$daily_messages_used", messages]}]},
                    "daily_window_start": {"$cond": [new_day, today, "$daily_window_start"]},
                    "total_tokens_consumed": {"$add": ["$total_tokens_consumed", tokens]},
                    "updated_at": get_utc_now(),
                }
            }],
        )
        return updated.modified_count > 0

    # ==============================================================================
    # HÀM: update_user_tier
    # Ý NGHĨA: Đặt hạn mức câu hỏi mỗi ngày của tài khoản theo chính sách của một gói.
    # ĐẦU VÀO: user_id (str), tier (str)
    # ĐẦU RA: bool
    # ==============================================================================
    async def update_user_tier(self, user_id: str, tier: str = "user") -> bool:
        spec = TIER_SPECS.get(tier, TIER_SPECS["user"])
        limit = spec.get("daily_messages_limit", TIER_SPECS["user"]["daily_messages_limit"])  # the guest tier has no question limit
        updated = await self.collection.update_one(
            {"user_id": user_id}, {"$set": {"daily_messages_limit": limit, "updated_at": get_utc_now()}}
        )
        return updated.matched_count > 0

    # ==============================================================================
    # HÀM: get_admin_dashboard_stats
    # Ý NGHĨA: Tổng hợp số liệu thống kê toàn hệ thống bằng MongoDB Aggregation Pipeline:
    #          Tổng số người dùng, người dùng hoạt động, phân loại vai trò và tổng tokens.
    # ĐẦU RA: dict chứa các chỉ số thống kê tổng hợp
    # ==============================================================================
    async def get_admin_dashboard_stats(self) -> dict:
        total_users = await self.collection.count_documents({})
        active_users = await self.collection.count_documents({"is_active": True})
        admin_users = await self.collection.count_documents({"role": "admin"})
        standard_users = await self.collection.count_documents({"role": "user"})

        # Pipeline tính tổng tokens trên toàn bộ tài khoản
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_tokens": {"$sum": "$total_tokens_consumed"},
                }
            }
        ]
        agg_result = await self.collection.aggregate(pipeline).to_list(1)
        total_tokens = agg_result[0]["total_tokens"] if agg_result else 0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "tier_breakdown": {
                "user": standard_users,
                "admin": admin_users,
            },
            "api_metrics": {
                "total_tokens_consumed": total_tokens,
            },
        }
