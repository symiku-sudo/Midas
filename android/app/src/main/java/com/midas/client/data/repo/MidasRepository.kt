package com.midas.client.data.repo

import com.midas.client.data.model.ApiEnvelope
import com.midas.client.data.model.BilibiliNoteSaveRequest
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSavedNotesData
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.BilibiliSummaryRequest
import com.midas.client.data.model.EditableConfigData
import com.midas.client.data.model.EditableConfigUpdateRequest
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
import org.json.JSONObject
import retrofit2.Response

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
    ): AppResult<NotesMergeSuggestData> {
        return request(baseUrl) {
            suggestMergeCandidates(
                NotesMergeSuggestRequest(
                    source = source,
                    limit = limit,
                    minScore = minScore,
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
