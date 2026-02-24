package com.midas.client.data.network

import com.midas.client.data.model.ApiEnvelope
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.BilibiliSummaryRequest
import com.midas.client.data.model.HealthData
import com.midas.client.data.model.XiaohongshuSyncData
import com.midas.client.data.model.XiaohongshuSyncJobCreateData
import com.midas.client.data.model.XiaohongshuSyncJobStatusData
import com.midas.client.data.model.XiaohongshuSyncRequest
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface MidasApiService {
    @GET("health")
    suspend fun health(): Response<ApiEnvelope<HealthData>>

    @POST("api/bilibili/summarize")
    suspend fun summarizeBilibili(
        @Body request: BilibiliSummaryRequest
    ): Response<ApiEnvelope<BilibiliSummaryData>>

    @POST("api/xiaohongshu/sync")
    suspend fun syncXiaohongshu(
        @Body request: XiaohongshuSyncRequest
    ): Response<ApiEnvelope<XiaohongshuSyncData>>

    @POST("api/xiaohongshu/sync/jobs")
    suspend fun createXiaohongshuSyncJob(
        @Body request: XiaohongshuSyncRequest
    ): Response<ApiEnvelope<XiaohongshuSyncJobCreateData>>

    @GET("api/xiaohongshu/sync/jobs/{jobId}")
    suspend fun getXiaohongshuSyncJob(
        @Path("jobId") jobId: String
    ): Response<ApiEnvelope<XiaohongshuSyncJobStatusData>>
}
