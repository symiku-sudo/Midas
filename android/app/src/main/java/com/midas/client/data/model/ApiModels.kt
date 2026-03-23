package com.midas.client.data.model

import com.squareup.moshi.Json

data class ApiEnvelope<T>(
    val ok: Boolean,
    val code: String,
    val message: String,
    val data: T?,
    @Json(name = "request_id") val requestId: String?
)

data class ErrorEnvelope(
    val ok: Boolean? = null,
    val code: String? = null,
    val message: String? = null,
    val data: Map<String, Any?>? = null,
    @Json(name = "request_id") val requestId: String? = null
)

data class HealthData(
    val status: String
)

data class FinanceWatchlistItem(
    val name: String = "",
    val symbol: String,
    val price: Double? = null,
    @Json(name = "change_pct") val changePct: String = "N/A",
    @Json(name = "alert_hint") val alertHint: String = "",
    @Json(name = "alert_active") val alertActive: Boolean = false,
    @Json(name = "related_news_count") val relatedNewsCount: Int = 0,
    @Json(name = "related_keywords") val relatedKeywords: List<String> = emptyList(),
    @Json(name = "related_asset_categories") val relatedAssetCategories: List<String> = emptyList(),
    @Json(name = "exposure_amount_wan") val exposureAmountWan: Double = 0.0,
    @Json(name = "exposure_relevance") val exposureRelevance: String = "LOW",
)

data class FinanceNewsItem(
    val title: String,
    val link: String = "",
    val publisher: String = "",
    val published: String = "",
    val category: String = "",
    @Json(name = "matched_keywords") val matchedKeywords: List<String> = emptyList(),
    @Json(name = "related_symbols") val relatedSymbols: List<String> = emptyList(),
    @Json(name = "related_watchlist_names") val relatedWatchlistNames: List<String> = emptyList(),
    @Json(name = "related_asset_categories") val relatedAssetCategories: List<String> = emptyList(),
    @Json(name = "exposure_amount_wan") val exposureAmountWan: Double = 0.0,
    @Json(name = "exposure_relevance") val exposureRelevance: String = "LOW",
)

data class FinanceNewsDebugData(
    @Json(name = "entries_scanned") val entriesScanned: Int = 0,
    @Json(name = "entries_filtered_by_source") val entriesFilteredBySource: Int = 0,
    @Json(name = "matched_entries_count") val matchedEntriesCount: Int = 0,
    @Json(name = "top_news_count") val topNewsCount: Int = 0,
    @Json(name = "digest_item_count") val digestItemCount: Int = 0,
    @Json(name = "digest_prompt_chars") val digestPromptChars: Int = 0,
    @Json(name = "digest_status") val digestStatus: String = "",
    @Json(name = "digest_last_generated_at") val digestLastGeneratedAt: String = "",
    @Json(name = "top_unmatched_titles") val topUnmatchedTitles: List<String> = emptyList(),
)

data class FinanceMarketAlertDebugData(
    @Json(name = "alert_enabled") val alertEnabled: Boolean = false,
    @Json(name = "alert_sent") val alertSent: Boolean = false,
    @Json(name = "last_alert_time") val lastAlertTime: String = "",
    @Json(name = "last_alert_signature") val lastAlertSignature: String = "",
    @Json(name = "last_alert_summary") val lastAlertSummary: String = "",
    @Json(name = "last_alert_status") val lastAlertStatus: String = "",
)

data class FinanceFocusCard(
    @Json(name = "card_id") val cardId: String = "",
    val title: String,
    val summary: String = "",
    val priority: String = "MEDIUM",
    val kind: String = "NEWS",
    @Json(name = "action_type") val actionType: String = "MONITOR",
    @Json(name = "action_label") val actionLabel: String = "",
    @Json(name = "action_hint") val actionHint: String = "",
    val reasons: List<String> = emptyList(),
    @Json(name = "related_symbols") val relatedSymbols: List<String> = emptyList(),
    @Json(name = "related_watchlist_names") val relatedWatchlistNames: List<String> = emptyList(),
    @Json(name = "related_asset_categories") val relatedAssetCategories: List<String> = emptyList(),
    @Json(name = "exposure_amount_wan") val exposureAmountWan: Double = 0.0,
    @Json(name = "exposure_relevance") val exposureRelevance: String = "LOW",
    @Json(name = "portfolio_impact_summary") val portfolioImpactSummary: String = "",
    val status: String = "ACTIVE",
    @Json(name = "status_updated_at") val statusUpdatedAt: String = "",
    @Json(name = "handled_at") val handledAt: String = "",
)

