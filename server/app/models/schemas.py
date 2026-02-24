from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthData(BaseModel):
    status: str = "ok"


class BilibiliSummaryRequest(BaseModel):
    video_url: str = Field(min_length=3, max_length=2000)


class BilibiliSummaryData(BaseModel):
    video_url: str
    summary_markdown: str
    elapsed_ms: int
    transcript_chars: int


class XiaohongshuSyncRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=100)


class XiaohongshuSummaryItem(BaseModel):
    note_id: str
    title: str
    source_url: str
    summary_markdown: str


class XiaohongshuSyncData(BaseModel):
    requested_limit: int
    fetched_count: int
    new_count: int
    skipped_count: int
    failed_count: int
    circuit_opened: bool
    summaries: list[XiaohongshuSummaryItem]


class XiaohongshuSyncJobCreateData(BaseModel):
    job_id: str
    status: str
    requested_limit: int


class XiaohongshuSyncJobError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class XiaohongshuSyncJobStatusData(BaseModel):
    job_id: str
    status: str
    requested_limit: int
    current: int
    total: int
    message: str
    result: XiaohongshuSyncData | None = None
    error: XiaohongshuSyncJobError | None = None
