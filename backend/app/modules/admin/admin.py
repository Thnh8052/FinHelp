"""
API Router: Quản Trị Viên (Admin RBAC)
Tác giả: Vũ Thành - FinAnalyst AI

Mọi endpoint ở đây yêu cầu role == 'admin' (require_admin). Đường dẫn giữ nguyên tiền tố /auth/admin cho Frontend.
1. Dashboard giám sát hệ thống (GET /api/v1/auth/admin/dashboard).
2. Điều chỉnh gói hạn mức của người dùng (POST /api/v1/auth/admin/update-tier).
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.error_codes import Code, api_error
from app.shared.deps import require_admin
from app.shared.health import check_services
from app.infrastructure.database.mongodb import get_database
from app.modules.auth.user_repo import UserRepository
from app.modules.auth.user import UserRecord

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
    services = await check_services()
    stats["system_performance"] = {
        "status": "healthy" if all(latency is not None for latency in services.values()) else "unhealthy",
        "database": "MongoDB Connected" if services["mongodb"] is not None else "MongoDB Unreachable",
        "latency_ms": services["mongodb"],
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
    return stats


class UpdateTierRequest(BaseModel):
    user_id: str
    tier: Literal["guest", "user", "admin"] = Field(default="user", description="Tên một gói có trong TIER_SPECS")


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
        raise api_error(status_code=404, code=Code.USER_NOT_FOUND)
    return {"success": True, "tier": req.tier}
