from __future__ import annotations

import logging
import os
from datetime import datetime
from functools import lru_cache
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, File, Query, Request, UploadFile

from app.core.config import clear_settings_cache, get_settings
from app.core.errors import AppError, ErrorCode
from app.core.response import success_response
from app.models.schemas import (
    AsyncJobCreateData,
    AsyncJobListData,
    AsyncJobStatusData,
    AssetCurrentData,
    AssetCurrentUpdateRequest,
    AssetSnapshotHistoryData,
    AssetSnapshotSaveRequest,
    AssetSnapshotRecord,
    AssetImageFillData,
    BilibiliNoteSaveRequest,
    BilibiliSummaryRequest,
    EditableConfigData,
    EditableConfigUpdateRequest,
    FinanceFocusCardActionData,
    FinanceFocusCardActionRequest,
    FinanceFocusCardHistoryData,
    FinanceWatchlistNtfyData,
    FinanceWatchlistNtfyUpdateRequest,
    HealthData,
    HomeOverviewData,
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
    NotesReviewTopicsData,
    NotesTimelineReviewData,
    NotesSaveBatchData,
    RelatedNotesData,
    UnifiedNotesData,
    XiaohongshuAuthUpdateData,
    XiaohongshuAuthUpdateRequest,
    XiaohongshuCaptureRefreshData,
    XiaohongshuNotesSaveRequest,
    XiaohongshuUrlSummaryRequest,
    XiaohongshuSyncedNotesPruneData,
)
from app.services.bilibili import BilibiliSummarizer
from app.services.async_jobs import AsyncJobService
from app.services.asset_image_fill import AssetImageFillService
from app.services.asset_snapshots import AssetSnapshotService
from app.services.editable_config import EditableConfigService
from app.services.finance_signals import FinanceSignalsService
from app.services.note_library import NoteLibraryService
from app.services.xiaohongshu import XiaohongshuService
from tools import xhs_capture_to_config as xhs_capture_tool

router = APIRouter()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_summarizer() -> BilibiliSummarizer:
    settings = get_settings()
    return BilibiliSummarizer(settings)


@lru_cache(maxsize=1)
def _get_xiaohongshu_service() -> XiaohongshuService:
    settings = get_settings()
    return XiaohongshuService(settings)

@lru_cache(maxsize=1)
def _get_note_library_service() -> NoteLibraryService:
    settings = get_settings()
    return NoteLibraryService(settings)


@lru_cache(maxsize=1)
def _get_editable_config_service() -> EditableConfigService:
    return EditableConfigService()


@lru_cache(maxsize=1)
def _get_finance_signals_service() -> FinanceSignalsService:
    return FinanceSignalsService(get_settings())


@lru_cache(maxsize=1)
def _get_asset_image_fill_service() -> AssetImageFillService:
    settings = get_settings()
    return AssetImageFillService(settings)


@lru_cache(maxsize=1)
def _get_asset_snapshot_service() -> AssetSnapshotService:
    settings = get_settings()
    return AssetSnapshotService(settings)


def _reload_runtime_services() -> None:
    clear_settings_cache()
    _get_summarizer.cache_clear()
    _get_xiaohongshu_service.cache_clear()
    _get_note_library_service.cache_clear()
    _get_editable_config_service.cache_clear()
    _get_finance_signals_service.cache_clear()
    _get_asset_image_fill_service.cache_clear()
    _get_asset_snapshot_service.cache_clear()


def _get_async_job_service(request: Request) -> AsyncJobService:
    service = getattr(request.app.state, "async_job_service", None)
    if service is None:
        raise AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message="异步任务服务尚未初始化。",
            status_code=500,
        )
    return service


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


async def run_bilibili_summary_job(video_url: str):
    summarizer = _get_summarizer()
    return await summarizer.summarize(video_url)


async def run_xiaohongshu_summary_job(url: str):
    service = _get_xiaohongshu_service()
    return await service.summarize_url(url)


@router.get("/health")
async def health(request: Request) -> dict:
    data = HealthData().model_dump()
    return success_response(data=data, request_id=request.state.request_id)