data class FinanceSignalsData(
    @Json(name = "update_time") val updateTime: String = "",
    @Json(name = "news_last_fetch_time") val newsLastFetchTime: String = "",
    @Json(name = "news_stale") val newsStale: Boolean = false,
    @Json(name = "watchlist_preview") val watchlistPreview: List<FinanceWatchlistItem> = emptyList(),
    @Json(name = "top_news") val topNews: List<FinanceNewsItem> = emptyList(),
    @Json(name = "focus_cards") val focusCards: List<FinanceFocusCard> = emptyList(),
    @Json(name = "watchlist_ntfy_enabled") val watchlistNtfyEnabled: Boolean = false,
    @Json(name = "ai_insight_text") val aiInsightText: String = "",
    @Json(name = "news_debug") val newsDebug: FinanceNewsDebugData = FinanceNewsDebugData(),
    @Json(name = "market_alert_debug") val marketAlertDebug: FinanceMarketAlertDebugData = FinanceMarketAlertDebugData(),
    @Json(name = "history_count") val historyCount: Int = 0,
)

data class FinanceFocusCardActionRequest(
    val status: String,
)

data class FinanceFocusCardActionData(
    @Json(name = "card_id") val cardId: String,
    val status: String,
    @Json(name = "status_updated_at") val statusUpdatedAt: String,
    @Json(name = "handled_at") val handledAt: String = "",
)

data class FinanceFocusCardHistoryItem(
    @Json(name = "card_id") val cardId: String,
    val title: String,
    val summary: String = "",
    val priority: String = "MEDIUM",
    val kind: String = "NEWS",
    @Json(name = "action_type") val actionType: String = "MONITOR",
    @Json(name = "action_label") val actionLabel: String = "",
    val reasons: List<String> = emptyList(),
    @Json(name = "related_symbols") val relatedSymbols: List<String> = emptyList(),
    @Json(name = "related_watchlist_names") val relatedWatchlistNames: List<String> = emptyList(),
    @Json(name = "related_asset_categories") val relatedAssetCategories: List<String> = emptyList(),
    @Json(name = "exposure_amount_wan") val exposureAmountWan: Double = 0.0,
    @Json(name = "exposure_relevance") val exposureRelevance: String = "LOW",
    @Json(name = "portfolio_impact_summary") val portfolioImpactSummary: String = "",
    val status: String = "ACTIVE",
    @Json(name = "first_seen_at") val firstSeenAt: String = "",
    @Json(name = "last_seen_at") val lastSeenAt: String = "",
    @Json(name = "status_updated_at") val statusUpdatedAt: String = "",
    @Json(name = "handled_at") val handledAt: String = "",
)

data class FinanceFocusCardHistoryData(
    val total: Int,
    val items: List<FinanceFocusCardHistoryItem> = emptyList(),
)

data class FinanceWatchlistNtfyUpdateRequest(
    val enabled: Boolean,
)

data class FinanceWatchlistNtfyData(
    val enabled: Boolean,
)

data class AsyncJobCreateData(
    @Json(name = "job_id") val jobId: String,
    @Json(name = "job_type") val jobType: String,
    val status: String,
    val message: String,
    @Json(name = "submitted_at") val submittedAt: String,
    @Json(name = "retry_of_job_id") val retryOfJobId: String = "",
    @Json(name = "progress_current") val progressCurrent: Int = 0,
    @Json(name = "progress_total") val progressTotal: Int = 0,
)

data class AsyncJobErrorData(
    val code: String,
    val message: String,
    val details: Map<String, Any?>? = null,
)

data class AsyncJobProgressData(
    val current: Int = 0,
    val total: Int = 0,
)

data class AsyncJobListItemData(
    @Json(name = "job_id") val jobId: String,
    @Json(name = "job_type") val jobType: String,
    val status: String,
    val message: String,
    @Json(name = "submitted_at") val submittedAt: String,
    @Json(name = "started_at") val startedAt: String = "",
    @Json(name = "finished_at") val finishedAt: String = "",
    @Json(name = "retry_of_job_id") val retryOfJobId: String = "",
    val progress: AsyncJobProgressData? = null,
)

data class AsyncJobListData(
    val total: Int,
    val items: List<AsyncJobListItemData>,
)

