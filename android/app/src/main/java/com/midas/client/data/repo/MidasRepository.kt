package com.midas.client.data.repo

import com.midas.client.data.model.ApiEnvelope
import com.midas.client.data.model.AsyncJobCreateData
import com.midas.client.data.model.AsyncJobListData
import com.midas.client.data.model.AsyncJobStatusData
import com.midas.client.data.model.AssetCurrentData
import com.midas.client.data.model.AssetCurrentUpdateRequest
import com.midas.client.data.model.AssetImageFillData
import com.midas.client.data.model.AssetSnapshotHistoryData
import com.midas.client.data.model.AssetSnapshotRecordData
import com.midas.client.data.model.AssetSnapshotSaveRequest
import com.midas.client.data.model.BilibiliNoteSaveRequest
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSavedNotesData
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.BilibiliSummaryRequest
import com.midas.client.data.model.EditableConfigData
import com.midas.client.data.model.EditableConfigUpdateRequest
import com.midas.client.data.model.FinanceSignalsData
import com.midas.client.data.model.FinanceWatchlistNtfyData
import com.midas.client.data.model.FinanceWatchlistNtfyUpdateRequest
import com.midas.client.data.model.HealthData
import com.midas.client.data.model.NotesMergeCommitData
import com.midas.client.data.model.NotesMergeCommitRequest
import com.midas.client.data.model.NotesMergeFinalizeData
import com.midas.client.data.model.NotesMergeFinalizeRequest
import com.midas.client.data.model.NotesMergePreviewData
import com.midas.client.data.model.NotesMergePreviewRequest
import com.midas.client.data.model.NotesMergeRollbackData
import com.midas.client.data.model.NotesMergeRollbackRequest
import com.midas.client.data.model.NotesMergeSuggestData
import com.midas.client.data.model.NotesMergeSuggestRequest
import com.midas.client.data.model.NotesDeleteData
import com.midas.client.data.model.NotesSaveBatchData
import com.midas.client.data.model.UnifiedNotesData
import com.midas.client.data.model.XiaohongshuAuthUpdateData
import com.midas.client.data.model.XiaohongshuAuthUpdateRequest
import com.midas.client.data.model.XiaohongshuCaptureRefreshData
import com.midas.client.data.model.XiaohongshuNotesSaveRequest
import com.midas.client.data.model.XiaohongshuSavedNotesData
import com.midas.client.data.model.XiaohongshuSummarizeUrlRequest
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.data.network.MidasApiFactory
import com.midas.client.data.network.MidasApiService
import com.midas.client.util.AppResult
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import retrofit2.Response

data class AssetImageUpload(
    val fileName: String,
    val bytes: ByteArray,
    val mimeType: String = "image/jpeg",
)

class MidasRepository {
    private suspend fun <T> request(
        baseUrl: String,
        call: suspend MidasApiService.() -> Response<ApiEnvelope<T>>,
    ): AppResult<T> {
        return runCatching {
            val api = MidasApiFactory.create(baseUrl)
            unwrap(api.call())
        }.getOrElse { throwable ->
            AppResult.Error(code = "NETWORK_ERROR", message = throwable.message ?: "网络请求失败")
        }
    }

    suspend fun testConnection(baseUrl: String): AppResult<HealthData> {
        return request(baseUrl) { health() }
    }

    suspend fun getFinanceSignals(baseUrl: String): AppResult<FinanceSignalsData> {
        return request(baseUrl) { getFinanceSignals() }
    }

    suspend fun triggerFinanceNewsDigest(baseUrl: String): AppResult<FinanceSignalsData> {
        return request(baseUrl) { triggerFinanceNewsDigest() }
    }

    suspend fun fillAssetStatsFromImages(
        baseUrl: String,
        images: List<AssetImageUpload>,
    ): AppResult<AssetImageFillData> {
        if (images.isEmpty()) {
            return AppResult.Error(code = "INVALID_INPUT", message = "请至少上传 1 张图片。")
        }
        val parts = images.mapIndexedNotNull { index, image ->
            if (image.bytes.isEmpty()) {
                return@mapIndexedNotNull null
            }
            val mime = image.mimeType.trim().ifBlank { "image/jpeg" }
            val mediaType = runCatching { mime.toMediaType() }
                .getOrDefault("image/jpeg".toMediaType())
            val fileName = image.fileName.trim().ifBlank { "asset_${index + 1}.jpg" }
            val body = image.bytes.toRequestBody(mediaType)
            MultipartBody.Part.createFormData("images", fileName, body)
        }
        if (parts.isEmpty()) {
            return AppResult.Error(code = "INVALID_INPUT", message = "图片内容为空，请重新选择。")
        }
        return request(baseUrl) { fillAssetStatsFromImages(parts) }
    }

    suspend fun getAssetCurrent(baseUrl: String): AppResult<AssetCurrentData> {
        return request(baseUrl) { getAssetCurrent() }
    }

