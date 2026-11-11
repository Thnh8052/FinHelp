"""
Tài khoản Admin duy nhất của hệ thống (FinAnalyst-AI), tạo hoặc cập nhật mỗi lần server khởi động:
- user_id ADMIN_USER_ID, username ADMIN_USERNAME, email ADMIN_EMAIL (auth/user.py; không ai đăng ký được hai tên này)
- Mật khẩu: settings.ADMIN_PASSWORD (biến môi trường; không đặt thì không tạo / không đổi tài khoản admin)
- Role: admin (Full quyền quản trị, cùng giới hạn tài liệu với người dùng, 10,000 câu hỏi/ngày)
Chỉ chạy khi server khởi động, không có endpoint HTTP nào gọi được. Không xoá tài khoản hay notebook nào.
"""

from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.logging import logger
from app.core.security import get_password_hash, verify_password
from app.infrastructure.database.mongodb import MongoManager
from app.modules.notebooks.notebook_repo import NotebookRepository
from app.modules.auth.user_repo import UserRepository
from app.modules.notebooks.notebook import NotebookRecord
from app.modules.auth.user import ADMIN_EMAIL, ADMIN_USER_ID, ADMIN_USERNAME, TIER_SPECS, UserRecord

ADMIN_FULL_NAME = "Vũ Thành (Quản Trị Viên Full Quyền)"
ADMIN_NOTEBOOK_ID = "nb_admin_sec_10k"


async def ensure_admin() -> dict:
    """Đảm bảo tài khoản Admin tồn tại với đầy đủ quyền hạn. Tìm theo user_id cố định, không theo username: một người dùng thường
    tên "admin" (đăng ký khi server chạy thiếu ADMIN_PASSWORD) không bao giờ bị nâng thành admin."""
    if MongoManager.db is None:
        logger.warning("MongoDB chưa kết nối, không thể khởi tạo Admin.")
        return {"success": False, "detail": "MongoDB disconnected"}
    if not settings.ADMIN_PASSWORD:
        logger.warning("ADMIN_PASSWORD is not set: the admin account was not created or changed.")
        return {"success": False, "detail": "ADMIN_PASSWORD is not set"}

    db = MongoManager.db
    user_repo = UserRepository(db)
    admin_limit = TIER_SPECS["admin"]["daily_messages_limit"]
    admin_user = await user_repo.get_by_id(ADMIN_USER_ID)

    if not admin_user:
        try:
            await user_repo.save_user(UserRecord(
                user_id=ADMIN_USER_ID,
                email=ADMIN_EMAIL,
                username=ADMIN_USERNAME,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                full_name=ADMIN_FULL_NAME,
                role="admin",
                daily_messages_limit=admin_limit,
                is_active=True,
            ))
        except DuplicateKeyError:
            logger.error(f"The username '{ADMIN_USERNAME}' or the email {ADMIN_EMAIL} belongs to another account: the admin account "
                         "was not created and nobody was given admin rights. Rename or remove that account, then restart.")
            return {"success": False, "detail": "admin username or email taken by another account"}
        logger.info("Admin user 'admin' created with full permissions.")
    else:
        password_changed = not verify_password(settings.ADMIN_PASSWORD, admin_user.hashed_password)
        changes = {"role": "admin", "full_name": ADMIN_FULL_NAME, "daily_messages_limit": admin_limit, "is_active": True}
        if password_changed:
            changes["hashed_password"] = get_password_hash(settings.ADMIN_PASSWORD)
        # A new ADMIN_PASSWORD ends the admin's old sessions; a plain restart with the same one does not
        await user_repo.collection.update_one(
            {"user_id": ADMIN_USER_ID}, {"$set": changes, "$inc": {"token_version": 1 if password_changed else 0}}
        )
        logger.info("Admin user 'admin' updated with full permissions.")

    # Workspace Notebook chính thức của Admin
    notebook_repo = NotebookRepository(db)
    if not await notebook_repo.get_by_id(ADMIN_NOTEBOOK_ID):
        await notebook_repo.save_notebook(NotebookRecord(notebook_id=ADMIN_NOTEBOOK_ID, owner_id=ADMIN_USER_ID, title="Phân Tích Báo Cáo Tài Chính"))

    return {
        "success": True,
        "message": "Admin account initialized with full permissions.",
        "admin": {"username": ADMIN_USERNAME, "role": "admin", "tier": "admin", "notebook_id": ADMIN_NOTEBOOK_ID},
    }