data class AsyncJobStatusData(
    @Json(name = "job_id") val jobId: String,
    @Json(name = "job_type") val jobType: String,
    val status: String,
    val message: String,
    @Json(name = "submitted_at") val submittedAt: String,
    @Json(name = "started_at") val startedAt: String = "",
    @Json(name = "finished_at") val finishedAt: String = "",
    @Json(name = "retry_of_job_id") val retryOfJobId: String = "",
    @Json(name = "request_payload") val requestPayload: Map<String, Any?> = emptyMap(),
    val result: Map<String, Any?>? = null,
    val error: AsyncJobErrorData? = null,
    val progress: AsyncJobProgressData? = null,
)

data class BilibiliSummaryRequest(
    @Json(name = "video_url") val videoUrl: String
)

data class BilibiliSummaryData(
    @Json(name = "video_url") val videoUrl: String,
    @Json(name = "summary_markdown") val summaryMarkdown: String,
    @Json(name = "elapsed_ms") val elapsedMs: Int,
    @Json(name = "transcript_chars") val transcriptChars: Int
)

data class BilibiliNoteSaveRequest(
    @Json(name = "video_url") val videoUrl: String,
    @Json(name = "summary_markdown") val summaryMarkdown: String,
    @Json(name = "elapsed_ms") val elapsedMs: Int,
    @Json(name = "transcript_chars") val transcriptChars: Int,
    val title: String = ""
)

data class BilibiliSavedNote(
    @Json(name = "note_id") val noteId: String,
    val title: String,
    @Json(name = "video_url") val videoUrl: String,
    @Json(name = "summary_markdown") val summaryMarkdown: String,
    @Json(name = "elapsed_ms") val elapsedMs: Int,
    @Json(name = "transcript_chars") val transcriptChars: Int,
    @Json(name = "saved_at") val savedAt: String
)

data class BilibiliSavedNotesData(
    val total: Int,
    val items: List<BilibiliSavedNote>
)

data class UnifiedNoteItem(
    val source: String,
    @Json(name = "note_id") val noteId: String,
    val title: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "summary_markdown") val summaryMarkdown: String,
    @Json(name = "saved_at") val savedAt: String,
    @Json(name = "merge_state") val mergeState: String = "ACTIVE",
    @Json(name = "merge_id") val mergeId: String = "",
    @Json(name = "canonical_note_id") val canonicalNoteId: String = "",
    @Json(name = "is_merged") val isMerged: Boolean = false,
    val topics: List<String> = emptyList(),
)

data class UnifiedNotesData(
    val total: Int,
    val limit: Int,
    val offset: Int,
    val items: List<UnifiedNoteItem>,
)

data class NotesReviewTopicItem(
    val topic: String,
    val total: Int,
    @Json(name = "latest_saved_at") val latestSavedAt: String = "",
    val items: List<UnifiedNoteItem> = emptyList(),
)

data class NotesReviewTopicsData(
    @Json(name = "window_days") val windowDays: Int,
    @Json(name = "total_topics") val totalTopics: Int,
    val items: List<NotesReviewTopicItem> = emptyList(),
)

data class NotesTimelineReviewItem(
    val label: String,
    @Json(name = "start_time") val startTime: String = "",
    @Json(name = "end_time") val endTime: String = "",
    val total: Int,
    val items: List<UnifiedNoteItem> = emptyList(),
)

data class NotesTimelineReviewData(
    @Json(name = "window_days") val windowDays: Int,
    val bucket: String,
    @Json(name = "total_buckets") val totalBuckets: Int,
    val items: List<NotesTimelineReviewItem> = emptyList(),
)

data class RelatedNoteItem(
    val source: String,
    @Json(name = "note_id") val noteId: String,
    val title: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "saved_at") val savedAt: String,
    @Json(name = "summary_excerpt") val summaryExcerpt: String = "",
    val score: Double,
    @Json(name = "relation_level") val relationLevel: String,
    @Json(name = "reason_codes") val reasonCodes: List<String> = emptyList(),
    @Json(name = "merge_state") val mergeState: String = "ACTIVE",
    @Json(name = "merge_id") val mergeId: String = "",
    @Json(name = "canonical_note_id") val canonicalNoteId: String = "",
    @Json(name = "is_merged") val isMerged: Boolean = false,
    val topics: List<String> = emptyList(),
)

data class RelatedNotesData(
    val source: String,
    @Json(name = "note_id") val noteId: String,
    val total: Int,
    val items: List<RelatedNoteItem> = emptyList(),
)

data class XiaohongshuSummarizeUrlRequest(
    val url: String
)

data class XiaohongshuSummaryItem(
    @Json(name = "note_id") val noteId: String,
    val title: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "summary_markdown") val summaryMarkdown: String
)

data class XiaohongshuNotesSaveRequest(
    val notes: List<XiaohongshuSummaryItem>
)

