from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.response import success_response
from app.models.schemas import (
    BilibiliNoteSaveRequest,
    BilibiliSummaryRequest,
    HealthData,
    NotesDeleteData,
    NotesSaveBatchData,
    XiaohongshuNotesSaveRequest,
    XiaohongshuSyncJobCreateData,
    XiaohongshuSyncJobError,
    XiaohongshuSyncJobStatusData,
    XiaohongshuSyncRequest,
)
from app.services.bilibili import BilibiliSummarizer
from app.services.note_library import NoteLibraryService
from app.services.xiaohongshu import XiaohongshuSyncService
from app.services.xiaohongshu_job import XiaohongshuSyncJobManager

router = APIRouter()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_summarizer() -> BilibiliSummarizer:
    settings = get_settings()
    return BilibiliSummarizer(settings)


@lru_cache(maxsize=1)
def _get_xiaohongshu_sync_service() -> XiaohongshuSyncService:
    settings = get_settings()
    return XiaohongshuSyncService(settings)


@lru_cache(maxsize=1)
def _get_xiaohongshu_sync_job_manager() -> XiaohongshuSyncJobManager:
    return XiaohongshuSyncJobManager()


@lru_cache(maxsize=1)
def _get_note_library_service() -> NoteLibraryService:
    settings = get_settings()
    return NoteLibraryService(settings)


@router.get("/health")
async def health(request: Request) -> dict:
    data = HealthData().model_dump()
    return success_response(data=data, request_id=request.state.request_id)


@router.post("/api/bilibili/summarize")
async def bilibili_summarize(payload: BilibiliSummaryRequest, request: Request) -> dict:
    logger.info("Receive summarize request: %s", payload.video_url)
    summarizer = _get_summarizer()
    result = await summarizer.summarize(payload.video_url)
    return success_response(data=result.model_dump(), request_id=request.state.request_id)


@router.post("/api/notes/bilibili/save")
async def save_bilibili_note(payload: BilibiliNoteSaveRequest, request: Request) -> dict:
    service = _get_note_library_service()
    saved = service.save_bilibili_note(
        video_url=payload.video_url,
        summary_markdown=payload.summary_markdown,
        elapsed_ms=payload.elapsed_ms,
        transcript_chars=payload.transcript_chars,
        title=payload.title,
    )
    return success_response(data=saved.model_dump(), request_id=request.state.request_id)


@router.get("/api/notes/bilibili")
async def list_bilibili_notes(request: Request) -> dict:
    service = _get_note_library_service()
    result = service.list_bilibili_notes()
    return success_response(data=result.model_dump(), request_id=request.state.request_id)


@router.delete("/api/notes/bilibili/{note_id}")
async def delete_bilibili_note(note_id: str, request: Request) -> dict:
    service = _get_note_library_service()
    deleted_count = service.delete_bilibili_note(note_id)
    data = NotesDeleteData(deleted_count=deleted_count)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.delete("/api/notes/bilibili")
async def clear_bilibili_notes(request: Request) -> dict:
    service = _get_note_library_service()
    deleted_count = service.clear_bilibili_notes()
    data = NotesDeleteData(deleted_count=deleted_count)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/xiaohongshu/sync")
async def xiaohongshu_sync(payload: XiaohongshuSyncRequest, request: Request) -> dict:
    logger.info("Receive xiaohongshu sync request, limit=%s", payload.limit)
    service = _get_xiaohongshu_sync_service()
    result = await service.sync(limit=payload.limit, confirm_live=payload.confirm_live)
    return success_response(data=result.model_dump(), request_id=request.state.request_id)


@router.post("/api/notes/xiaohongshu/save-batch")
async def save_xiaohongshu_notes(
    payload: XiaohongshuNotesSaveRequest, request: Request
) -> dict:
    service = _get_note_library_service()
    saved_count = service.save_xiaohongshu_notes(payload.notes)
    data = NotesSaveBatchData(saved_count=saved_count)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.get("/api/notes/xiaohongshu")
