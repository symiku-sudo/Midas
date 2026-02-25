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
