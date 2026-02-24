from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import setup_logging
from app.core.response import error_response
from app.middleware.request_id import RequestIDMiddleware

settings = get_settings()
setup_logging(settings.runtime.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="Midas Server", version="0.1.0")
app.add_middleware(RequestIDMiddleware)
app.include_router(router)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("AppError: %s - %s", exc.code.value, exc.message)
    payload = error_response(
        code=exc.code,
        message=exc.message,
        request_id=request.state.request_id,
        data=exc.details or None,
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("ValidationError: %s", exc.errors())
    payload = error_response(
        code=ErrorCode.INVALID_INPUT,
        message="请求参数不合法。",
        request_id=request.state.request_id,
        data={"errors": exc.errors()},
    )
    return JSONResponse(status_code=422, content=payload)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    payload = error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message="服务端发生未预期错误。",
        request_id=request.state.request_id,
    )
    return JSONResponse(status_code=500, content=payload)
