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
