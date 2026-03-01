from __future__ import annotations

import logging
import os
from functools import lru_cache
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Request

from app.core.config import clear_settings_cache, get_settings
from app.core.errors import AppError, ErrorCode
from app.core.response import success_response
from app.models.schemas import (
    BilibiliNoteSaveRequest,
    BilibiliSummaryRequest,
    EditableConfigData,
    EditableConfigUpdateRequest,
    HealthData,
    NotesMergeCommitData,
    NotesMergeCommitRequest,
    NotesMergeFinalizeData,
    NotesMergeFinalizeRequest,
    NotesMergePreviewData,
    NotesMergePreviewRequest,
    NotesMergeRollbackData,
    NotesMergeRollbackRequest,
    NotesMergeSuggestData,
    NotesMergeSuggestRequest,
    NotesDeleteData,
    NotesSaveBatchData,
    XiaohongshuAuthUpdateData,
    XiaohongshuAuthUpdateRequest,
    XiaohongshuCaptureRefreshData,
    XiaohongshuNotesSaveRequest,
    XiaohongshuUrlSummaryRequest,
    XiaohongshuSyncedNotesPruneData,
)
from app.services.bilibili import BilibiliSummarizer
from app.services.editable_config import EditableConfigService
from app.services.note_library import NoteLibraryService
from app.services.xiaohongshu import XiaohongshuSyncService
from tools import xhs_capture_to_config as xhs_capture_tool

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
def _get_note_library_service() -> NoteLibraryService:
    settings = get_settings()
    return NoteLibraryService(settings)


@lru_cache(maxsize=1)
def _get_editable_config_service() -> EditableConfigService:
    return EditableConfigService()


def _reload_runtime_services() -> None:
    clear_settings_cache()
    _get_summarizer.cache_clear()
    _get_xiaohongshu_sync_service.cache_clear()
    _get_note_library_service.cache_clear()
    _get_editable_config_service.cache_clear()


def _count_cookie_pairs(raw_cookie: str) -> int:
    pairs = 0
    for segment in raw_cookie.split(";"):
        token = segment.strip()
        if token and "=" in token:
            pairs += 1
    return pairs


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    return None


async def _probe_xiaohongshu_web_identity(
    *,
    cookie: str,
    user_agent: str,
    origin: str,
    referer: str,
) -> tuple[str, bool] | None:
    settings = get_settings()
    request_url = settings.xiaohongshu.web_readonly.request_url.strip()
    if not request_url:
        return None

    host = urlparse(request_url).netloc.strip().lower()
    if not host:
        return None

    headers: dict[str, str] = {
        "Cookie": cookie,
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
    }
    if origin:
        headers["Origin"] = origin
    if referer:
        headers["Referer"] = referer

    url = f"https://{host}/api/sns/web/v2/user/me"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError:
        return None

    if response.status_code in {401, 403}:
        return "", True
    if response.status_code >= 400:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    user_id = str(data.get("user_id", "") or "").strip()
    guest = _coerce_bool(data.get("guest"))
    if guest is None:
        return None
    return user_id, guest


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


@router.post("/api/xiaohongshu/summarize-url")
async def xiaohongshu_summarize_url(
    payload: XiaohongshuUrlSummaryRequest, request: Request
) -> dict:
    logger.info("Receive xiaohongshu summarize-url request")
    service = _get_xiaohongshu_sync_service()
    result = await service.summarize_url(payload.url)
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


