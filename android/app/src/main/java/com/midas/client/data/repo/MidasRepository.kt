package com.midas.client.data.repo

import com.midas.client.data.model.ApiEnvelope
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.BilibiliSummaryRequest
import com.midas.client.data.model.HealthData
import com.midas.client.data.model.XiaohongshuSyncData
import com.midas.client.data.model.XiaohongshuSyncJobCreateData
import com.midas.client.data.model.XiaohongshuSyncJobStatusData
import com.midas.client.data.model.XiaohongshuSyncRequest
import com.midas.client.data.network.MidasApiFactory
import com.midas.client.util.AppResult
import org.json.JSONObject
import retrofit2.Response

class MidasRepository {
    suspend fun testConnection(baseUrl: String): AppResult<HealthData> {
        return runCatching {
            val api = MidasApiFactory.create(baseUrl)
            unwrap(api.health())
        }.getOrElse { throwable ->
            AppResult.Error(code = "NETWORK_ERROR", message = throwable.message ?: "网络请求失败")
        }
    }

    suspend fun summarizeBilibili(baseUrl: String, videoUrl: String): AppResult<BilibiliSummaryData> {
        return runCatching {
            val api = MidasApiFactory.create(baseUrl)
            unwrap(api.summarizeBilibili(BilibiliSummaryRequest(videoUrl = videoUrl)))
        }.getOrElse { throwable ->
            AppResult.Error(code = "NETWORK_ERROR", message = throwable.message ?: "网络请求失败")
        }
    }

    suspend fun syncXiaohongshu(
        baseUrl: String,
        limit: Int,
        confirmLive: Boolean = false,
    ): AppResult<XiaohongshuSyncData> {
        return runCatching {
            val api = MidasApiFactory.create(baseUrl)
            unwrap(
                api.syncXiaohongshu(
                    XiaohongshuSyncRequest(limit = limit, confirmLive = confirmLive)
                )
            )
        }.getOrElse { throwable ->
            AppResult.Error(code = "NETWORK_ERROR", message = throwable.message ?: "网络请求失败")
        }
    }

    suspend fun createXiaohongshuSyncJob(
        baseUrl: String,
        limit: Int,
        confirmLive: Boolean = false,
    ): AppResult<XiaohongshuSyncJobCreateData> {
        return runCatching {
            val api = MidasApiFactory.create(baseUrl)
            unwrap(
                api.createXiaohongshuSyncJob(
                    XiaohongshuSyncRequest(limit = limit, confirmLive = confirmLive)
                )
            )
        }.getOrElse { throwable ->
            AppResult.Error(code = "NETWORK_ERROR", message = throwable.message ?: "网络请求失败")
        }
    }

    suspend fun getXiaohongshuSyncJob(
        baseUrl: String,
        jobId: String,
    ): AppResult<XiaohongshuSyncJobStatusData> {
        return runCatching {
            val api = MidasApiFactory.create(baseUrl)
            unwrap(api.getXiaohongshuSyncJob(jobId))
        }.getOrElse { throwable ->
            AppResult.Error(code = "NETWORK_ERROR", message = throwable.message ?: "网络请求失败")
        }
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
