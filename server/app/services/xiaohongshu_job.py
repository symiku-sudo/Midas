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
    result: XiaohongshuSyncData | None = None
    error: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class XiaohongshuSyncJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, XiaohongshuSyncJobState] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, *, requested_limit: int) -> XiaohongshuSyncJobState:
        async with self._lock:
            job_id = uuid.uuid4().hex
            state = XiaohongshuSyncJobState(
                job_id=job_id,
                status=XiaohongshuJobStatus.PENDING,
                requested_limit=requested_limit,
                message="任务已创建，等待执行。",
            )
            self._jobs[job_id] = state
            return copy.deepcopy(state)

    async def get_job(self, job_id: str) -> XiaohongshuSyncJobState | None:
        async with self._lock:
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
            state.updated_at = time.time()

    async def set_progress(
        self, job_id: str, *, current: int, total: int, message: str
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
            state.updated_at = time.time()

    async def set_success(self, job_id: str, *, result: XiaohongshuSyncData) -> None:
        async with self._lock:
            state = self._must_get(job_id)
            state.status = XiaohongshuJobStatus.SUCCEEDED
            state.current = result.fetched_count
            state.total = result.fetched_count
            state.message = "同步任务完成。"
            state.result = result
            state.error = None
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

    def _must_get(self, job_id: str) -> XiaohongshuSyncJobState:
        if job_id not in self._jobs:
            raise KeyError(f"job not found: {job_id}")
        return self._jobs[job_id]

