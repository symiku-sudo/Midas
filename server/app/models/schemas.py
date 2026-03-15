from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthData(BaseModel):
    status: str = "ok"


class FinanceWatchlistItem(BaseModel):
    name: str = ""
    symbol: str
    price: float | None = None
    change_pct: str = "N/A"
    alert_hint: str = ""
    alert_active: bool = False
    related_news_count: int = 0
    related_keywords: list[str] = Field(default_factory=list)


class FinanceNewsItem(BaseModel):
    title: str
    link: str = ""
    publisher: str = ""
    published: str = ""
    category: str = ""
    matched_keywords: list[str] = Field(default_factory=list)
    related_symbols: list[str] = Field(default_factory=list)
    related_watchlist_names: list[str] = Field(default_factory=list)


class FinanceNewsDebugData(BaseModel):
    entries_scanned: int = 0
    entries_filtered_by_source: int = 0
    matched_entries_count: int = 0
    top_news_count: int = 0
    digest_item_count: int = 0
    digest_prompt_chars: int = 0
    digest_status: str = ""
    digest_last_generated_at: str = ""
    top_unmatched_titles: list[str] = Field(default_factory=list)


class FinanceMarketAlertDebugData(BaseModel):
    alert_enabled: bool = False
    alert_sent: bool = False
    last_alert_time: str = ""
    last_alert_signature: str = ""
    last_alert_summary: str = ""
    last_alert_status: str = ""


class FinanceFocusCard(BaseModel):
    title: str
    summary: str = ""
    priority: str = "MEDIUM"
    kind: str = "NEWS"
    action_type: str = "MONITOR"
    action_label: str = ""
    action_hint: str = ""
    reasons: list[str] = Field(default_factory=list)
    related_symbols: list[str] = Field(default_factory=list)
    related_watchlist_names: list[str] = Field(default_factory=list)


class FinanceSignalsData(BaseModel):
    update_time: str
    news_last_fetch_time: str = ""
    news_stale: bool = False
    watchlist_preview: list[FinanceWatchlistItem]
    top_news: list[FinanceNewsItem] = Field(default_factory=list)
    focus_cards: list[FinanceFocusCard] = Field(default_factory=list)
    watchlist_ntfy_enabled: bool = False
    ai_insight_text: str
    news_debug: FinanceNewsDebugData = Field(default_factory=FinanceNewsDebugData)
    market_alert_debug: FinanceMarketAlertDebugData = Field(
        default_factory=FinanceMarketAlertDebugData
    )


class FinanceWatchlistNtfyUpdateRequest(BaseModel):
    enabled: bool


class FinanceWatchlistNtfyData(BaseModel):
    enabled: bool


class AssetImageFillData(BaseModel):
    image_count: int = Field(ge=1)
    category_amounts: dict[str, float]
    total_amount_wan: float = Field(ge=0)


class AssetSnapshotRecord(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    saved_at: str = Field(min_length=1, max_length=32)
    total_amount_wan: float = Field(ge=0)
    amounts: dict[str, float] = Field(default_factory=dict)


class AssetSnapshotHistoryData(BaseModel):
    total: int
    items: list[AssetSnapshotRecord]


class AssetCurrentData(BaseModel):
    total_amount_wan: float = Field(ge=0)
    amounts: dict[str, float] = Field(default_factory=dict)


class AssetSnapshotSaveRequest(BaseModel):
    id: str = Field(default="", max_length=128)
    saved_at: str = Field(default="", max_length=32)
    total_amount_wan: float = Field(default=0, ge=0)
    amounts: dict[str, float] = Field(default_factory=dict)


class AssetCurrentUpdateRequest(BaseModel):
    total_amount_wan: float = Field(default=0, ge=0)
    amounts: dict[str, float] = Field(default_factory=dict)


class BilibiliSummaryRequest(BaseModel):
    video_url: str = Field(min_length=3, max_length=2000)


class BilibiliSummaryData(BaseModel):
    video_url: str
    summary_markdown: str
    elapsed_ms: int
    transcript_chars: int


class AsyncJobCreateData(BaseModel):
    job_id: str
    job_type: str
    status: str
    message: str
    submitted_at: str
    retry_of_job_id: str = ""
    progress_current: int = 0
    progress_total: int = 0


class AsyncJobErrorData(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class AsyncJobProgressData(BaseModel):
    current: int = 0
    total: int = 0


class AsyncJobListItem(BaseModel):
    job_id: str
    job_type: str
    status: str
    message: str
    submitted_at: str
    started_at: str = ""
    finished_at: str = ""
    retry_of_job_id: str = ""
    progress: AsyncJobProgressData | None = None


class AsyncJobListData(BaseModel):
    total: int
    items: list[AsyncJobListItem]


class AsyncJobStatusData(BaseModel):
    job_id: str
    job_type: str
    status: str
    message: str
    submitted_at: str
    started_at: str = ""
    finished_at: str = ""
    retry_of_job_id: str = ""
    request_payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: AsyncJobErrorData | None = None
    progress: AsyncJobProgressData | None = None


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


class UnifiedNoteItem(BaseModel):
    source: str
    note_id: str
    title: str
    source_url: str
    summary_markdown: str
    saved_at: str


class UnifiedNotesData(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[UnifiedNoteItem]


class XiaohongshuUrlSummaryRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class XiaohongshuSummaryItem(BaseModel):
    note_id: str
    title: str
    source_url: str
    summary_markdown: str


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
    min_score: float = Field(default=0.35, ge=0.0, le=1.0)
    include_weak: bool = False


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
    relation_level: str
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


class EditableConfigData(BaseModel):
    settings: dict[str, Any]


class EditableConfigUpdateRequest(BaseModel):
    settings: dict[str, Any]
