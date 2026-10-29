"""
Module khởi tạo & quản trị tài khoản Admin hệ thống (FinAnalyst-AI)
Xóa sạch dữ liệu tài khoản mock cũ và khởi tạo tài khoản admin full quyền duy nhất:
- Username: admin
- Mật khẩu: settings.ADMIN_PASSWORD (biến môi trường; không đặt thì không tạo / không đổi tài khoản admin)
- Role: admin (Full quyền quản trị, upload tới 50 documents, 10,000 queries/ngày)
Chỉ chạy khi server khởi động, không có endpoint HTTP nào gọi được.
"""

from app.core.config import settings
from app.core.logging import logger
from app.core.security import get_password_hash
from app.db.mongodb import MongoManager
from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.notebook_repo import NotebookRepository
from app.db.repositories.user_repo import UserRepository
from app.models.chat import ChatSessionRecord
from app.models.notebook import NotebookRecord
from app.models.user import UserQuota, UserRecord


async def setup_admin_and_clean_mocks() -> dict:
    """Xóa bỏ tài khoản mock cũ và đảm bảo tài khoản Admin tồn tại với đầy đủ quyền hạn."""
    if MongoManager.db is None:
        logger.warning("MongoDB chưa kết nối, không thể khởi tạo Admin.")
        return {"success": False, "detail": "MongoDB disconnected"}

    db = MongoManager.db
    user_repo = UserRepository(db)
    notebook_repo = NotebookRepository(db)
    chat_repo = ChatRepository(db)

    # 1. Dọn dẹp các tài khoản Mock cũ trong collection `users`
    mock_usernames = ["analyst_demo", "user_free", "usr_demo_001", "usr_free_01"]
    delete_result = await user_repo.collection.delete_many({
        "$or": [
            {"username": {"$in": mock_usernames}},
            {"email": {"$in": ["member@finanalyst.ai"]}},
        ]
    })
    logger.info(f"Purged {delete_result.deleted_count} mock users from database.")

    # 2. Xóa các notebook mock cũ không thuộc về admin mới
    await notebook_repo.collection.delete_many({
        "notebook_id": {"$in": ["nb_demo_001", "nb_vuthanh_01"]}
    })
    await chat_repo.collection.delete_many({
        "session_id": {"$in": ["ses_vuthanh_01", "ses_demo_001"]}
    })

    # 3. Tạo hoặc cập nhật tài khoản Admin Full Quyền (cần ADMIN_PASSWORD: không có mật khẩu mặc định)
    if not settings.ADMIN_PASSWORD:
        logger.warning("ADMIN_PASSWORD is not set: the admin account was not created or changed.")
        return {"success": False, "detail": "ADMIN_PASSWORD is not set"}
    admin_user = await user_repo.get_by_username("admin")
    admin_quota = UserQuota(
        tier="admin",
        daily_messages_limit=10000,
        messages_used_today=0,
        max_upload_documents=50,
        max_file_size_mb=100,
        total_tokens_consumed=0,
        total_cost_usd=0.0,
    )

    admin_record = UserRecord(
        user_id="usr_admin_master",
        email="admin@finanalyst.ai",
        username="admin",
        hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
        full_name="Vũ Thành (Quản Trị Viên Full Quyền)",
        role="admin",
        quota=admin_quota,
        is_active=True,
    )

    if not admin_user:
        await user_repo.save_user(admin_record)
        logger.info("Admin user 'admin' created with full permissions.")
    else:
        # Cập nhật thông tin và đảm bảo mật khẩu & quyền admin
        await user_repo.collection.update_one(
            {"user_id": admin_user.user_id},
            {
                "$set": {
                    "hashed_password": get_password_hash(settings.ADMIN_PASSWORD),
                    "role": "admin",
                    "full_name": "Vũ Thành (Quản Trị Viên Full Quyền)",
                    "quota": admin_quota.model_dump(),
                    "is_active": True,
                }
            },
        )
        logger.info("Admin user 'admin' updated with full permissions.")

    # 4. Đảm bảo có Workspace Notebook chính thức cho Admin
    admin_nb_id = "nb_admin_sec_10k"
    existing_nb = await notebook_repo.get_by_id(admin_nb_id)
    if not existing_nb:
        admin_notebook = NotebookRecord(
            notebook_id=admin_nb_id,
            user_id="usr_admin_master",
            title="Phân Tích Báo Cáo Tài Chính",
            description="Không gian làm việc chính thức phân tích báo cáo tài chính doanh nghiệp.",
            tags=["Báo cáo tài chính", "Admin Workspace"],
            document_ids=[],
        )
        await notebook_repo.save_notebook(admin_notebook)

    # 5. Đảm bảo có Chat Session khởi đầu cho Admin
    admin_ses_id = "ses_admin_sec_main"
    existing_ses = await chat_repo.get_session(admin_ses_id)
    if not existing_ses:
        admin_session = ChatSessionRecord(
            session_id=admin_ses_id,
            notebook_id=admin_nb_id,
            user_id="usr_admin_master",
            title="Đoạn chat phân tích ban đầu",
        )
        await chat_repo.save_session(admin_session)

    return {
        "success": True,
        "message": "Admin account initialized with full permissions. Mock accounts deleted.",
        "admin": {
            "username": "admin",
            "role": "admin",
            "tier": "admin",
            "notebook_id": admin_nb_id,
            "session_id": admin_ses_id,
        },
    }
