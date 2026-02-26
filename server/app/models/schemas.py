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


class BilibiliNoteSaveRequest(BaseModel):
    video_url: str = Field(min_length=3, max_length=2000)
    summary_markdown: str = Field(min_length=1)
    elapsed_ms: int = Field(ge=0)
    transcript_chars: int = Field(ge=0)
    title: str = Field(default="", max_length=200)


class BilibiliSavedNote(BaseModel):
    note_id: str
    title: str
    video_url: str
    summary_markdown: str
    elapsed_ms: int
    transcript_chars: int
    saved_at: str


class BilibiliSavedNotesData(BaseModel):
    total: int
    items: list[BilibiliSavedNote]


class XiaohongshuSyncRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=100)
    confirm_live: bool = False


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


class XiaohongshuNotesSaveRequest(BaseModel):
    notes: list[XiaohongshuSummaryItem] = Field(min_length=1)


class XiaohongshuSavedNote(BaseModel):
    note_id: str
    title: str
    source_url: str
    summary_markdown: str
    saved_at: str


class XiaohongshuSavedNotesData(BaseModel):
    total: int
    items: list[XiaohongshuSavedNote]


class NotesDeleteData(BaseModel):
    deleted_count: int


class NotesSaveBatchData(BaseModel):
    saved_count: int


class XiaohongshuSyncedNotesPruneData(BaseModel):
    candidate_count: int
    deleted_count: int


class XiaohongshuCaptureRefreshData(BaseModel):
    har_path: str
    request_url_host: str
    request_method: str
    headers_count: int
    non_empty_keys: int
    empty_keys: list[str]


class XiaohongshuSyncCooldownData(BaseModel):
    mode: str
    allowed: bool
    remaining_seconds: int
    next_allowed_at_epoch: int
    last_sync_at_epoch: int
    min_interval_seconds: int


class EditableConfigData(BaseModel):
    settings: dict[str, Any]


class EditableConfigUpdateRequest(BaseModel):
    settings: dict[str, Any]


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
