package com.midas.client.ui.screen

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.data.repo.MidasRepository
import com.midas.client.data.repo.SettingsRepository
import com.midas.client.util.AppResult
import com.midas.client.util.UrlNormalizer
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val baseUrlInput: String = "",
    val isTesting: Boolean = false,
    val testStatus: String = "",
    val saveStatus: String = "",
)

data class BilibiliUiState(
    val videoUrlInput: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String = "",
    val result: BilibiliSummaryData? = null,
)

data class XiaohongshuUiState(
    val limitInput: String = "5",
    val confirmLive: Boolean = false,
    val isSyncing: Boolean = false,
    val progressCurrent: Int = 0,
    val progressTotal: Int = 0,
    val progressMessage: String = "",
    val errorMessage: String = "",
    val summaries: List<XiaohongshuSummaryItem> = emptyList(),
    val statsText: String = "",
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val settingsRepository = SettingsRepository(application)
    private val apiRepository = MidasRepository()

    private val _settingsState = MutableStateFlow(
        SettingsUiState(baseUrlInput = settingsRepository.getServerBaseUrl())
    )
    val settingsState: StateFlow<SettingsUiState> = _settingsState.asStateFlow()

    private val _bilibiliState = MutableStateFlow(BilibiliUiState())
    val bilibiliState: StateFlow<BilibiliUiState> = _bilibiliState.asStateFlow()

    private val _xiaohongshuState = MutableStateFlow(XiaohongshuUiState())
    val xiaohongshuState: StateFlow<XiaohongshuUiState> = _xiaohongshuState.asStateFlow()

    private var syncPollingJob: Job? = null

    fun onBaseUrlInputChange(newValue: String) {
        _settingsState.update { it.copy(baseUrlInput = newValue, saveStatus = "", testStatus = "") }
    }

    fun saveBaseUrl() {
        val normalized = settingsRepository.saveServerBaseUrl(_settingsState.value.baseUrlInput)
        _settingsState.update {
            it.copy(
                baseUrlInput = normalized,
                saveStatus = "已保存服务端地址。",
            )
        }
    }

    fun testConnection() {
        val baseUrl = normalizeCurrentBaseUrl()
        if (baseUrl.isEmpty()) {
            _settingsState.update { it.copy(testStatus = "请输入服务端地址。") }
            return
        }

        viewModelScope.launch {
            _settingsState.update {
                it.copy(
                    isTesting = true,
                    testStatus = "正在测试连接...",
                )
            }

            when (val result = apiRepository.testConnection(baseUrl)) {
                is AppResult.Success -> {
                    _settingsState.update {
                        it.copy(
                            isTesting = false,
                            testStatus = "连接成功（status=${result.data.status}）",
                        )
                    }
                }

                is AppResult.Error -> {
                    _settingsState.update {
                        it.copy(
                            isTesting = false,
                            testStatus = "连接失败：${result.code} - ${result.message}",
                        )
                    }
                }
            }
        }
    }

    fun onBilibiliUrlInputChange(newValue: String) {
        _bilibiliState.update { it.copy(videoUrlInput = newValue, errorMessage = "") }
    }

    fun submitBilibiliSummary() {
        val baseUrl = normalizeCurrentBaseUrl()
        val videoUrl = _bilibiliState.value.videoUrlInput.trim()
        if (videoUrl.isEmpty()) {
            _bilibiliState.update { it.copy(errorMessage = "请输入 B 站链接。") }
            return
        }

        viewModelScope.launch {
            _bilibiliState.update {
                it.copy(isLoading = true, errorMessage = "", result = null)
            }
            when (val result = apiRepository.summarizeBilibili(baseUrl, videoUrl)) {
                is AppResult.Success -> {
                    _bilibiliState.update {
                        it.copy(isLoading = false, result = result.data)
                    }
                }

                is AppResult.Error -> {
                    _bilibiliState.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = "${result.code} - ${result.message}",
                        )
                    }
                }
            }
        }
    }

    fun onXiaohongshuLimitInputChange(newValue: String) {
        _xiaohongshuState.update { it.copy(limitInput = newValue, errorMessage = "") }
    }

    fun onXiaohongshuConfirmLiveChange(newValue: Boolean) {
        _xiaohongshuState.update { it.copy(confirmLive = newValue) }
    }

    fun startXiaohongshuSync() {
        val baseUrl = normalizeCurrentBaseUrl()
        val limit = _xiaohongshuState.value.limitInput.toIntOrNull()
        val confirmLive = _xiaohongshuState.value.confirmLive
        if (limit == null || limit <= 0) {
            _xiaohongshuState.update { it.copy(errorMessage = "同步数量必须为正整数。") }
            return
        }

        syncPollingJob?.cancel()
        syncPollingJob = viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isSyncing = true,
                    progressCurrent = 0,
                    progressTotal = limit,
                    progressMessage = "正在创建同步任务...",
                    errorMessage = "",
                    summaries = emptyList(),
                    statsText = "",
                )
            }

            when (
                val create = apiRepository.createXiaohongshuSyncJob(
                    baseUrl = baseUrl,
                    limit = limit,
                    confirmLive = confirmLive,
                )
            ) {
                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSyncing = false,
                            errorMessage = "${create.code} - ${create.message}",
                        )
                    }
                }

                is AppResult.Success -> {
                    val jobId = create.data.jobId
                    pollSyncJob(baseUrl, jobId)
                }
            }
        }
    }

    private suspend fun pollSyncJob(baseUrl: String, jobId: String) {
        val maxPollCount = 180
        repeat(maxPollCount) {
            when (val poll = apiRepository.getXiaohongshuSyncJob(baseUrl, jobId)) {
                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSyncing = false,
                            errorMessage = "${poll.code} - ${poll.message}",
                        )
                    }
                    return
                }

                is AppResult.Success -> {
                    val data = poll.data
                    _xiaohongshuState.update {
                        it.copy(
                            progressCurrent = data.current,
                            progressTotal = data.total,
                            progressMessage = data.message,
                        )
                    }

                    when (data.status) {
                        "pending", "running" -> {
                            delay(600)
                        }

                        "succeeded" -> {
                            val result = data.result
                            val stats = if (result == null) {
                                "同步完成（未返回结果明细）。"
                            } else {
                                "同步完成：拉取 ${result.fetchedCount}，新增 ${result.newCount}，跳过 ${result.skippedCount}，失败 ${result.failedCount}"
                            }
                            _xiaohongshuState.update {
                                it.copy(
                                    isSyncing = false,
                                    summaries = result?.summaries ?: emptyList(),
                                    statsText = stats,
                                    progressMessage = "同步任务完成。",
                                )
                            }
                            return
                        }

                        "failed" -> {
                            val err = data.error
                            val message = if (err == null) {
                                "同步任务失败。"
                            } else {
                                "${err.code} - ${err.message}"
                            }
                            _xiaohongshuState.update {
                                it.copy(isSyncing = false, errorMessage = message)
                            }
                            return
                        }

                        else -> {
                            _xiaohongshuState.update {
                                it.copy(isSyncing = false, errorMessage = "未知任务状态：${data.status}")
                            }
                            return
                        }
                    }
                }
            }
        }

        _xiaohongshuState.update {
            it.copy(isSyncing = false, errorMessage = "同步超时，请稍后重试。")
        }
    }

    private fun normalizeCurrentBaseUrl(): String {
        val normalized = UrlNormalizer.normalize(_settingsState.value.baseUrlInput)
        _settingsState.update { it.copy(baseUrlInput = normalized) }
        return normalized
    }
}
