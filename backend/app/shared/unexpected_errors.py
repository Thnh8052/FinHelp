"""Turn an unforeseen error into a JSON answer that names a request id, so a report from a user can be found in the log.

A middleware and not app.exception_handler(Exception): Starlette runs that handler outside every middleware, so its answer would carry no CORS
headers and the browser would hide it. Add this one before CORSMiddleware (the last one added is the outermost).
"""
import uuid

from starlette.responses import JSONResponse

from app.core.error_codes import Code
from app.core.logging import logger


class UnexpectedErrors:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = False

        async def watching_send(message):
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, watching_send)
        except Exception:
            request_id = uuid.uuid4().hex[:12]
            logger.exception(f"Unhandled error [{request_id}] {scope['method']} {scope['path']}")
            if started:  # part of the answer has already left: nothing valid can be sent any more
                raise
            body = {"detail": {"code": Code.INTERNAL_ERROR, "params": {}}, "request_id": request_id}
            await JSONResponse(body, status_code=500)(scope, receive, send)
