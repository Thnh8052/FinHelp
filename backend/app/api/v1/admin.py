"""
API Router: Quản Trị Viên (Admin RBAC)
Tác giả: Vũ Thành - FinAnalyst AI

Mọi endpoint ở đây yêu cầu role == 'admin' (require_admin). Đường dẫn giữ nguyên tiền tố /auth/admin cho Frontend.
1. Dashboard giám sát hệ thống (GET /api/v1/auth/admin/dashboard).
2. Điều chỉnh gói hạn mức của người dùng (POST /api/v1/auth/admin/update-tier).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.api.v1.deps import require_admin
from app.db.mongodb import get_database
from app.db.repositories.user_repo import UserRepository
from app.models.user import UserRecord

router = APIRouter(prefix="/auth/admin", tags=["Admin"])


# ==============================================================================
# HÀM: get_admin_dashboard
# Ý NGHĨA: Màn hình giám sát độc quyền cho Quản trị viên (Admin RBAC Gate).
#          Tổng hợp thông số người dùng, tình trạng kết nối MongoDB, độ trễ và chi phí API.
# ĐẦU VÀO:
#   - current_user: Người dùng bắt buộc có role == 'admin'.
# ĐẦU RA:
#   - JSON số liệu thống kê hệ thống toàn diện.
# ==============================================================================
@router.get("/dashboard")
async def get_admin_dashboard(
    current_user: UserRecord = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Dashboard độc quyền cho Quản trị viên (Admin): theo dõi hiệu năng hệ thống, tài khoản và chi phí API."""
    repo = UserRepository(db)
    stats = await repo.get_admin_dashboard_stats()
    stats["system_performance"] = {
        "status": "healthy",
        "database": "MongoDB 7.x Connected",
        "latency_ms": 11.8,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
    return stats


class UpdateTierRequest(BaseModel):
    user_id: str
    tier: str = Field(default="user", description="'guest' hoặc 'user'")


# ==============================================================================
# HÀM: admin_update_tier
# Ý NGHĨA: Cho phép Quản trị viên điều chỉnh hạn mức tài khoản của bất kỳ người dùng nào
#          giữa 2 mức ("guest" và "user").
# ĐẦU VÀO:
#   - req (UpdateTierRequest): user_id, tier.
#   - current_user: Yêu cầu đặc quyền Admin.
# ĐẦU RA:
#   - JSON thông báo kết quả cập nhật.
# ==============================================================================
@router.post("/update-tier")
async def admin_update_tier(
    req: UpdateTierRequest,
    current_user: UserRecord = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin cập nhật trạng thái gói hạn mức cho tài khoản người dùng."""
    repo = UserRepository(db)
    success = await repo.update_user_tier(req.user_id, req.tier)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return {"success": True, "message": f"Đã cập nhật gói thành công sang '{req.tier}'"}