    suspend fun saveAssetCurrent(
        baseUrl: String,
        totalAmountWan: Double,
        amounts: Map<String, Double>,
    ): AppResult<AssetCurrentData> {
        return request(baseUrl) {
            saveAssetCurrent(
                AssetCurrentUpdateRequest(
                    totalAmountWan = totalAmountWan,
                    amounts = amounts,
                )
            )
        }
    }

    suspend fun listAssetSnapshots(baseUrl: String): AppResult<AssetSnapshotHistoryData> {
        return request(baseUrl) { listAssetSnapshots() }
    }

    suspend fun saveAssetSnapshot(
        baseUrl: String,
        id: String,
        savedAt: String,
        totalAmountWan: Double,
        amounts: Map<String, Double>,
    ): AppResult<AssetSnapshotRecordData> {
        return request(baseUrl) {
            saveAssetSnapshot(
                AssetSnapshotSaveRequest(
                    id = id,
                    savedAt = savedAt,
                    totalAmountWan = totalAmountWan,
                    amounts = amounts,
                )
            )
        }
    }

    suspend fun deleteAssetSnapshot(
        baseUrl: String,
        recordId: String,
    ): AppResult<NotesDeleteData> {
        return request(baseUrl) { deleteAssetSnapshot(recordId) }
    }

    suspend fun createBilibiliSummaryJob(
        baseUrl: String,
        videoUrl: String,
    ): AppResult<AsyncJobCreateData> {
        return request(baseUrl) {
            createBilibiliSummaryJob(BilibiliSummaryRequest(videoUrl = videoUrl))
        }
    }

    suspend fun createXiaohongshuSummaryJob(
        baseUrl: String,
        url: String,
    ): AppResult<AsyncJobCreateData> {
        return request(baseUrl) {
            createXiaohongshuSummaryJob(XiaohongshuSummarizeUrlRequest(url = url))
        }
    }

    suspend fun getAsyncJob(
        baseUrl: String,
        jobId: String,
    ): AppResult<AsyncJobStatusData> {
        return request(baseUrl) { getAsyncJob(jobId) }
    }

    suspend fun listAsyncJobs(
        baseUrl: String,
        limit: Int = 20,
        status: String = "",
        jobType: String = "",
    ): AppResult<AsyncJobListData> {
        return request(baseUrl) { listAsyncJobs(limit, status, jobType) }
    }

    suspend fun retryAsyncJob(
        baseUrl: String,
        jobId: String,
    ): AppResult<AsyncJobCreateData> {
        return request(baseUrl) { retryAsyncJob(jobId) }
    }

    suspend fun summarizeBilibili(baseUrl: String, videoUrl: String): AppResult<BilibiliSummaryData> {
        return request(baseUrl) {
            summarizeBilibili(BilibiliSummaryRequest(videoUrl = videoUrl))
        }
    }

    suspend fun saveBilibiliNote(
        baseUrl: String,
        summary: BilibiliSummaryData,
        title: String = "",
    ): AppResult<BilibiliSavedNote> {
        return request(baseUrl) {
            saveBilibiliNote(
                BilibiliNoteSaveRequest(
                    videoUrl = summary.videoUrl,
                    summaryMarkdown = summary.summaryMarkdown,
                    elapsedMs = summary.elapsedMs,
                    transcriptChars = summary.transcriptChars,
                    title = title,
                )
            )
        }
    }

    suspend fun listBilibiliNotes(baseUrl: String): AppResult<BilibiliSavedNotesData> {
        return request(baseUrl) { listBilibiliNotes() }
    }

    suspend fun searchNotes(
        baseUrl: String,
        keyword: String = "",
        source: String = "",
        limit: Int = 50,
        offset: Int = 0,
    ): AppResult<UnifiedNotesData> {
        return request(baseUrl) { searchNotes(keyword, source, limit, offset) }
    }

    suspend fun deleteBilibiliNote(baseUrl: String, noteId: String): AppResult<NotesDeleteData> {
        return request(baseUrl) { deleteBilibiliNote(noteId) }
    }

    suspend fun clearBilibiliNotes(baseUrl: String): AppResult<NotesDeleteData> {
        return request(baseUrl) { clearBilibiliNotes() }
    }

    suspend fun summarizeXiaohongshuUrl(
        baseUrl: String,
        url: String,
    ): AppResult<XiaohongshuSummaryItem> {
        return request(baseUrl) {
            summarizeXiaohongshuUrl(XiaohongshuSummarizeUrlRequest(url = url))
        }
    }

    suspend fun saveXiaohongshuNotes(
        baseUrl: String,
        notes: List<XiaohongshuSummaryItem>,
    ): AppResult<NotesSaveBatchData> {
        return request(baseUrl) {
            saveXiaohongshuNotes(XiaohongshuNotesSaveRequest(notes = notes))
        }
    }

    suspend fun listXiaohongshuNotes(baseUrl: String): AppResult<XiaohongshuSavedNotesData> {
        return request(baseUrl) { listXiaohongshuNotes() }
    }

