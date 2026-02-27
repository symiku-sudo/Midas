from __future__ import annotations

import asyncio
import copy
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.models.schemas import XiaohongshuSyncData


class XiaohongshuJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class XiaohongshuSyncJobState:
    job_id: str
    status: XiaohongshuJobStatus
    requested_limit: int
    current: int = 0
    total: int = 0
    message: str = ""
    summaries: list[dict[str, Any]] = field(default_factory=list)
    acked_note_ids: set[str] = field(default_factory=set)
    result: XiaohongshuSyncData | None = None
    error: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class XiaohongshuSyncJobManager:
    _COMPLETED_STATUSES = {
        XiaohongshuJobStatus.SUCCEEDED,
        XiaohongshuJobStatus.FAILED,
    }

    def __init__(
        self,
        *,
        max_jobs: int = 200,
        completed_ttl_seconds: int = 3600,
    ) -> None:
        self._jobs: dict[str, XiaohongshuSyncJobState] = {}
        self._lock = asyncio.Lock()
        self._max_jobs = max(int(max_jobs), 10)
        self._completed_ttl_seconds = max(int(completed_ttl_seconds), 60)

    async def create_job(self, *, requested_limit: int) -> XiaohongshuSyncJobState:
        async with self._lock:
            self._garbage_collect_locked(now=time.time())
            job_id = uuid.uuid4().hex
            state = XiaohongshuSyncJobState(
                job_id=job_id,
                status=XiaohongshuJobStatus.PENDING,
                requested_limit=requested_limit,
                message="任务已创建，等待执行。",
            )
            self._jobs[job_id] = state
            self._garbage_collect_locked(now=time.time())
            return copy.deepcopy(state)

    async def get_job(self, job_id: str) -> XiaohongshuSyncJobState | None:
        async with self._lock:
            self._garbage_collect_locked(now=time.time())
            state = self._jobs.get(job_id)
            if state is None:
                return None
            return copy.deepcopy(state)

    async def set_running(self, job_id: str, *, total: int, message: str) -> None:
        async with self._lock:
            state = self._must_get(job_id)
            state.status = XiaohongshuJobStatus.RUNNING
            state.total = max(total, 0)
            state.message = message
            state.summaries = []
            state.acked_note_ids = set()
            state.updated_at = time.time()

    async def set_progress(
        self,
        job_id: str,
        *,
        current: int,
        total: int,
        message: str,
        summaries: list[dict[str, Any]] | None = None,
    ) -> None:
        async with self._lock:
            state = self._must_get(job_id)
            if state.status not in {
                XiaohongshuJobStatus.RUNNING,
                XiaohongshuJobStatus.PENDING,
            }:
                return
            state.status = XiaohongshuJobStatus.RUNNING
            state.current = max(current, 0)
            state.total = max(total, 0)
            state.message = message
            if summaries is not None:
                state.summaries = copy.deepcopy(summaries)
            state.updated_at = time.time()

    async def set_success(self, job_id: str, *, result: XiaohongshuSyncData) -> None:
        async with self._lock:
            state = self._must_get(job_id)
            state.status = XiaohongshuJobStatus.SUCCEEDED
            state.current = result.fetched_count
            state.total = result.fetched_count
            state.message = "同步任务完成。"
            state.summaries = [item.model_dump() for item in result.summaries]
            # Avoid storing duplicated summaries in memory for completed jobs.
            state.result = result.model_copy(update={"summaries": []})
            state.error = None
            state.updated_at = time.time()
            self._garbage_collect_locked(now=state.updated_at)

    async def build_ack_plan(
        self, job_id: str, *, note_ids: list[str]
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        async with self._lock:
            state = self._must_get(job_id)
            normalized_ids: list[str] = []
            seen: set[str] = set()
            for note_id in note_ids:
                value = str(note_id).strip()
                if not value or value in seen:
                    continue
                normalized_ids.append(value)
                seen.add(value)

            summary_map: dict[str, dict[str, Any]] = {}
            for item in state.summaries:
                note_id = str(item.get("note_id", "")).strip()
                if note_id:
                    summary_map[note_id] = item

            to_ack: list[dict[str, Any]] = []
            already_acked: list[str] = []
            missing_ids: list[str] = []
            for note_id in normalized_ids:
                if note_id in state.acked_note_ids:
                    already_acked.append(note_id)
                    continue
                summary = summary_map.get(note_id)
                if summary is None:
                    missing_ids.append(note_id)
                    continue
                to_ack.append(copy.deepcopy(summary))

            return to_ack, already_acked, missing_ids

    async def apply_acked_note_ids(self, job_id: str, *, note_ids: list[str]) -> None:
        async with self._lock:
            state = self._must_get(job_id)
            for note_id in note_ids:
                value = str(note_id).strip()
                if value:
                    state.acked_note_ids.add(value)
            state.updated_at = time.time()

    async def set_failed(
        self,
        job_id: str,
        *,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        async with self._lock:
            state = self._must_get(job_id)
            state.status = XiaohongshuJobStatus.FAILED
            if current is not None:
                state.current = max(current, 0)
            if total is not None:
                state.total = max(total, 0)
            state.message = "同步任务失败。"
            state.result = None
            state.error = {
                "code": code,
                "message": message,
                "details": details or None,
            }
            state.updated_at = time.time()
            self._garbage_collect_locked(now=state.updated_at)

    def _garbage_collect_locked(self, *, now: float) -> None:
        expired_job_ids = [
            job_id
            for job_id, state in self._jobs.items()
            if state.status in self._COMPLETED_STATUSES
            and (now - state.updated_at) >= self._completed_ttl_seconds
        ]
        for job_id in expired_job_ids:
            self._jobs.pop(job_id, None)

        overflow = len(self._jobs) - self._max_jobs
        if overflow <= 0:
            return

        candidates = sorted(
            (
                state
                for state in self._jobs.values()
                if state.status in self._COMPLETED_STATUSES
            ),
            key=lambda item: item.updated_at,
        )
        for state in candidates[:overflow]:
            self._jobs.pop(state.job_id, None)

    def _must_get(self, job_id: str) -> XiaohongshuSyncJobState:
        if job_id not in self._jobs:
            raise KeyError(f"job not found: {job_id}")
        return self._jobs[job_id]
