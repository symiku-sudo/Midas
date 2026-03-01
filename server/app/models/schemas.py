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


class XiaohongshuUrlSummaryRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


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


class NotesMergeSuggestRequest(BaseModel):
    source: str = Field(default="", max_length=32)
    limit: int = Field(default=20, ge=1, le=100)
    min_score: float = Field(default=0.55, ge=0.0, le=1.0)


class NotesMergePreviewRequest(BaseModel):
    source: str = Field(min_length=1, max_length=32)
    note_ids: list[str] = Field(min_length=2, max_length=2)


class NotesMergeCommitRequest(BaseModel):
    source: str = Field(min_length=1, max_length=32)
    note_ids: list[str] = Field(min_length=2, max_length=2)
    merged_title: str = Field(default="", max_length=200)
    merged_summary_markdown: str = Field(default="", min_length=0)


class NotesMergeRollbackRequest(BaseModel):
    merge_id: str = Field(min_length=1, max_length=128)


class NotesMergeFinalizeRequest(BaseModel):
    merge_id: str = Field(min_length=1, max_length=128)
    confirm_destructive: bool = False


class NotesMergeCandidateNote(BaseModel):
    note_id: str
    title: str
    saved_at: str


class NotesMergeCandidateItem(BaseModel):
    source: str
    note_ids: list[str]
    score: float
    reason_codes: list[str]
    notes: list[NotesMergeCandidateNote]


class NotesMergeSuggestData(BaseModel):
    total: int
    items: list[NotesMergeCandidateItem]


class NotesMergePreviewData(BaseModel):
    source: str
    note_ids: list[str]
    merged_title: str
    merged_summary_markdown: str
    source_refs: list[str]
    conflict_markers: list[str]


class NotesMergeCommitData(BaseModel):
    merge_id: str
    status: str
    source: str
    merged_note_id: str
    source_note_ids: list[str]
    can_rollback: bool
    can_finalize: bool


class NotesMergeRollbackData(BaseModel):
    merge_id: str
    status: str
    deleted_merged_count: int
    restored_source_count: int


class NotesMergeFinalizeData(BaseModel):
    merge_id: str
    status: str
    deleted_source_count: int
    kept_merged_note_id: str


class XiaohongshuCaptureRefreshData(BaseModel):
    har_path: str
    request_url_host: str
    request_method: str
    headers_count: int
    non_empty_keys: int
    empty_keys: list[str]


class XiaohongshuAuthUpdateRequest(BaseModel):
    cookie: str = Field(min_length=1, max_length=50000)
    user_agent: str = Field(default="", max_length=2000)
    origin: str = Field(default="", max_length=2000)
    referer: str = Field(default="", max_length=2000)


class XiaohongshuAuthUpdateData(BaseModel):
    updated_keys: list[str]
    non_empty_keys: int
    cookie_pairs: int


class XiaohongshuSyncCooldownData(BaseModel):
    mode: str
    allowed: bool
    remaining_seconds: int
    next_allowed_at_epoch: int
    last_sync_at_epoch: int
    min_interval_seconds: int


class XiaohongshuPendingCountData(BaseModel):
    mode: str
    pending_count: int
    scanned_count: int


class EditableConfigData(BaseModel):
    settings: dict[str, Any]


class EditableConfigUpdateRequest(BaseModel):
    settings: dict[str, Any]


class XiaohongshuSyncJobCreateData(BaseModel):
    job_id: str
    status: str
    requested_limit: int


class XiaohongshuSyncJobAckRequest(BaseModel):
    note_ids: list[str] = Field(min_length=1)


class XiaohongshuSyncJobAckData(BaseModel):
    job_id: str
    status: str
    requested_count: int
    acked_count: int
    already_acked_count: int
    missing_note_ids: list[str]
    acked_note_ids: list[str]


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
    summaries: list[XiaohongshuSummaryItem] = Field(default_factory=list)
    result: XiaohongshuSyncData | None = None
    error: XiaohongshuSyncJobError | None = None
