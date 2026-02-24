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

data class XiaohongshuSyncRequest(
    val limit: Int? = null,
    @Json(name = "confirm_live") val confirmLive: Boolean = false
)

data class XiaohongshuSummaryItem(
    @Json(name = "note_id") val noteId: String,
    val title: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "summary_markdown") val summaryMarkdown: String
)

data class XiaohongshuSyncData(
    @Json(name = "requested_limit") val requestedLimit: Int,
    @Json(name = "fetched_count") val fetchedCount: Int,
    @Json(name = "new_count") val newCount: Int,
    @Json(name = "skipped_count") val skippedCount: Int,
    @Json(name = "failed_count") val failedCount: Int,
    @Json(name = "circuit_opened") val circuitOpened: Boolean,
    val summaries: List<XiaohongshuSummaryItem>
)

data class XiaohongshuSyncJobCreateData(
    @Json(name = "job_id") val jobId: String,
    val status: String,
    @Json(name = "requested_limit") val requestedLimit: Int
)

data class XiaohongshuSyncJobError(
    val code: String,
    val message: String,
    val details: Map<String, Any?>? = null
)

data class XiaohongshuSyncJobStatusData(
    @Json(name = "job_id") val jobId: String,
    val status: String,
    @Json(name = "requested_limit") val requestedLimit: Int,
    val current: Int,
    val total: Int,
    val message: String,
    val result: XiaohongshuSyncData?,
    val error: XiaohongshuSyncJobError?
)
