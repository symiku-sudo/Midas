from __future__ import annotations

from typing import Any

from app.core.errors import ErrorCode


def success_response(data: dict[str, Any], request_id: str, message: str = "") -> dict[str, Any]:
    return {
        "ok": True,
        "code": ErrorCode.OK.value,
        "message": message,
        "data": data,
        "request_id": request_id,
    }


def error_response(
    *,
    code: ErrorCode,
    message: str,
    request_id: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "code": code.value,
        "message": message,
        "data": data,
        "request_id": request_id,
    }