    suspend fun deleteXiaohongshuNote(baseUrl: String, noteId: String): AppResult<NotesDeleteData> {
        return request(baseUrl) { deleteXiaohongshuNote(noteId) }
    }

    suspend fun clearXiaohongshuNotes(baseUrl: String): AppResult<NotesDeleteData> {
        return request(baseUrl) { clearXiaohongshuNotes() }
    }

    suspend fun suggestMergeCandidates(
        baseUrl: String,
        source: String = "",
        limit: Int = 20,
        minScore: Double = 0.35,
        includeWeak: Boolean = false,
    ): AppResult<NotesMergeSuggestData> {
        return request(baseUrl) {
            suggestMergeCandidates(
                NotesMergeSuggestRequest(
                    source = source,
                    limit = limit,
                    minScore = minScore,
                    includeWeak = includeWeak,
                )
            )
        }
    }

    suspend fun previewMerge(
        baseUrl: String,
        source: String,
        noteIds: List<String>,
    ): AppResult<NotesMergePreviewData> {
        return request(baseUrl) {
            previewMerge(
                NotesMergePreviewRequest(
                    source = source,
                    noteIds = noteIds,
                )
            )
        }
    }

    suspend fun commitMerge(
        baseUrl: String,
        source: String,
        noteIds: List<String>,
        mergedTitle: String = "",
        mergedSummaryMarkdown: String = "",
    ): AppResult<NotesMergeCommitData> {
        return request(baseUrl) {
            commitMerge(
                NotesMergeCommitRequest(
                    source = source,
                    noteIds = noteIds,
                    mergedTitle = mergedTitle,
                    mergedSummaryMarkdown = mergedSummaryMarkdown,
                )
            )
        }
    }

    suspend fun rollbackMerge(baseUrl: String, mergeId: String): AppResult<NotesMergeRollbackData> {
        return request(baseUrl) {
            rollbackMerge(NotesMergeRollbackRequest(mergeId = mergeId))
        }
    }

    suspend fun finalizeMerge(baseUrl: String, mergeId: String): AppResult<NotesMergeFinalizeData> {
        return request(baseUrl) {
            finalizeMerge(
                NotesMergeFinalizeRequest(
                    mergeId = mergeId,
                    confirmDestructive = true,
                )
            )
        }
    }

    suspend fun refreshXiaohongshuCapture(baseUrl: String): AppResult<XiaohongshuCaptureRefreshData> {
        return request(baseUrl) { refreshXiaohongshuCapture() }
    }

    suspend fun updateXiaohongshuAuth(
        baseUrl: String,
        cookie: String,
        userAgent: String = "",
        origin: String = "",
        referer: String = "",
    ): AppResult<XiaohongshuAuthUpdateData> {
        return request(baseUrl) {
            updateXiaohongshuAuth(
                XiaohongshuAuthUpdateRequest(
                    cookie = cookie,
                    userAgent = userAgent,
                    origin = origin,
                    referer = referer,
                )
            )
        }
    }

    suspend fun getEditableConfig(baseUrl: String): AppResult<EditableConfigData> {
        return request(baseUrl) { getEditableConfig() }
    }

    suspend fun updateFinanceWatchlistNtfy(
        baseUrl: String,
        enabled: Boolean,
    ): AppResult<FinanceWatchlistNtfyData> {
        return request(baseUrl) {
            updateFinanceWatchlistNtfy(FinanceWatchlistNtfyUpdateRequest(enabled = enabled))
        }
    }

    suspend fun updateEditableConfig(
        baseUrl: String,
        settings: Map<String, Any?>,
    ): AppResult<EditableConfigData> {
        return request(baseUrl) {
            updateEditableConfig(EditableConfigUpdateRequest(settings = settings))
        }
    }

    suspend fun resetEditableConfig(baseUrl: String): AppResult<EditableConfigData> {
        return request(baseUrl) { resetEditableConfig() }
    }

    private fun <T> unwrap(response: Response<ApiEnvelope<T>>): AppResult<T> {
        val body = response.body()
        if (response.isSuccessful && body != null && body.ok && body.data != null) {
            return AppResult.Success(body.data)
        }

        if (body != null) {
            val code = body.code.ifBlank { "UPSTREAM_ERROR" }
            val message = body.message.ifBlank { "请求失败" }
            return AppResult.Error(code = code, message = message)
        }

        val fallbackCode = "HTTP_${response.code()}"
        val fallbackMessage = "请求失败（HTTP ${response.code()}）"
        val errorText = response.errorBody()?.string()
        if (errorText.isNullOrBlank()) {
            return AppResult.Error(code = fallbackCode, message = fallbackMessage)
        }

        return runCatching {
            val json = JSONObject(errorText)
            val code = json.optString("code", fallbackCode)
            val message = json.optString("message", fallbackMessage)
            AppResult.Error(code = code, message = message)
        }.getOrElse {
            AppResult.Error(code = fallbackCode, message = fallbackMessage)
        }
    }
}
