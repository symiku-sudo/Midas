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
import com.midas.client.data.model.NotesDeleteData
import com.midas.client.data.model.NotesSaveBatchData
import com.midas.client.data.model.XiaohongshuCaptureRefreshData
import com.midas.client.data.model.XiaohongshuSyncedNotesPruneData
import com.midas.client.data.model.XiaohongshuSyncData
import com.midas.client.data.model.XiaohongshuSyncCooldownData
import com.midas.client.data.model.XiaohongshuSyncJobCreateData
import com.midas.client.data.model.XiaohongshuSyncJobStatusData
import com.midas.client.data.model.XiaohongshuNotesSaveRequest
import com.midas.client.data.model.XiaohongshuSavedNotesData
import com.midas.client.data.model.XiaohongshuSyncRequest
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

    @POST("api/xiaohongshu/sync")
    suspend fun syncXiaohongshu(
        @Body request: XiaohongshuSyncRequest
    ): Response<ApiEnvelope<XiaohongshuSyncData>>

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

    @POST("api/notes/xiaohongshu/synced/prune")
    suspend fun pruneUnsavedXiaohongshuSyncedNotes():
        Response<ApiEnvelope<XiaohongshuSyncedNotesPruneData>>

    @POST("api/xiaohongshu/capture/refresh")
    suspend fun refreshXiaohongshuCapture():
        Response<ApiEnvelope<XiaohongshuCaptureRefreshData>>

    @GET("api/xiaohongshu/sync/cooldown")
    suspend fun getXiaohongshuSyncCooldown():
        Response<ApiEnvelope<XiaohongshuSyncCooldownData>>

    @GET("api/config/editable")
    suspend fun getEditableConfig(): Response<ApiEnvelope<EditableConfigData>>

    @PUT("api/config/editable")
    suspend fun updateEditableConfig(
        @Body request: EditableConfigUpdateRequest
    ): Response<ApiEnvelope<EditableConfigData>>

    @POST("api/config/editable/reset")
    suspend fun resetEditableConfig(): Response<ApiEnvelope<EditableConfigData>>

    @POST("api/xiaohongshu/sync/jobs")
    suspend fun createXiaohongshuSyncJob(
        @Body request: XiaohongshuSyncRequest
    ): Response<ApiEnvelope<XiaohongshuSyncJobCreateData>>

    @GET("api/xiaohongshu/sync/jobs/{jobId}")
    suspend fun getXiaohongshuSyncJob(
        @Path("jobId") jobId: String
    ): Response<ApiEnvelope<XiaohongshuSyncJobStatusData>>
}
