"""Security headers on every answer. The strict content policy is for the API only: the /docs page has to load its own scripts."""
from starlette.datastructures import MutableHeaders

from app.core.config import settings

ONE_YEAR_SECONDS = 365 * 24 * 60 * 60


class SecurityHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                if scope["path"].startswith(settings.API_V1_STR):
                    headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                if scope["scheme"] == "https":
                    headers["Strict-Transport-Security"] = f"max-age={ONE_YEAR_SECONDS}"
            await send(message)

        await self.app(scope, receive, with_headers)
