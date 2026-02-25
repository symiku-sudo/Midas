package com.midas.client.ui.screen

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.data.repo.MidasRepository
import com.midas.client.data.repo.SettingsRepository
import com.midas.client.util.AppResult
import com.midas.client.util.EditableConfigField
import com.midas.client.util.EditableConfigFormMapper
import com.midas.client.util.ErrorContext
import com.midas.client.util.ErrorMessageMapper
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
    val editableConfigFields: List<EditableConfigField> = emptyList(),
    val isConfigLoading: Boolean = false,
    val isConfigSaving: Boolean = false,
    val isConfigResetting: Boolean = false,
    val configStatus: String = "",
)

data class BilibiliUiState(
    val videoUrlInput: String = "",
    val isLoading: Boolean = false,
    val isSavingNote: Boolean = false,
    val errorMessage: String = "",
    val saveStatus: String = "",
    val result: BilibiliSummaryData? = null,
)

data class XiaohongshuUiState(
    val limitInput: String = "5",
    val isSyncing: Boolean = false,
    val isSavingNotes: Boolean = false,
    val progressCurrent: Int = 0,
    val progressTotal: Int = 0,
    val progressMessage: String = "",
    val errorMessage: String = "",
    val saveStatus: String = "",
    val summaries: List<XiaohongshuSummaryItem> = emptyList(),
    val statsText: String = "",
)

