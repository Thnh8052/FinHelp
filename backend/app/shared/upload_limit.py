"""Refuse an oversized upload from its Content-Length, before the server reads the body to its temporary folder.

FastAPI parses the whole request before calling the route, so the per-account limit in upload_pdf cannot protect the disk on its own.
This ceiling is the largest limit of any account; upload_pdf then applies the caller's own limit.
"""
from starlette.responses import JSONResponse

from app.modules.auth.user import TIER_SPECS

UPLOAD_PATH = "/documents/upload/"
MULTIPART_OVERHEAD = 1024 * 1024
MAX_UPLOAD_BODY = max(spec["max_file_size_mb"] for spec in TIER_SPECS.values()) * 1024 * 1024 + MULTIPART_OVERHEAD


class UploadSizeLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and UPLOAD_PATH in scope["path"]:
            length = dict(scope["headers"]).get(b"content-length", b"")
            if not length.isdigit():
                await JSONResponse({"detail": "Thiếu độ dài của tệp tải lên."}, status_code=411)(scope, receive, send)
                return
            if int(length) > MAX_UPLOAD_BODY:
                await JSONResponse({"detail": "Dung lượng tệp vượt quá giới hạn cho phép."}, status_code=413)(scope, receive, send)
                return
        await self.app(scope, receive, send)