@router.post("/api/notes/xiaohongshu/synced/prune")
async def prune_unsaved_xiaohongshu_synced_notes(request: Request) -> dict:
    service = _get_note_library_service()
    result = service.prune_unsaved_xiaohongshu_synced_notes()
    data = XiaohongshuSyncedNotesPruneData(
        candidate_count=result.candidate_count,
        deleted_count=result.deleted_count,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/notes/merge/suggest")
async def suggest_notes_merge(
    payload: NotesMergeSuggestRequest, request: Request
) -> dict:
    service = _get_note_library_service()
    result = service.suggest_merge_candidates(
        source=payload.source,
        limit=payload.limit,
        min_score=payload.min_score,
    )
    data = NotesMergeSuggestData(total=result.total, items=result.items)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/notes/merge/preview")
async def preview_notes_merge(
    payload: NotesMergePreviewRequest, request: Request
) -> dict:
    service = _get_note_library_service()
    result = service.preview_merge(source=payload.source, note_ids=payload.note_ids)
    data = NotesMergePreviewData(
        source=result.source,
        note_ids=result.note_ids,
        merged_title=result.merged_title,
        merged_summary_markdown=result.merged_summary_markdown,
        source_refs=result.source_refs,
        conflict_markers=result.conflict_markers,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/notes/merge/commit")
async def commit_notes_merge(payload: NotesMergeCommitRequest, request: Request) -> dict:
    service = _get_note_library_service()
    result = service.commit_merge(
        source=payload.source,
        note_ids=payload.note_ids,
        merged_title=payload.merged_title,
        merged_summary_markdown=payload.merged_summary_markdown,
    )
    data = NotesMergeCommitData(
        merge_id=result.merge_id,
        status=result.status,
        source=result.source,
        merged_note_id=result.merged_note_id,
        source_note_ids=result.source_note_ids,
        can_rollback=result.can_rollback,
        can_finalize=result.can_finalize,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/notes/merge/rollback")
async def rollback_notes_merge(
    payload: NotesMergeRollbackRequest, request: Request
) -> dict:
    service = _get_note_library_service()
    result = service.rollback_merge(merge_id=payload.merge_id)
    data = NotesMergeRollbackData(
        merge_id=result.merge_id,
        status=result.status,
        deleted_merged_count=result.deleted_merged_count,
        restored_source_count=result.restored_source_count,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/notes/merge/finalize")
async def finalize_notes_merge(
    payload: NotesMergeFinalizeRequest, request: Request
) -> dict:
    service = _get_note_library_service()
    result = service.finalize_merge(
        merge_id=payload.merge_id,
        confirm_destructive=payload.confirm_destructive,
    )
    data = NotesMergeFinalizeData(
        merge_id=result.merge_id,
        status=result.status,
        deleted_source_count=result.deleted_source_count,
        kept_merged_note_id=result.kept_merged_note_id,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/xiaohongshu/auth/update")
async def update_xiaohongshu_auth(
    payload: XiaohongshuAuthUpdateRequest, request: Request
) -> dict:
    cookie = payload.cookie.strip()
    if not cookie:
        raise AppError(
            code=ErrorCode.INVALID_INPUT,
            message="Cookie 不能为空，请先在手机授权页完成登录后再上传。",
            status_code=400,
        )

    updates: dict[str, str] = {"XHS_HEADER_COOKIE": cookie}
    if payload.user_agent.strip():
        updates["XHS_HEADER_USER_AGENT"] = payload.user_agent.strip()
    if payload.origin.strip():
        updates["XHS_HEADER_ORIGIN"] = payload.origin.strip()
    if payload.referer.strip():
        updates["XHS_HEADER_REFERER"] = payload.referer.strip()

    try:
        xhs_capture_tool.upsert_env_file(xhs_capture_tool.DEFAULT_ENV_PATH, updates)
    except Exception as exc:
        logger.exception("Failed to persist xiaohongshu auth to .env.")
        raise AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message="写入小红书鉴权配置失败。",
            status_code=500,
            details={"error": str(exc)},
        ) from exc

    for key, value in updates.items():
        if value:
            os.environ[key] = value
    _reload_runtime_services()

    identity = await _probe_xiaohongshu_web_identity(
        cookie=cookie,
        user_agent=updates.get("XHS_HEADER_USER_AGENT", ""),
        origin=updates.get("XHS_HEADER_ORIGIN", ""),
        referer=updates.get("XHS_HEADER_REFERER", ""),
    )
    if identity is not None:
        user_id, guest = identity
        if guest:
            details = {"user_id": user_id} if user_id else None
            raise AppError(
                code=ErrorCode.AUTH_EXPIRED,
                message=(
                    "上传的 Cookie 仍是游客态。"
                    "请使用“内置授权(可回传)”完成登录后再上传。"
                ),
                status_code=401,
                details=details,
            )

    data = XiaohongshuAuthUpdateData(
        updated_keys=sorted(updates.keys()),
        non_empty_keys=len(updates),
        cookie_pairs=_count_cookie_pairs(cookie),
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/xiaohongshu/capture/refresh")
async def refresh_xiaohongshu_capture(request: Request) -> dict:
    try:
        _capture_source, capture_path, capture, updates = (
            xhs_capture_tool.apply_capture_from_default_auth_source_to_env(
                require_cookie=True
            )
        )
    except ValueError as exc:
        raise AppError(
            code=ErrorCode.INVALID_INPUT,
            message=str(exc),
            status_code=400,
        ) from exc
    except Exception as exc:
        logger.exception("Failed to refresh xiaohongshu capture from default HAR.")
        raise AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message="刷新小红书抓包配置失败。",
            status_code=500,
            details={"error": str(exc)},
        ) from exc

    for key, value in updates.items():
        if value:
            os.environ[key] = value
    _reload_runtime_services()

    empty_keys = sorted([key for key, value in updates.items() if not value])
    data = XiaohongshuCaptureRefreshData(
        har_path=str(capture_path),
        request_url_host=urlparse(capture.request_url).netloc,
        request_method=capture.request_method,
        headers_count=len(capture.request_headers),
        non_empty_keys=len(updates) - len(empty_keys),
        empty_keys=empty_keys,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.get("/api/config/editable")
async def get_editable_config(request: Request) -> dict:
    service = _get_editable_config_service()
    data = EditableConfigData(settings=service.get_editable_settings())
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.put("/api/config/editable")
async def update_editable_config(
    payload: EditableConfigUpdateRequest, request: Request
) -> dict:
    service = _get_editable_config_service()
    settings_data = service.update_editable_settings(payload.settings)
    _reload_runtime_services()
    data = EditableConfigData(settings=settings_data)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/config/editable/reset")
async def reset_editable_config(request: Request) -> dict:
    service = _get_editable_config_service()
    settings_data = service.reset_to_defaults()
    _reload_runtime_services()
    data = EditableConfigData(settings=settings_data)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)