data class NotesUiState(
    val keywordInput: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String = "",
    val actionStatus: String = "",
    val bilibiliNotes: List<BilibiliSavedNote> = emptyList(),
    val xiaohongshuNotes: List<XiaohongshuSavedNote> = emptyList(),
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

    private val _notesState = MutableStateFlow(NotesUiState())
    val notesState: StateFlow<NotesUiState> = _notesState.asStateFlow()

    private var syncPollingJob: Job? = null

    init {
        loadEditableConfig()
    }

    fun onBaseUrlInputChange(newValue: String) {
        _settingsState.update {
            it.copy(
                baseUrlInput = newValue,
                saveStatus = "",
                testStatus = "",
                configStatus = "",
            )
        }
    }

    fun saveBaseUrl() {
        val normalized = settingsRepository.saveServerBaseUrl(_settingsState.value.baseUrlInput)
        _settingsState.update {
            it.copy(
                baseUrlInput = normalized,
                saveStatus = "已保存服务端地址。",
            )
        }
        loadEditableConfig()
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
                            testStatus = "连接失败：${
                                ErrorMessageMapper.format(
                                    code = result.code,
                                    message = result.message,
                                    context = ErrorContext.CONNECTION,
                                )
                            }",
                        )
                    }
                }
            }
        }
    }

    fun onEditableConfigFieldTextChange(path: String, newValue: String) {
        _settingsState.update {
            it.copy(
                editableConfigFields = EditableConfigFormMapper.updateText(
                    fields = it.editableConfigFields,
                    path = path,
                    text = newValue,
                ),
                configStatus = "",
            )
        }
    }

    fun onEditableConfigFieldBooleanChange(path: String, newValue: Boolean) {
        _settingsState.update {
            it.copy(
                editableConfigFields = EditableConfigFormMapper.updateBoolean(
                    fields = it.editableConfigFields,
                    path = path,
                    value = newValue,
                ),
                configStatus = "",
            )
        }
    }

    fun loadEditableConfig() {
        val baseUrl = normalizeCurrentBaseUrl()
        viewModelScope.launch {
            _settingsState.update {
                it.copy(
                    isConfigLoading = true,
                    configStatus = "正在拉取可编辑配置...",
                )
            }

            when (val result = apiRepository.getEditableConfig(baseUrl)) {
                is AppResult.Success -> {
                    _settingsState.update {
                        it.copy(
                            isConfigLoading = false,
                            editableConfigFields = EditableConfigFormMapper.flatten(result.data.settings),
                            configStatus = "已拉取可编辑配置。",
                        )
                    }
                }

                is AppResult.Error -> {
                    _settingsState.update {
                        it.copy(
                            isConfigLoading = false,
                            configStatus = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.CONFIG,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun saveEditableConfig() {
        val baseUrl = normalizeCurrentBaseUrl()
        val fields = _settingsState.value.editableConfigFields
        if (fields.isEmpty()) {
            _settingsState.update { it.copy(configStatus = "请先加载可编辑配置。") }
            return
        }

        val parsed = runCatching { EditableConfigFormMapper.buildPayload(fields) }.getOrElse { throwable ->
            _settingsState.update {
                it.copy(configStatus = throwable.message ?: "配置格式错误。")
            }
            return
        }

        viewModelScope.launch {
            _settingsState.update {
                it.copy(
                    isConfigSaving = true,
                    configStatus = "正在保存配置...",
                )
            }

            when (val result = apiRepository.updateEditableConfig(baseUrl, parsed)) {
                is AppResult.Success -> {
                    _settingsState.update {
                        it.copy(
                            isConfigSaving = false,
                            editableConfigFields = EditableConfigFormMapper.flatten(result.data.settings),
                            configStatus = "配置已保存并生效。",
                        )
                    }
                }

                is AppResult.Error -> {
                    _settingsState.update {
                        it.copy(
                            isConfigSaving = false,
                            configStatus = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.CONFIG,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun resetEditableConfig() {
        val baseUrl = normalizeCurrentBaseUrl()
        viewModelScope.launch {
            _settingsState.update {
                it.copy(
                    isConfigResetting = true,
                    configStatus = "正在恢复默认配置...",
                )
            }

            when (val result = apiRepository.resetEditableConfig(baseUrl)) {
                is AppResult.Success -> {
                    _settingsState.update {
                        it.copy(
                            isConfigResetting = false,
                            editableConfigFields = EditableConfigFormMapper.flatten(result.data.settings),
                            configStatus = "已恢复默认配置。",
                        )
                    }
                }

                is AppResult.Error -> {
                    _settingsState.update {
                        it.copy(
                            isConfigResetting = false,
                            configStatus = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.CONFIG,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun onBilibiliUrlInputChange(newValue: String) {
        _bilibiliState.update { it.copy(videoUrlInput = newValue, errorMessage = "", saveStatus = "") }
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
                it.copy(isLoading = true, errorMessage = "", saveStatus = "", result = null)
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
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.BILIBILI,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun saveCurrentBilibiliResult() {
        val baseUrl = normalizeCurrentBaseUrl()
        val summary = _bilibiliState.value.result
        if (summary == null) {
            _bilibiliState.update { it.copy(saveStatus = "暂无可保存的总结结果。") }
            return
        }

        viewModelScope.launch {
            _bilibiliState.update { it.copy(isSavingNote = true, saveStatus = "") }
            when (val result = apiRepository.saveBilibiliNote(baseUrl, summary)) {
                is AppResult.Success -> {
                    _bilibiliState.update {
                        it.copy(
                            isSavingNote = false,
                            saveStatus = "已保存 B 站笔记：${result.data.noteId}",
                        )
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _bilibiliState.update {
                        it.copy(
                            isSavingNote = false,
                            saveStatus = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.BILIBILI,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun onXiaohongshuLimitInputChange(newValue: String) {
        _xiaohongshuState.update { it.copy(limitInput = newValue, errorMessage = "", saveStatus = "") }
    }

    fun startXiaohongshuSync() {
        val baseUrl = normalizeCurrentBaseUrl()
        val limit = _xiaohongshuState.value.limitInput.toIntOrNull()
        if (limit == null || limit <= 0) {
            _xiaohongshuState.update { it.copy(errorMessage = "同步数量必须为正整数。") }
            return
        }

        syncPollingJob?.cancel()
        syncPollingJob = viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isSyncing = true,
                    isSavingNotes = false,
                    progressCurrent = 0,
                    progressTotal = limit,
                    progressMessage = "正在创建同步任务...",
                    errorMessage = "",
                    saveStatus = "",
                    summaries = emptyList(),
                    statsText = "",
                )
            }

            when (
                val create = apiRepository.createXiaohongshuSyncJob(
                    baseUrl = baseUrl,
                    limit = limit,
                    confirmLive = true,
                )
            ) {
                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSyncing = false,
                            errorMessage = ErrorMessageMapper.format(
                                code = create.code,
                                message = create.message,
                                context = ErrorContext.XIAOHONGSHU_SYNC,
                            ),
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

    fun saveCurrentXiaohongshuSummaries() {
        val baseUrl = normalizeCurrentBaseUrl()
        val summaries = _xiaohongshuState.value.summaries
        if (summaries.isEmpty()) {
            _xiaohongshuState.update { it.copy(saveStatus = "暂无可保存的小红书总结。") }
            return
        }

        viewModelScope.launch {
            _xiaohongshuState.update { it.copy(isSavingNotes = true, saveStatus = "") }
            when (val result = apiRepository.saveXiaohongshuNotes(baseUrl, summaries)) {
                is AppResult.Success -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSavingNotes = false,
                            saveStatus = "已保存 ${result.data.savedCount} 条小红书笔记。",
                        )
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSavingNotes = false,
                            saveStatus = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.XIAOHONGSHU_SYNC,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun onNotesKeywordInputChange(newValue: String) {
        _notesState.update { it.copy(keywordInput = newValue) }
    }

    fun loadSavedNotes() {
        val baseUrl = normalizeCurrentBaseUrl()
        viewModelScope.launch {
            _notesState.update { it.copy(isLoading = true, errorMessage = "", actionStatus = "") }

            val bilibiliResult = apiRepository.listBilibiliNotes(baseUrl)
            if (bilibiliResult is AppResult.Error) {
                _notesState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = ErrorMessageMapper.format(
                            code = bilibiliResult.code,
                            message = bilibiliResult.message,
                            context = ErrorContext.BILIBILI,
                        ),
                    )
                }
                return@launch
            }

            val xhsResult = apiRepository.listXiaohongshuNotes(baseUrl)
            if (xhsResult is AppResult.Error) {
                _notesState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = ErrorMessageMapper.format(
                            code = xhsResult.code,
                            message = xhsResult.message,
                            context = ErrorContext.XIAOHONGSHU_SYNC,
                        ),
                    )
                }
                return@launch
            }

            val bilibiliData = (bilibiliResult as AppResult.Success).data
            val xhsData = (xhsResult as AppResult.Success).data
            _notesState.update {
                it.copy(
                    isLoading = false,
                    bilibiliNotes = bilibiliData.items,
                    xiaohongshuNotes = xhsData.items,
                )
            }
        }
    }

    fun deleteBilibiliSavedNote(noteId: String) {
        val baseUrl = normalizeCurrentBaseUrl()
        viewModelScope.launch {
            when (val result = apiRepository.deleteBilibiliNote(baseUrl, noteId)) {
                is AppResult.Success -> {
                    _notesState.update {
                        it.copy(actionStatus = "已删除 ${result.data.deletedCount} 条 B 站笔记。", errorMessage = "")
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _notesState.update {
                        it.copy(
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.BILIBILI,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun clearBilibiliSavedNotes() {
        val baseUrl = normalizeCurrentBaseUrl()
        viewModelScope.launch {
            when (val result = apiRepository.clearBilibiliNotes(baseUrl)) {
                is AppResult.Success -> {
                    _notesState.update {
                        it.copy(actionStatus = "已清空 ${result.data.deletedCount} 条 B 站笔记。", errorMessage = "")
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _notesState.update {
                        it.copy(
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.BILIBILI,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun deleteXiaohongshuSavedNote(noteId: String) {
        val baseUrl = normalizeCurrentBaseUrl()
        viewModelScope.launch {
            when (val result = apiRepository.deleteXiaohongshuNote(baseUrl, noteId)) {
                is AppResult.Success -> {
                    _notesState.update {
                        it.copy(actionStatus = "已删除 ${result.data.deletedCount} 条小红书笔记。", errorMessage = "")
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _notesState.update {
                        it.copy(
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.XIAOHONGSHU_SYNC,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun clearXiaohongshuSavedNotes() {
        val baseUrl = normalizeCurrentBaseUrl()
        viewModelScope.launch {
            when (val result = apiRepository.clearXiaohongshuNotes(baseUrl)) {
                is AppResult.Success -> {
                    _notesState.update {
                        it.copy(actionStatus = "已清空 ${result.data.deletedCount} 条小红书笔记。", errorMessage = "")
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _notesState.update {
                        it.copy(
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.XIAOHONGSHU_SYNC,
                            ),
                        )
                    }
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
                            errorMessage = ErrorMessageMapper.format(
                                code = poll.code,
                                message = poll.message,
                                context = ErrorContext.XIAOHONGSHU_JOB,
                            ),
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
                                "同步完成：请求 ${result.requestedLimit}，拉取 ${result.fetchedCount}，新增 ${result.newCount}，跳过 ${result.skippedCount}，失败 ${result.failedCount}"
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
                                ErrorMessageMapper.format(
                                    code = err.code,
                                    message = err.message,
                                    context = ErrorContext.XIAOHONGSHU_JOB,
                                )
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
