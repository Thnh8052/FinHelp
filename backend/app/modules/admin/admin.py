"""
API Router: Quản Trị Viên (Admin RBAC)
Tác giả: Vũ Thành - FinAnalyst AI

Mọi endpoint ở đây yêu cầu role == 'admin' (require_admin). Đường dẫn giữ nguyên tiền tố /auth/admin cho Frontend.
1. Dashboard giám sát hệ thống (GET /api/v1/auth/admin/dashboard).
2. Số liệu cho trang /admin: lượt hỏi, token, trạng thái xử lý PDF, câu trả lời bị đánh dấu sai (GET /api/v1/auth/admin/overview).
3. Điều chỉnh gói hạn mức của người dùng (POST /api/v1/auth/admin/update-tier).
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.error_codes import Code, api_error
from app.shared.deps import require_admin
from app.shared.health import check_services
from app.infrastructure.database.mongodb import get_database
from app.modules.auth.user_repo import UserRepository
from app.modules.auth.user import UserRecord
from app.modules.admin.overview import build_overview
from app.modules.admin.review import LABELS, open_count, review_queue, set_review

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


@router.get("/overview")
async def get_admin_overview(
    days: int = Query(14, ge=7, le=90),
    user: Optional[str] = Query(None, max_length=64, description="One user's id, or \"guests\"; every user when left out"),
    current_user: UserRecord = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Every number of the admin dashboard in one read-only request; `days` is the window of the charts and the audit list, `user` narrows the
    questions, tokens, documents and answers to one user's chats (the user list stays whole)."""
    overview = await build_overview(db, days, user)
    overview["review_open"] = await open_count(db, days, user)  # answers waiting for the admin (review queue)
    services = await check_services()
    overview["services"] = services  # latency in ms per service, None when it did not answer
    return overview


@router.get("/review")
async def get_review_queue(
    days: int = Query(14, ge=1, le=90),
    label: Optional[Literal[tuple(LABELS)]] = Query(None, description="One problem; every problem when left out"),  # type: ignore[valid-type]
    user: Optional[str] = Query(None, max_length=64, description="One user's id, or \"guests\""),
    status: Literal["open", "reviewed", "all"] = Query("open"),
    current_user: UserRecord = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """The answers with a problem (review.PROBLEMS: reported by the user, shown with a warning, blocked, not found, partial, degraded, turned away,
    slow), newest first, with the number of open ones per problem."""
    return await review_queue(db, days=days, label=label, user=user, status=status)


class ReviewRequest(BaseModel):
    status: Literal["ok", "needs_fix", "open"]
    note: str = Field(default="", max_length=2000)


@router.post("/review/{message_id}")
async def review_answer(
    message_id: str,
    req: ReviewRequest,
    current_user: UserRecord = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """The admin's verdict on an answer of the queue ("ok", "needs_fix" with a note), or "open" to put it back."""
    if not await set_review(db, message_id, req.status, req.note, reviewer=current_user.username):
        raise api_error(status_code=404, code=Code.MESSAGE_NOT_FOUND)
    return {"success": True}


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