@router.get("/api/home/overview")
async def get_home_overview(request: Request) -> dict:
    async_job_service = _get_async_job_service(request)
    notes_service = _get_note_library_service()
    finance_service = _get_finance_signals_service()
    asset_service = _get_asset_snapshot_service()

    recent_jobs = await async_job_service.list_jobs(limit=5)
    recent_notes = notes_service.search_notes(
        limit=5,
        offset=0,
        sort_by="saved_at",
        sort_order="desc",
    )
    finance_data = finance_service.get_dashboard_state()
    asset_current = asset_service.get_current()

    data = HomeOverviewData(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        recent_tasks=recent_jobs.items,
        recent_notes=recent_notes.items,
        finance_focus_cards=finance_data.focus_cards[:3],
        quick_links=[
            {"target": "bilibili", "title": "B站总结", "subtitle": "贴链接，走后台任务"},
            {"target": "xiaohongshu", "title": "小红书单链", "subtitle": "总结后直接保存"},
            {"target": "notes", "title": "笔记回看", "subtitle": "按筛选和时间回顾"},
        ],
        asset_total_amount_wan=asset_current.total_amount_wan,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.get("/api/finance/signals")
async def get_finance_signals(request: Request) -> dict:
    service = _get_finance_signals_service()
    data = service.get_dashboard_state()
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.put("/api/finance/signals/watchlist-ntfy")
async def update_finance_watchlist_ntfy(
    payload: FinanceWatchlistNtfyUpdateRequest, request: Request
) -> dict:
    service = _get_finance_signals_service()
    enabled = service.set_watchlist_ntfy_enabled(payload.enabled)
    _reload_runtime_services()
    data = FinanceWatchlistNtfyData(enabled=enabled)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/finance/signals/digest")
async def trigger_finance_news_digest(request: Request) -> dict:
    service = _get_finance_signals_service()
    data = await service.trigger_news_digest()
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/finance/signals/cards/{card_id}/status")
async def update_finance_focus_card_status(
    card_id: str,
    payload: FinanceFocusCardActionRequest,
    request: Request,
) -> dict:
    service = _get_finance_signals_service()
    data: FinanceFocusCardActionData = service.update_focus_card_status(
        card_id=card_id,
        status=payload.status,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.get("/api/finance/signals/history")
async def get_finance_focus_card_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    service = _get_finance_signals_service()
    data: FinanceFocusCardHistoryData = service.get_focus_card_history(limit=limit)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/assets/fill-from-images")
async def fill_asset_stats_from_images(
    request: Request,
    images: list[UploadFile] = File(...),
) -> dict:
    service = _get_asset_image_fill_service()
    result: AssetImageFillData = await service.extract_from_uploads(images)
    return success_response(data=result.model_dump(), request_id=request.state.request_id)


@router.get("/api/assets/current")
async def get_asset_current(request: Request) -> dict:
    service = _get_asset_snapshot_service()
    data: AssetCurrentData = service.get_current()
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.put("/api/assets/current")
async def save_asset_current(payload: AssetCurrentUpdateRequest, request: Request) -> dict:
    service = _get_asset_snapshot_service()
    data: AssetCurrentData = service.save_current(
        total_amount_wan=payload.total_amount_wan,
        amounts=payload.amounts,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.get("/api/assets/snapshots")
async def list_asset_snapshots(request: Request) -> dict:
    service = _get_asset_snapshot_service()
    data: AssetSnapshotHistoryData = service.list_history()
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/assets/snapshots")
async def save_asset_snapshot(payload: AssetSnapshotSaveRequest, request: Request) -> dict:
    service = _get_asset_snapshot_service()
    data: AssetSnapshotRecord = service.save_snapshot(
        record_id=payload.id,
        saved_at=payload.saved_at,
        total_amount_wan=payload.total_amount_wan,
        amounts=payload.amounts,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.delete("/api/assets/snapshots/{record_id}")
async def delete_asset_snapshot(record_id: str, request: Request) -> dict:
    service = _get_asset_snapshot_service()
    deleted_count = service.delete_snapshot(record_id)
    data = NotesDeleteData(deleted_count=deleted_count)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/jobs/bilibili-summarize")
async def create_bilibili_summarize_job(
    payload: BilibiliSummaryRequest, request: Request
) -> dict:
    service = _get_async_job_service(request)
    data: AsyncJobCreateData = await service.create_bilibili_summary_job(
        video_url=payload.video_url,
        request_id=request.state.request_id,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/jobs/xiaohongshu/summarize-url")
async def create_xiaohongshu_summarize_job(
    payload: XiaohongshuUrlSummaryRequest, request: Request
) -> dict:
    service = _get_async_job_service(request)
    data: AsyncJobCreateData = await service.create_xiaohongshu_summary_job(
        url=payload.url,
        request_id=request.state.request_id,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.get("/api/jobs")
async def list_async_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    status: str = Query(default=""),
    job_type: str = Query(default=""),
) -> dict:
    service = _get_async_job_service(request)
    data: AsyncJobListData = await service.list_jobs(
        limit=limit,
        status=status,
        job_type=job_type,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.get("/api/jobs/{job_id}")
async def get_async_job(job_id: str, request: Request) -> dict:
    service = _get_async_job_service(request)
    data: AsyncJobStatusData = await service.get_job(job_id)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/jobs/{job_id}/retry")
async def retry_async_job(job_id: str, request: Request) -> dict:
    service = _get_async_job_service(request)
    data: AsyncJobCreateData = await service.retry_job(
        job_id=job_id,
        request_id=request.state.request_id,
    )
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


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


@router.get("/api/notes/search")
async def search_notes(
    request: Request,
    keyword: str = Query(default=""),
    source: str = Query(default=""),
    saved_from: str = Query(default=""),
    saved_to: str = Query(default=""),
    merged: bool | None = Query(default=None),
    sort_by: str = Query(default="saved_at"),
    sort_order: str = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    service = _get_note_library_service()
    search_kwargs = dict(
        keyword=keyword,
        source=source,
        limit=limit,
        offset=offset,
    )
    if saved_from:
        search_kwargs["saved_from"] = saved_from
    if saved_to:
        search_kwargs["saved_to"] = saved_to
    if merged is not None:
        search_kwargs["merged"] = merged
    if sort_by and sort_by != "saved_at":
        search_kwargs["sort_by"] = sort_by
    if sort_order and sort_order != "desc":
        search_kwargs["sort_order"] = sort_order
    result: UnifiedNotesData = service.search_notes(**search_kwargs)
    return success_response(data=result.model_dump(), request_id=request.state.request_id)


@router.get("/api/notes/review/topics")
async def review_notes_topics(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=8, ge=1, le=50),
    per_topic_limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    service = _get_note_library_service()
    result: NotesReviewTopicsData = service.review_notes_by_topics(
        days=days,
        limit=limit,
        per_topic_limit=per_topic_limit,
    )
    return success_response(data=result.model_dump(), request_id=request.state.request_id)


@router.get("/api/notes/review/timeline")
async def review_notes_timeline(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    bucket: str = Query(default="day"),
    limit: int = Query(default=10, ge=1, le=50),
    per_bucket_limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    service = _get_note_library_service()
    result: NotesTimelineReviewData = service.review_notes_by_timeline(
        days=days,
        bucket=bucket,
        limit=limit,
        per_bucket_limit=per_bucket_limit,
    )
    return success_response(data=result.model_dump(), request_id=request.state.request_id)


@router.get("/api/notes/{source}/{note_id}/related")
async def get_related_notes(
    source: str,
    note_id: str,
    request: Request,
    limit: int = Query(default=8, ge=1, le=50),
    min_score: float = Query(default=0.2, ge=0.0, le=1.0),
) -> dict:
    service = _get_note_library_service()
    result: RelatedNotesData = service.find_related_notes(
        source=source,
        note_id=note_id,
        limit=limit,
        min_score=min_score,
    )
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
    service = _get_xiaohongshu_service()
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
        include_weak=payload.include_weak,
    )
    data = NotesMergeSuggestData(total=result.total, items=result.items)
    return success_response(data=data.model_dump(), request_id=request.state.request_id)


@router.post("/api/notes/merge/preview")
async def preview_notes_merge(
    payload: NotesMergePreviewRequest, request: Request
) -> dict:
    service = _get_note_library_service()
    result = await service.preview_merge(source=payload.source, note_ids=payload.note_ids)
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
    result = await service.commit_merge(
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
