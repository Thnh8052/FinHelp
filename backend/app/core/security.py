"""
Module Bảo Mật & Xác Thực (Security & Cryptography)
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Băm mật khẩu (Password Hashing) bằng thuật toán an toàn bcrypt với chuỗi salt ngẫu nhiên.
2. Kiểm tra tính hợp lệ của mật khẩu người dùng khi đăng nhập.
3. Sinh mã JSON Web Token (JWT) có thời hạn (Access Token) phục vụ xác thực người dùng không trạng thái (stateless auth).
"""

import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from jose import jwt
from app.core.config import settings


# ==============================================================================
# HÀM: verify_password
# Ý NGHĨA: Xác minh mật khẩu thô người dùng nhập vào có khớp với mật khẩu băm lưu trong MongoDB hay không.
# ĐẦU VÀO:
#   - plain_password: Mật khẩu dạng văn bản thô do người dùng nhập.
#   - hashed_password: Chuỗi mật khẩu đã băm (bcrypt) lưu trong CSDL.
# ĐẦU RA:
#   - bool: True nếu mật khẩu chính xác, False nếu sai hoặc xảy ra lỗi giải mã.
# ==============================================================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Giới hạn 72 byte để tuân thủ đặc tả an toàn của thư viện bcrypt
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ==============================================================================
# HÀM: get_password_hash
# Ý NGHĨA: Băm mật khẩu người dùng trước khi lưu trữ vào cơ sở dữ liệu MongoDB.
# ĐẦU VÀO:
#   - password: Mật khẩu dạng thô người dùng đăng ký hoặc đổi mật khẩu.
# ĐẦU RA:
#   - str: Chuỗi mật khẩu băm bcrypt an toàn (kèm salt ngẫu nhiên) để lưu vào DB.
# ==============================================================================
def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")


# ==============================================================================
# HÀM: create_access_token
# Ý NGHĨA: Tạo mã JWT Bearer Token chứa mã định danh người dùng (subject = user_id) và hạn sử dụng (exp).
# ĐẦU VÀO:
#   - subject: Mã định danh người dùng (user_id).
#   - expires_delta: Thời gian hết hạn tùy chỉnh (nếu không truyền, mặc định theo cấu hình hệ thống).
# ĐẦU RA:
#   - str: Chuỗi JWT đã ký điện tử bằng khóa bí mật bí mật (SECRET_KEY) và thuật toán mã hóa (ALGORITHM).
# ==============================================================================
def create_access_token(subject: str | Any, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
