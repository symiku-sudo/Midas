from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.schemas import (
    AsyncJobCreateData,
    AsyncJobErrorData,
    AsyncJobListData,
    AsyncJobListItem,
    AsyncJobProgressData,
    AsyncJobStatusData,
)

logger = logging.getLogger(__name__)

_STATUS_PENDING = "PENDING"
_STATUS_RUNNING = "RUNNING"
_STATUS_SUCCEEDED = "SUCCEEDED"
_STATUS_FAILED = "FAILED"
_STATUS_INTERRUPTED = "INTERRUPTED"
_RETRYABLE_STATUSES = {
    _STATUS_FAILED,
    _STATUS_INTERRUPTED,
}

_JOB_TYPE_BILIBILI_SUMMARIZE = "bilibili_summarize"
_JOB_TYPE_XIAOHONGSHU_SUMMARIZE_URL = "xiaohongshu_summarize_url"
_JOB_TYPE_XIAOHONGSHU_SYNC = "xiaohongshu_sync"
_SUPPORTED_JOB_TYPES = {
    _JOB_TYPE_BILIBILI_SUMMARIZE,
    _JOB_TYPE_XIAOHONGSHU_SUMMARIZE_URL,
    _JOB_TYPE_XIAOHONGSHU_SYNC,
}


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AsyncJobService:
    def __init__(
        self,
        settings: Settings,
        *,
        bilibili_runner: Callable[[str], Awaitable[Any]],
        xiaohongshu_runner: Callable[[str], Awaitable[Any]],
        xiaohongshu_sync_runner: Callable[
            [int | None, bool, Callable[[dict[str, Any]], Awaitable[None]] | None],
            Awaitable[Any],
        ],
    ) -> None:
        self._settings = settings
        self._bilibili_runner = bilibili_runner
        self._xiaohongshu_runner = xiaohongshu_runner
        self._xiaohongshu_sync_runner = xiaohongshu_sync_runner
        self._store_path = Path(settings.runtime.temp_dir) / "async_jobs.json"
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._jobs_by_id: dict[str, dict[str, Any]] = {}
        self._write_lock = asyncio.Lock()
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        await self._load_store()
        await self._recover_incomplete_jobs()
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        await self._queue.put(None)
        await self._worker_task
        self._worker_task = None

    async def create_bilibili_summary_job(
        self, *, video_url: str, request_id: str
    ) -> AsyncJobCreateData:
        return await self._create_job(
            job_type=_JOB_TYPE_BILIBILI_SUMMARIZE,
            request_payload={"video_url": video_url},
            request_id=request_id,
        )

    async def create_xiaohongshu_summary_job(
        self, *, url: str, request_id: str
    ) -> AsyncJobCreateData:
        return await self._create_job(
            job_type=_JOB_TYPE_XIAOHONGSHU_SUMMARIZE_URL,
            request_payload={"url": url},
            request_id=request_id,
        )

    async def create_xiaohongshu_sync_job(
        self,
        *,
        limit: int | None,
        confirm_live: bool,
        request_id: str,
    ) -> AsyncJobCreateData:
        requested_limit = int(limit) if limit is not None else 0
        progress_total = max(requested_limit, 0)
        return await self._create_job(
            job_type=_JOB_TYPE_XIAOHONGSHU_SYNC,
            request_payload={
                "limit": limit,
                "confirm_live": bool(confirm_live),
            },
            request_id=request_id,
            progress_current=0,
            progress_total=progress_total,
        )

    async def list_jobs(
        self, *, limit: int = 20, status: str = "", job_type: str = ""
    ) -> AsyncJobListData:
        normalized_status = status.strip().upper()
        normalized_job_types = [
            item.strip().lower()
            for item in job_type.split(",")
            if item.strip()
        ]
        unsupported_job_types = [
            item for item in normalized_job_types if item not in _SUPPORTED_JOB_TYPES
        ]
        if unsupported_job_types:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"不支持的 job_type: {', '.join(unsupported_job_types)}",
                status_code=400,
            )

        items = list(self._jobs_by_id.values())
        items.sort(
            key=lambda item: (
                str(item.get("submitted_at", "")),
                str(item.get("job_id", "")),
            ),
            reverse=True,
        )
        filtered: list[AsyncJobListItem] = []
        total = 0
        for item in items:
            if normalized_status and item.get("status") != normalized_status:
                continue
            if normalized_job_types and item.get("job_type") not in normalized_job_types:
                continue
            total += 1
            if len(filtered) < limit:
                filtered.append(self._to_list_item(item))
        return AsyncJobListData(total=total, items=filtered)

    async def get_job(self, job_id: str) -> AsyncJobStatusData:
        record = self._jobs_by_id.get(job_id)
        if record is None:
            raise AppError(
                code=ErrorCode.JOB_NOT_FOUND,
                message=f"未找到 job_id={job_id} 对应的任务。",
                status_code=404,
            )
        return self._to_status_data(record)

    async def retry_job(self, job_id: str, *, request_id: str) -> AsyncJobCreateData:
        record = self._jobs_by_id.get(job_id)
        if record is None:
            raise AppError(
                code=ErrorCode.JOB_NOT_FOUND,
                message=f"未找到 job_id={job_id} 对应的任务。",
                status_code=404,
            )
        status = str(record.get("status", "")).strip().upper()
        if status not in _RETRYABLE_STATUSES:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="仅支持重试 FAILED 或 INTERRUPTED 状态的任务。",
                status_code=400,
                details={"job_id": job_id, "status": status},
            )
        request_payload = record.get("request_payload")
        if not isinstance(request_payload, dict) or not request_payload:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="原任务缺少可重试的请求参数。",
                status_code=400,
                details={"job_id": job_id},
            )
        job_type = str(record.get("job_type", "")).strip().lower()
        progress_total = 0
        if job_type == _JOB_TYPE_XIAOHONGSHU_SYNC:
            progress_total = self._coerce_progress_number(request_payload.get("limit"))
        return await self._create_job(
            job_type=job_type,
            request_payload=dict(request_payload),
            request_id=request_id,
            retry_of_job_id=job_id,
            progress_current=0,
            progress_total=progress_total,
        )

    async def _create_job(
        self,
        *,
        job_type: str,
        request_payload: dict[str, Any],
        request_id: str,
        retry_of_job_id: str = "",
        progress_current: int = 0,
        progress_total: int = 0,
    ) -> AsyncJobCreateData:
        if job_type not in _SUPPORTED_JOB_TYPES:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"不支持的 job_type: {job_type}",
                status_code=400,
            )
        submitted_at = _now_text()
        job_id = uuid.uuid4().hex
        record = {
            "job_id": job_id,
            "job_type": job_type,
            "status": _STATUS_PENDING,
            "message": "任务已入队，等待执行。",
            "submitted_at": submitted_at,
            "started_at": "",
            "finished_at": "",
            "request_payload": dict(request_payload),
            "request_id": request_id,
            "retry_of_job_id": retry_of_job_id.strip(),
            "progress": self._build_progress_record(
                current=progress_current,
                total=progress_total,
            ),
            "result": None,
            "error": None,
        }
        self._jobs_by_id[job_id] = record
        await self._persist_store()
        await self._queue.put(job_id)
        return AsyncJobCreateData(
            job_id=job_id,
            job_type=job_type,
            status=_STATUS_PENDING,
            message=record["message"],
            submitted_at=submitted_at,
            retry_of_job_id=record["retry_of_job_id"],
            progress_current=progress_current,
            progress_total=progress_total,
        )

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                if job_id is None:
                    return
                await self._run_job(job_id)
            finally:
                self._queue.task_done()

    async def _run_job(self, job_id: str) -> None:
        record = self._jobs_by_id.get(job_id)
        if record is None:
            return
        if record.get("status") != _STATUS_PENDING:
            return

        record["status"] = _STATUS_RUNNING
        record["started_at"] = _now_text()
        record["message"] = "任务执行中。"
        await self._persist_store()

        try:
            result = await self._execute_job(record)
        except AppError as exc:
            logger.warning("Async job failed: job_id=%s code=%s", job_id, exc.code.value)
            record["status"] = _STATUS_FAILED
            record["finished_at"] = _now_text()
            record["message"] = exc.message
            self._sync_progress_from_result(record)
            record["error"] = {
                "code": exc.code.value,
                "message": exc.message,
                "details": exc.details or None,
            }
            await self._persist_store()
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Async job crashed: job_id=%s", job_id)
            record["status"] = _STATUS_FAILED
            record["finished_at"] = _now_text()
            record["message"] = "任务执行失败。"
            self._sync_progress_from_result(record)
            record["error"] = {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "服务端发生未预期错误。",
                "details": {"error": str(exc)},
            }
            await self._persist_store()
            return

        record["status"] = _STATUS_SUCCEEDED
        record["finished_at"] = _now_text()
        record["message"] = "任务执行完成。"
        record["result"] = result
        self._sync_progress_from_result(record)
        record["error"] = None
        await self._persist_store()

    async def _execute_job(self, record: dict[str, Any]) -> dict[str, Any]:
        job_type = str(record.get("job_type", "")).strip().lower()
        payload = record.get("request_payload") or {}
        if job_type == _JOB_TYPE_BILIBILI_SUMMARIZE:
            result = await self._bilibili_runner(str(payload.get("video_url", "")))
            return result.model_dump()
        if job_type == _JOB_TYPE_XIAOHONGSHU_SUMMARIZE_URL:
            result = await self._xiaohongshu_runner(str(payload.get("url", "")))
            return result.model_dump()
        if job_type == _JOB_TYPE_XIAOHONGSHU_SYNC:
            async def _on_progress(progress_payload: dict[str, Any]) -> None:
                self._apply_progress_update(record, progress_payload)
                await self._persist_store()

            result = await self._xiaohongshu_sync_runner(
                self._optional_int(payload.get("limit")),
                bool(payload.get("confirm_live", False)),
                _on_progress,
            )
            return result.model_dump()
        raise AppError(
            code=ErrorCode.INVALID_INPUT,
            message=f"不支持的 job_type: {job_type}",
            status_code=400,
        )

    async def _load_store(self) -> None:
        if not self._store_path.exists():
            self._jobs_by_id = {}
            return
        try:
            payload = json.loads(self._store_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ignore broken async job store: %s", exc)
            self._jobs_by_id = {}
            return
        if not isinstance(payload, dict):
            self._jobs_by_id = {}
            return
        jobs_raw = payload.get("jobs")
        if not isinstance(jobs_raw, list):
            self._jobs_by_id = {}
            return
        items: dict[str, dict[str, Any]] = {}
        for item in jobs_raw:
            if not isinstance(item, dict):
                continue
            job_id = str(item.get("job_id", "")).strip()
            if not job_id:
                continue
            items[job_id] = {
                "job_id": job_id,
                "job_type": str(item.get("job_type", "")).strip(),
                "status": str(item.get("status", _STATUS_PENDING)).strip().upper(),
                "message": str(item.get("message", "")).strip(),
                "submitted_at": str(item.get("submitted_at", "")).strip(),
                "started_at": str(item.get("started_at", "")).strip(),
                "finished_at": str(item.get("finished_at", "")).strip(),
                "request_payload": item.get("request_payload")
                if isinstance(item.get("request_payload"), dict)
                else {},
                "request_id": str(item.get("request_id", "")).strip(),
                "retry_of_job_id": str(item.get("retry_of_job_id", "")).strip(),
                "progress": item.get("progress") if isinstance(item.get("progress"), dict) else None,
                "result": item.get("result") if isinstance(item.get("result"), dict) else None,
                "error": item.get("error") if isinstance(item.get("error"), dict) else None,
            }
        self._jobs_by_id = items

    async def _recover_incomplete_jobs(self) -> None:
        changed = False
        pending_job_ids: list[str] = []
        for record in self._jobs_by_id.values():
            status = str(record.get("status", "")).strip().upper()
            if status == _STATUS_RUNNING:
                record["status"] = _STATUS_INTERRUPTED
                record["finished_at"] = _now_text()
                record["message"] = "服务重启前任务中断，请重新提交。"
                self._sync_progress_from_result(record)
                record["error"] = {
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "服务重启导致任务中断。",
                    "details": None,
                }
                changed = True
                continue
            if status == _STATUS_PENDING:
                pending_job_ids.append(str(record.get("job_id", "")))
        if changed:
            await self._persist_store()
        for job_id in pending_job_ids:
            await self._queue.put(job_id)

    async def _persist_store(self) -> None:
        async with self._write_lock:
            payload = {
                "jobs": sorted(
                    self._jobs_by_id.values(),
                    key=lambda item: (
                        str(item.get("submitted_at", "")),
                        str(item.get("job_id", "")),
                    ),
                )
            }
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=str(self._store_path.parent),
                delete=False,
            ) as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)
                tmp_name = fp.name
            Path(tmp_name).replace(self._store_path)

    def _to_list_item(self, record: dict[str, Any]) -> AsyncJobListItem:
        return AsyncJobListItem(
            job_id=str(record.get("job_id", "")).strip(),
            job_type=str(record.get("job_type", "")).strip(),
            status=str(record.get("status", "")).strip(),
            message=str(record.get("message", "")).strip(),
            submitted_at=str(record.get("submitted_at", "")).strip(),
            started_at=str(record.get("started_at", "")).strip(),
            finished_at=str(record.get("finished_at", "")).strip(),
            retry_of_job_id=str(record.get("retry_of_job_id", "")).strip(),
            progress=self._to_progress_data(record.get("progress")),
        )

    def _to_status_data(self, record: dict[str, Any]) -> AsyncJobStatusData:
        error_raw = record.get("error")
        error = None
        if isinstance(error_raw, dict):
            error = AsyncJobErrorData(
                code=str(error_raw.get("code", "")).strip(),
                message=str(error_raw.get("message", "")).strip(),
                details=error_raw.get("details")
                if isinstance(error_raw.get("details"), dict) or error_raw.get("details") is None
                else None,
            )
        return AsyncJobStatusData(
            job_id=str(record.get("job_id", "")).strip(),
            job_type=str(record.get("job_type", "")).strip(),
            status=str(record.get("status", "")).strip(),
            message=str(record.get("message", "")).strip(),
            submitted_at=str(record.get("submitted_at", "")).strip(),
            started_at=str(record.get("started_at", "")).strip(),
            finished_at=str(record.get("finished_at", "")).strip(),
            retry_of_job_id=str(record.get("retry_of_job_id", "")).strip(),
            request_payload=record.get("request_payload")
            if isinstance(record.get("request_payload"), dict)
            else {},
            result=record.get("result") if isinstance(record.get("result"), dict) else None,
            error=error,
            progress=self._to_progress_data(record.get("progress")),
        )

    def _to_progress_data(self, raw: Any) -> AsyncJobProgressData | None:
        if not isinstance(raw, dict):
            return None
        current = self._coerce_progress_number(raw.get("current"))
        total = self._coerce_progress_number(raw.get("total"))
        if current <= 0 and total <= 0:
            return None
        return AsyncJobProgressData(current=current, total=total)

    def _apply_progress_update(self, record: dict[str, Any], progress_payload: dict[str, Any]) -> None:
        if not isinstance(progress_payload, dict):
            return
        message = str(progress_payload.get("message", "")).strip()
        if message:
            record["message"] = message
        current = self._coerce_progress_number(progress_payload.get("current"))
        total = self._coerce_progress_number(progress_payload.get("total"))
        record["progress"] = self._build_progress_record(current=current, total=total)
        preview = {
            "current": current,
            "total": total,
            "message": message,
            "summaries": progress_payload.get("summaries")
            if isinstance(progress_payload.get("summaries"), list)
            else [],
        }
        record["result"] = preview

    def _sync_progress_from_result(self, record: dict[str, Any]) -> None:
        result = record.get("result")
        if not isinstance(result, dict):
            return
        current = self._coerce_progress_number(
            result.get("new_count", result.get("current")),
        )
        total = self._coerce_progress_number(
            result.get("requested_limit", result.get("total")),
        )
        if current <= 0 and total <= 0:
            return
        record["progress"] = self._build_progress_record(current=current, total=total)

    def _build_progress_record(self, *, current: int, total: int) -> dict[str, int] | None:
        normalized_current = max(int(current), 0)
        normalized_total = max(int(total), 0)
        if normalized_current <= 0 and normalized_total <= 0:
            return None
        return {
            "current": normalized_current,
            "total": normalized_total,
        }

    def _coerce_progress_number(self, raw: Any) -> int:
        if isinstance(raw, bool) or raw is None:
            return 0
        if isinstance(raw, int):
            return max(raw, 0)
        if isinstance(raw, float):
            return max(int(raw), 0)
        if isinstance(raw, str):
            return max(int(raw.strip() or "0"), 0) if raw.strip().lstrip("-").isdigit() else 0
        return 0

    def _optional_int(self, raw: Any) -> int | None:
        if raw is None:
            return None
        value = self._coerce_progress_number(raw)
        return value if value > 0 else None
