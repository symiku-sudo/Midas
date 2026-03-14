from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router, run_bilibili_summary_job, run_xiaohongshu_summary_job
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import setup_logging
from app.core.response import error_response
from app.middleware.access_token import AccessTokenMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.services.async_jobs import AsyncJobService
from app.services.database_backup import PeriodicDatabaseBackupService

settings = get_settings()
setup_logging(settings.runtime.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    backup_service = PeriodicDatabaseBackupService(settings)
    async_job_service = AsyncJobService(
        settings,
        bilibili_runner=run_bilibili_summary_job,
        xiaohongshu_runner=run_xiaohongshu_summary_job,
    )
    stop_event = asyncio.Event()
    backup_task = asyncio.create_task(backup_service.run(stop_event))
    await async_job_service.start()
    app.state.periodic_backup_service = backup_service
    app.state.periodic_backup_task = backup_task
    app.state.async_job_service = async_job_service
    try:
        yield
    finally:
        stop_event.set()
        await async_job_service.stop()
        await backup_task


app = FastAPI(title="Midas Server", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AccessTokenMiddleware)
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
