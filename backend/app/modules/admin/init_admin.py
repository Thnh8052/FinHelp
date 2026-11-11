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
from app.core.security import get_password_hash, verify_password
from app.infrastructure.database.mongodb import MongoManager
from app.modules.notebooks.notebook_repo import NotebookRepository
from app.modules.auth.user_repo import UserRepository
from app.modules.notebooks.notebook import NotebookRecord
from app.modules.auth.user import TIER_SPECS, UserRecord


async def setup_admin_and_clean_mocks() -> dict:
    """Xóa bỏ tài khoản mock cũ và đảm bảo tài khoản Admin tồn tại với đầy đủ quyền hạn."""
    if MongoManager.db is None:
        logger.warning("MongoDB chưa kết nối, không thể khởi tạo Admin.")
        return {"success": False, "detail": "MongoDB disconnected"}

    db = MongoManager.db
    user_repo = UserRepository(db)
    notebook_repo = NotebookRepository(db)

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

    # 3. Tạo hoặc cập nhật tài khoản Admin Full Quyền (cần ADMIN_PASSWORD: không có mật khẩu mặc định)
    if not settings.ADMIN_PASSWORD:
        logger.warning("ADMIN_PASSWORD is not set: the admin account was not created or changed.")
        return {"success": False, "detail": "ADMIN_PASSWORD is not set"}
    admin_user = await user_repo.get_by_username("admin")
    admin_limit = TIER_SPECS["admin"]["daily_messages_limit"]

    admin_record = UserRecord(
        user_id="usr_admin_master",
        email="admin@finanalyst.ai",
        username="admin",
        hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
        full_name="Vũ Thành (Quản Trị Viên Full Quyền)",
        role="admin",
        daily_messages_limit=admin_limit,
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
                    "daily_messages_limit": admin_limit,
                    "is_active": True,
                },
                # A new ADMIN_PASSWORD ends the admin's old sessions; a plain restart with the same one does not
                "$inc": {"token_version": 0 if verify_password(settings.ADMIN_PASSWORD, admin_user.hashed_password) else 1},
            },
        )
        logger.info("Admin user 'admin' updated with full permissions.")

    # 4. Đảm bảo có Workspace Notebook chính thức cho Admin
    admin_nb_id = "nb_admin_sec_10k"
    existing_nb = await notebook_repo.get_by_id(admin_nb_id)
    if not existing_nb:
        admin_notebook = NotebookRecord(
            notebook_id=admin_nb_id,
            owner_id="usr_admin_master",
            title="Phân Tích Báo Cáo Tài Chính",
        )
        await notebook_repo.save_notebook(admin_notebook)

    return {
        "success": True,
        "message": "Admin account initialized with full permissions. Mock accounts deleted.",
        "admin": {
            "username": "admin",
            "role": "admin",
            "tier": "admin",
            "notebook_id": admin_nb_id,
        },
    }