async def list_xiaohongshu_notes(request: Request) -> dict:
    service = _get_note_library_service()
    result = service.list_xiaohongshu_notes()
    return success_response(data=result.model_dump(), request_id=request.state.request_id)


@router.delete("/api/notes/xiaohongshu/{note_id}")
async def delete_xiaohongshu_note(note_id: str, request: Request) -> dict:
    service = _get_note_library_service()
    deleted_count = service.delete_xiaohongshu_note(note_id)
    data = NotesDeleteData(deleted_count=deleted_count)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.delete("/api/notes/xiaohongshu")
async def clear_xiaohongshu_notes(request: Request) -> dict:
    service = _get_note_library_service()
    deleted_count = service.clear_xiaohongshu_notes()
    data = NotesDeleteData(deleted_count=deleted_count)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/xiaohongshu/sync/jobs")
async def xiaohongshu_sync_create_job(
    payload: XiaohongshuSyncRequest, request: Request
) -> dict:
    logger.info("Receive xiaohongshu sync job create request, limit=%s", payload.limit)
    settings = get_settings()
    requested_limit = payload.limit or settings.xiaohongshu.default_limit
    manager = _get_xiaohongshu_sync_job_manager()
    job = await manager.create_job(requested_limit=requested_limit)
    asyncio.create_task(
        _run_xiaohongshu_sync_job(
            job.job_id,
            payload.limit,
            payload.confirm_live,
        )
    )
    data = XiaohongshuSyncJobCreateData(
        job_id=job.job_id,
        status=job.status.value,
        requested_limit=requested_limit,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.get("/api/xiaohongshu/sync/jobs/{job_id}")
async def xiaohongshu_sync_get_job(job_id: str, request: Request) -> dict:
    manager = _get_xiaohongshu_sync_job_manager()
    state = await manager.get_job(job_id)
    if state is None:
        raise AppError(
            code=ErrorCode.INVALID_INPUT,
            message=f"同步任务不存在：{job_id}",
            status_code=404,
        )

    error = (
        XiaohongshuSyncJobError(
            code=state.error.get("code", ErrorCode.INTERNAL_ERROR.value),
            message=state.error.get("message", "unknown error"),
            details=state.error.get("details"),
        )
        if state.error
        else None
    )
    data = XiaohongshuSyncJobStatusData(
        job_id=state.job_id,
        status=state.status.value,
        requested_limit=state.requested_limit,
        current=state.current,
        total=state.total,
        message=state.message,
        result=state.result,
        error=error,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


async def _run_xiaohongshu_sync_job(
    job_id: str,
    limit: int | None,
    confirm_live: bool,
) -> None:
    settings = get_settings()
    requested_limit = limit or settings.xiaohongshu.default_limit
    service = _get_xiaohongshu_sync_service()
    manager = _get_xiaohongshu_sync_job_manager()

    await manager.set_running(
        job_id,
        total=requested_limit,
        message="任务已启动，正在同步小红书笔记。",
    )

    async def _on_progress(current: int, total: int, message: str) -> None:
        try:
            await manager.set_progress(
                job_id, current=current, total=total, message=message
            )
        except Exception:
            logger.exception("Failed to update xiaohongshu sync progress, job=%s", job_id)

    try:
        result = await service.sync(
            limit=limit,
            confirm_live=confirm_live,
            progress_callback=_on_progress,
        )
        await manager.set_success(job_id, result=result)
    except AppError as exc:
        details = exc.details if isinstance(exc.details, dict) else {}
        processed = int(details.get("processed_count", 0))
        total = int(details.get("fetched_count", requested_limit))
        await manager.set_failed(
            job_id,
            code=exc.code.value,
            message=exc.message,
            details=details or None,
            current=processed,
            total=total,
        )
    except Exception as exc:
        logger.exception("Unhandled xiaohongshu sync job error, job=%s", job_id)
        await manager.set_failed(
            job_id,
            code=ErrorCode.INTERNAL_ERROR.value,
            message="服务端发生未预期错误。",
            details={"error": str(exc)},
        )
