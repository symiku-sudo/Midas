from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.response import error_response


class AccessTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = get_settings().auth.access_token.strip()
        if not token or request.url.path == "/health" or request.method == "OPTIONS":
            return await call_next(request)

        provided = self._extract_token(request)
        if provided and hmac.compare_digest(provided, token):
            return await call_next(request)

        request_id = getattr(request.state, "request_id", "")
        payload = error_response(
            code=ErrorCode.AUTH_EXPIRED,
            message="访问令牌无效或缺失。",
            request_id=request_id,
        )
        return JSONResponse(status_code=401, content=payload)

    def _extract_token(self, request) -> str:
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        return request.headers.get("X-Midas-Token", "").strip()