data class XiaohongshuSavedNote(
    @Json(name = "note_id") val noteId: String,
    val title: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "summary_markdown") val summaryMarkdown: String,
    @Json(name = "saved_at") val savedAt: String
)

data class XiaohongshuSavedNotesData(
    val total: Int,
    val items: List<XiaohongshuSavedNote>
)

data class NotesDeleteData(
    @Json(name = "deleted_count") val deletedCount: Int
)

data class NotesSaveBatchData(
    @Json(name = "saved_count") val savedCount: Int
)

data class NotesMergeSuggestRequest(
    val source: String = "",
    val limit: Int = 20,
    @Json(name = "min_score") val minScore: Double = 0.35,
    @Json(name = "include_weak") val includeWeak: Boolean = false,
)

data class NotesMergeCandidateNote(
    @Json(name = "note_id") val noteId: String,
    val title: String,
    @Json(name = "saved_at") val savedAt: String,
)

data class NotesMergeCandidateItem(
    val source: String,
    @Json(name = "note_ids") val noteIds: List<String>,
    val score: Double,
    @Json(name = "relation_level") val relationLevel: String = "WEAK",
    @Json(name = "reason_codes") val reasonCodes: List<String>,
    val notes: List<NotesMergeCandidateNote>,
)

data class NotesMergeSuggestData(
    val total: Int,
    val items: List<NotesMergeCandidateItem>,
)

data class NotesMergePreviewRequest(
    val source: String,
    @Json(name = "note_ids") val noteIds: List<String>,
)

data class NotesMergePreviewData(
    val source: String,
    @Json(name = "note_ids") val noteIds: List<String>,
    @Json(name = "merged_title") val mergedTitle: String,
    @Json(name = "merged_summary_markdown") val mergedSummaryMarkdown: String,
    @Json(name = "source_refs") val sourceRefs: List<String>,
    @Json(name = "conflict_markers") val conflictMarkers: List<String>,
)

data class NotesMergeCommitRequest(
    val source: String,
    @Json(name = "note_ids") val noteIds: List<String>,
    @Json(name = "merged_title") val mergedTitle: String = "",
    @Json(name = "merged_summary_markdown") val mergedSummaryMarkdown: String = "",
)

data class NotesMergeCommitData(
    @Json(name = "merge_id") val mergeId: String,
    val status: String,
    val source: String,
    @Json(name = "merged_note_id") val mergedNoteId: String,
    @Json(name = "source_note_ids") val sourceNoteIds: List<String>,
    @Json(name = "can_rollback") val canRollback: Boolean,
    @Json(name = "can_finalize") val canFinalize: Boolean,
)

data class NotesMergeRollbackRequest(
    @Json(name = "merge_id") val mergeId: String,
)

data class NotesMergeRollbackData(
    @Json(name = "merge_id") val mergeId: String,
    val status: String,
    @Json(name = "deleted_merged_count") val deletedMergedCount: Int,
    @Json(name = "restored_source_count") val restoredSourceCount: Int,
)

data class NotesMergeFinalizeRequest(
    @Json(name = "merge_id") val mergeId: String,
    @Json(name = "confirm_destructive") val confirmDestructive: Boolean = true,
)

data class NotesMergeFinalizeData(
    @Json(name = "merge_id") val mergeId: String,
    val status: String,
    @Json(name = "deleted_source_count") val deletedSourceCount: Int,
    @Json(name = "kept_merged_note_id") val keptMergedNoteId: String,
)

data class XiaohongshuCaptureRefreshData(
    @Json(name = "har_path") val harPath: String,
    @Json(name = "request_url_host") val requestUrlHost: String,
    @Json(name = "request_method") val requestMethod: String,
    @Json(name = "headers_count") val headersCount: Int,
    @Json(name = "non_empty_keys") val nonEmptyKeys: Int,
    @Json(name = "empty_keys") val emptyKeys: List<String>
)

data class XiaohongshuAuthUpdateRequest(
    val cookie: String,
    @Json(name = "user_agent") val userAgent: String = "",
    val origin: String = "",
    val referer: String = ""
)

data class XiaohongshuAuthUpdateData(
    @Json(name = "updated_keys") val updatedKeys: List<String>,
    @Json(name = "non_empty_keys") val nonEmptyKeys: Int,
    @Json(name = "cookie_pairs") val cookiePairs: Int
)

data class EditableConfigData(
    val settings: Map<String, Any?>
)

data class EditableConfigUpdateRequest(
    val settings: Map<String, Any?>
)
