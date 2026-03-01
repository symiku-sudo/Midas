from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    OK = "OK"
    INVALID_INPUT = "INVALID_INPUT"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    RATE_LIMITED = "RATE_LIMITED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    MERGE_NOT_FOUND = "MERGE_NOT_FOUND"
    MERGE_NOT_ALLOWED = "MERGE_NOT_ALLOWED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
