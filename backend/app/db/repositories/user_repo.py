"""
Data Access Layer (Repository) cho Người Dùng & Hạn Mức trong MongoDB
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Tương tác trực tiếp với MongoDB collection `users`.
2. Truy vấn người dùng theo ID, Email, Username hoặc cả hai.
3. Quản lý trạng thái xác thực: cập nhật mật khẩu, ghi nhận lần đăng nhập cuối, mã OTP reset token.
4. Quản lý hạn mức Quota: cộng dồn số câu hỏi, lượng tokens tiêu thụ và chi phí API vào MongoDB.
5. Cung cấp dữ liệu thống kê tổng hợp (aggregation) cho màn hình Admin Dashboard.
"""

from typing import Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.common import get_utc_now
from app.models.user import TIER_SPECS, UserRecord


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
        doc = await self.find_one({"email": email})
        return UserRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: get_by_username
    # Ý NGHĨA: Tìm kiếm tài khoản dựa trên tên đăng nhập username (kiểm tra tính duy nhất khi tạo tài khoản).
    # ĐẦU VÀO: username (str)
    # ĐẦU RA: UserRecord (nếu tìm thấy) hoặc None
    # ==============================================================================
    async def get_by_username(self, username: str) -> Optional[UserRecord]:
        doc = await self.find_one({"username": username})
        return UserRecord(**doc) if doc else None

    # ==============================================================================
    # HÀM: get_by_email_or_username
    # Ý NGHĨA: Tìm kiếm tài khoản hỗ trợ người dùng đăng nhập bằng cả email hoặc username tùy ý.
    # ĐẦU VÀO: identifier (str) - có thể là email hoặc username
    # ĐẦU RA: UserRecord (nếu tìm thấy) hoặc None
    # ==============================================================================
    async def get_by_email_or_username(self, identifier: str) -> Optional[UserRecord]:
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
    # Ý NGHĨA: Lưu mã OTP khôi phục mật khẩu 6 số kèm thời gian hết hạn (15 phút) vào MongoDB.
    # ĐẦU VÀO: email (str), reset_token (str), expires_at (datetime)
    # ĐẦU RA: bool
    # ==============================================================================
    async def set_reset_token(self, email: str, reset_token: str, expires_at: Any) -> bool:
        updated = await self.update_one(
            {"email": email},
            {
                "reset_token": reset_token,
                "reset_token_expires_at": expires_at,
                "updated_at": get_utc_now(),
            },
        )
        return updated > 0

    # ==============================================================================
    # HÀM: get_by_reset_token
    # Ý NGHĨA: Tìm kiếm người dùng dựa trên mã OTP / reset token.
    # ĐẦU VÀO: reset_token (str)
    # ĐẦU RA: UserRecord hoặc None
    # ==============================================================================
    async def get_by_reset_token(self, reset_token: str) -> Optional[UserRecord]:
        doc = await self.find_one({"reset_token": reset_token})
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
        docs = await self.find_many({}, limit=limit, skip=skip, sort=[("created_at", -1)])
        return [UserRecord(**d) for d in docs]

    # ==============================================================================
    # HÀM: increment_quota_usage
    # Ý NGHĨA: Thực hiện phép toán nguyên tử ($inc trong MongoDB) để cộng dồn số câu hỏi,
    #          tổng lượng tokens LLM tiêu thụ và chi phí USD đã sử dụng.
    # ĐẦU VÀO: user_id (str), messages (int), tokens (int), cost_usd (float)
    # ĐẦU RA: bool
    # ==============================================================================
    async def increment_quota_usage(
        self, user_id: str, messages: int = 1, tokens: int = 0, cost_usd: float = 0.0
    ) -> bool:
        updated = await self.collection.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "quota.messages_used_today": messages,
                    "quota.total_tokens_consumed": tokens,
                    "quota.total_cost_usd": cost_usd,
                },
                "$set": {"updated_at": get_utc_now()},
            },
        )
        return updated.modified_count > 0

    # ==============================================================================
    # HÀM: update_user_tier
    # Ý NGHĨA: Cập nhật hạn mức tài khoản theo chính sách ("guest" hoặc "user").
    # ĐẦU VÀO: user_id (str), tier (str)
    # ĐẦU RA: bool
    # ==============================================================================
    async def update_user_tier(self, user_id: str, tier: str = "user") -> bool:
        spec = TIER_SPECS.get(tier, TIER_SPECS["user"])
        new_quota = {
            "tier": tier,
            "daily_messages_limit": spec.get("daily_messages_limit", TIER_SPECS["user"]["daily_messages_limit"]),  # the guest tier has no question limit
            "max_upload_documents": spec["max_upload_documents"],
            "max_file_size_mb": spec["max_file_size_mb"],
        }

        update_fields = {f"quota.{k}": v for k, v in new_quota.items()}
        update_fields["updated_at"] = get_utc_now()
        updated = await self.collection.update_one({"user_id": user_id}, {"$set": update_fields})
        return updated.modified_count > 0

    # ==============================================================================
    # HÀM: get_admin_dashboard_stats
    # Ý NGHĨA: Tổng hợp số liệu thống kê toàn hệ thống bằng MongoDB Aggregation Pipeline:
    #          Tổng số người dùng, người dùng hoạt động, phân loại vai trò, tổng tokens và chi phí USD.
    # ĐẦU RA: dict chứa các chỉ số thống kê tổng hợp
    # ==============================================================================
    async def get_admin_dashboard_stats(self) -> dict:
        total_users = await self.collection.count_documents({})
        active_users = await self.collection.count_documents({"is_active": True})
        admin_users = await self.collection.count_documents({"role": "admin"})
        standard_users = await self.collection.count_documents({"role": "user"})

        # Pipeline tính tổng tokens và chi phí API trên toàn bộ tài khoản
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_tokens": {"$sum": "$quota.total_tokens_consumed"},
                    "total_cost": {"$sum": "$quota.total_cost_usd"},
                }
            }
        ]
        agg_result = await self.collection.aggregate(pipeline).to_list(1)
        total_tokens = agg_result[0]["total_tokens"] if agg_result else 0
        total_cost = agg_result[0]["total_cost"] if agg_result else 0.0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "tier_breakdown": {
                "user": standard_users,
                "admin": admin_users,
            },
            "api_metrics": {
                "total_tokens_consumed": total_tokens,
                "total_estimated_cost_usd": round(total_cost, 4),
            },
        }
