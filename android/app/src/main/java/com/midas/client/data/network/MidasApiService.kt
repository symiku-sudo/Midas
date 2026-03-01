package com.midas.client.data.network

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
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path

interface MidasApiService {
    @GET("health")
    suspend fun health(): Response<ApiEnvelope<HealthData>>

    @POST("api/bilibili/summarize")
    suspend fun summarizeBilibili(
        @Body request: BilibiliSummaryRequest
    ): Response<ApiEnvelope<BilibiliSummaryData>>

    @POST("api/notes/bilibili/save")
    suspend fun saveBilibiliNote(
        @Body request: BilibiliNoteSaveRequest
    ): Response<ApiEnvelope<BilibiliSavedNote>>

    @GET("api/notes/bilibili")
    suspend fun listBilibiliNotes(): Response<ApiEnvelope<BilibiliSavedNotesData>>

    @DELETE("api/notes/bilibili/{noteId}")
    suspend fun deleteBilibiliNote(
        @Path("noteId") noteId: String
    ): Response<ApiEnvelope<NotesDeleteData>>

    @DELETE("api/notes/bilibili")
    suspend fun clearBilibiliNotes(): Response<ApiEnvelope<NotesDeleteData>>

    @POST("api/xiaohongshu/summarize-url")
    suspend fun summarizeXiaohongshuUrl(
        @Body request: XiaohongshuSummarizeUrlRequest
    ): Response<ApiEnvelope<XiaohongshuSummaryItem>>

    @POST("api/notes/xiaohongshu/save-batch")
    suspend fun saveXiaohongshuNotes(
        @Body request: XiaohongshuNotesSaveRequest
    ): Response<ApiEnvelope<NotesSaveBatchData>>

    @GET("api/notes/xiaohongshu")
    suspend fun listXiaohongshuNotes(): Response<ApiEnvelope<XiaohongshuSavedNotesData>>

    @DELETE("api/notes/xiaohongshu/{noteId}")
    suspend fun deleteXiaohongshuNote(
        @Path("noteId") noteId: String
    ): Response<ApiEnvelope<NotesDeleteData>>

    @DELETE("api/notes/xiaohongshu")
    suspend fun clearXiaohongshuNotes(): Response<ApiEnvelope<NotesDeleteData>>

    @POST("api/notes/merge/suggest")
    suspend fun suggestMergeCandidates(
        @Body request: NotesMergeSuggestRequest
    ): Response<ApiEnvelope<NotesMergeSuggestData>>

    @POST("api/notes/merge/preview")
    suspend fun previewMerge(
        @Body request: NotesMergePreviewRequest
    ): Response<ApiEnvelope<NotesMergePreviewData>>

    @POST("api/notes/merge/commit")
    suspend fun commitMerge(
        @Body request: NotesMergeCommitRequest
    ): Response<ApiEnvelope<NotesMergeCommitData>>

    @POST("api/notes/merge/rollback")
    suspend fun rollbackMerge(
        @Body request: NotesMergeRollbackRequest
    ): Response<ApiEnvelope<NotesMergeRollbackData>>

    @POST("api/notes/merge/finalize")
    suspend fun finalizeMerge(
        @Body request: NotesMergeFinalizeRequest
    ): Response<ApiEnvelope<NotesMergeFinalizeData>>

    @POST("api/xiaohongshu/capture/refresh")
    suspend fun refreshXiaohongshuCapture():
        Response<ApiEnvelope<XiaohongshuCaptureRefreshData>>

    @POST("api/xiaohongshu/auth/update")
    suspend fun updateXiaohongshuAuth(
        @Body request: XiaohongshuAuthUpdateRequest
    ): Response<ApiEnvelope<XiaohongshuAuthUpdateData>>

    @GET("api/config/editable")
    suspend fun getEditableConfig(): Response<ApiEnvelope<EditableConfigData>>

    @PUT("api/config/editable")
    suspend fun updateEditableConfig(
        @Body request: EditableConfigUpdateRequest
    ): Response<ApiEnvelope<EditableConfigData>>

    @POST("api/config/editable/reset")
    suspend fun resetEditableConfig(): Response<ApiEnvelope<EditableConfigData>>

}
