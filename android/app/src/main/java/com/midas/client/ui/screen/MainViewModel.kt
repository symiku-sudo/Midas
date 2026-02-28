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
    val configFieldErrors: Map<String, String> = emptyMap(),
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
    val urlInput: String = "",
    val isSummarizingUrl: Boolean = false,
    val isRefreshingCaptureConfig: Boolean = false,
    val savingSingleNoteIds: Set<String> = emptySet(),
    val savedNoteIds: Set<String> = emptySet(),
    val errorMessage: String = "",
    val saveStatus: String = "",
    val captureRefreshStatus: String = "",
    val summarizeUrlStatus: String = "",
    val summaries: List<XiaohongshuSummaryItem> = emptyList(),
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

    private var autoSaveConfigJob: Job? = null

    init {
        loadEditableConfig()
        loadSavedNotes()
    }

    fun onAppForeground() {
        loadSavedNotes()
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
        val updatedFields = EditableConfigFormMapper.updateText(
            fields = _settingsState.value.editableConfigFields,
            path = path,
            text = newValue,
        )
        val error = updatedFields.firstOrNull { it.path == path }
            ?.let { EditableConfigFormMapper.validateField(it) }
        _settingsState.update {
            val nextErrors = it.configFieldErrors.toMutableMap()
            if (error.isNullOrBlank()) {
                nextErrors.remove(path)
            } else {
                nextErrors[path] = error
            }
            it.copy(
                editableConfigFields = updatedFields,
                configFieldErrors = nextErrors,
                configStatus = error ?: "",
            )
        }
        if (error.isNullOrBlank()) {
            scheduleAutoSaveConfig()
        } else {
            autoSaveConfigJob?.cancel()
        }
    }

    fun onEditableConfigFieldBooleanChange(path: String, newValue: Boolean) {
        val updatedFields = EditableConfigFormMapper.updateBoolean(
            fields = _settingsState.value.editableConfigFields,
            path = path,
            value = newValue,
        )
        val error = updatedFields.firstOrNull { it.path == path }
            ?.let { EditableConfigFormMapper.validateField(it) }
        _settingsState.update {
            val nextErrors = it.configFieldErrors.toMutableMap()
            if (error.isNullOrBlank()) {
                nextErrors.remove(path)
            } else {
                nextErrors[path] = error
            }
            it.copy(
                editableConfigFields = updatedFields,
                configFieldErrors = nextErrors,
                configStatus = error ?: "",
            )
        }
        if (error.isNullOrBlank()) {
            scheduleAutoSaveConfig()
        } else {
            autoSaveConfigJob?.cancel()
        }
    }

    fun loadEditableConfig() {
        val baseUrl = requireBaseUrl {
            _settingsState.update {
                it.copy(
                    isConfigLoading = false,
                    configStatus = "请先填写服务端地址。",
                )
            }
        } ?: return
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
                            configFieldErrors = emptyMap(),
                            configStatus = "已拉取可编辑配置。",
                        )
                    }
                }

                is AppResult.Error -> {
                    _settingsState.update {
                        it.copy(
                            isConfigLoading = false,
                            configFieldErrors = emptyMap(),
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
        val baseUrl = requireBaseUrl {
            _settingsState.update {
                it.copy(
                    isConfigResetting = false,
                    configStatus = "请先填写服务端地址。",
                )
            }
        } ?: return
        autoSaveConfigJob?.cancel()
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
                            configFieldErrors = emptyMap(),
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

    private fun scheduleAutoSaveConfig() {
        autoSaveConfigJob?.cancel()
        autoSaveConfigJob = viewModelScope.launch {
            delay(600)
            val baseUrl = requireBaseUrl {
                _settingsState.update {
                    it.copy(
                        isConfigSaving = false,
                        configStatus = "请先填写服务端地址。",
                    )
                }
            } ?: return@launch
            val snapshot = _settingsState.value
            if (snapshot.editableConfigFields.isEmpty()) {
                return@launch
            }
            if (snapshot.configFieldErrors.isNotEmpty()) {
                _settingsState.update {
                    it.copy(configStatus = "请先修正红色配置项。")
                }
                return@launch
            }

            val parsed = runCatching {
                EditableConfigFormMapper.buildPayload(snapshot.editableConfigFields)
            }.getOrElse { throwable ->
                _settingsState.update {
                    it.copy(configStatus = throwable.message ?: "配置格式错误。")
                }
                return@launch
            }

            _settingsState.update {
                it.copy(
                    isConfigSaving = true,
                    configStatus = "正在自动保存配置...",
                )
            }

            when (val result = apiRepository.updateEditableConfig(baseUrl, parsed)) {
                is AppResult.Success -> {
                    _settingsState.update {
                        it.copy(
                            isConfigSaving = false,
                            editableConfigFields = EditableConfigFormMapper.flatten(result.data.settings),
                            configFieldErrors = emptyMap(),
                            configStatus = "配置已自动保存。",
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

    fun onBilibiliUrlInputChange(newValue: String) {
        _bilibiliState.update { it.copy(videoUrlInput = newValue, errorMessage = "", saveStatus = "") }
    }

    fun submitBilibiliSummary() {
        val baseUrl = requireBaseUrl {
            _bilibiliState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
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
        val baseUrl = requireBaseUrl {
            _bilibiliState.update { it.copy(saveStatus = "请先填写服务端地址。") }
        } ?: return
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

    fun onXiaohongshuUrlInputChange(newValue: String) {
        _xiaohongshuState.update {
            it.copy(
                urlInput = newValue,
                errorMessage = "",
                summarizeUrlStatus = "",
                saveStatus = "",
                captureRefreshStatus = "",
            )
        }
    }

    fun summarizeXiaohongshuByUrl() {
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        val url = _xiaohongshuState.value.urlInput.trim()
        if (url.isEmpty()) {
            _xiaohongshuState.update { it.copy(errorMessage = "请输入小红书笔记链接。") }
            return
        }

        viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isSummarizingUrl = true,
                    errorMessage = "",
                    summarizeUrlStatus = "",
                    saveStatus = "",
                    captureRefreshStatus = "",
                )
            }
            when (val result = apiRepository.summarizeXiaohongshuUrl(baseUrl, url)) {
                is AppResult.Success -> {
                    _xiaohongshuState.update {
                        val currentList = it.summaries.filter { summary ->
                            summary.noteId != result.data.noteId
                        }
                        it.copy(
                            isSummarizingUrl = false,
                            summaries = listOf(result.data) + currentList,
                            summarizeUrlStatus = "单篇笔记总结完成，可直接保存。",
                        )
                    }
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSummarizingUrl = false,
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

    fun saveSingleXiaohongshuSummary(item: XiaohongshuSummaryItem) {
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(saveStatus = "请先填写服务端地址。") }
        } ?: return
        val noteId = item.noteId
        val current = _xiaohongshuState.value
        if (noteId in current.savedNoteIds) {
            _xiaohongshuState.update { it.copy(saveStatus = "该笔记已保存。") }
            return
        }
        if (noteId in current.savingSingleNoteIds) {
            return
        }

        viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    saveStatus = "",
                    captureRefreshStatus = "",
                    savingSingleNoteIds = it.savingSingleNoteIds + noteId,
                )
            }
            when (val result = apiRepository.saveXiaohongshuNotes(baseUrl, listOf(item))) {
                is AppResult.Success -> {
                    _xiaohongshuState.update {
                        it.copy(
                            savingSingleNoteIds = it.savingSingleNoteIds - noteId,
                            savedNoteIds = it.savedNoteIds + noteId,
                            saveStatus = "已保存该篇小红书笔记。",
                        )
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            savingSingleNoteIds = it.savingSingleNoteIds - noteId,
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

    fun submitXiaohongshuMobileAuth(cookie: String, userAgent: String) {
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        if (_xiaohongshuState.value.isRefreshingCaptureConfig) {
            return
        }
        val normalizedCookie = cookie.trim()
        if (normalizedCookie.isEmpty()) {
            _xiaohongshuState.update {
                it.copy(errorMessage = "未获取到 Cookie，请先在授权页完成登录后再上传。")
            }
            return
        }

        viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isRefreshingCaptureConfig = true,
                    captureRefreshStatus = "正在上传手机登录态...",
                    saveStatus = "",
                    errorMessage = "",
                )
            }

            when (
                val result = apiRepository.updateXiaohongshuAuth(
                    baseUrl = baseUrl,
                    cookie = normalizedCookie,
                    userAgent = userAgent.trim(),
                    origin = "https://www.xiaohongshu.com",
                    referer = "https://www.xiaohongshu.com/",
                )
            ) {
                is AppResult.Success -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isRefreshingCaptureConfig = false,
                            captureRefreshStatus = "已上传手机登录态：Cookie 条目 ${result.data.cookiePairs}。",
                        )
                    }
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isRefreshingCaptureConfig = false,
                            captureRefreshStatus = "",
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

    fun refreshXiaohongshuAuthConfig() {
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        if (_xiaohongshuState.value.isRefreshingCaptureConfig) {
            return
        }

        viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isRefreshingCaptureConfig = true,
                    captureRefreshStatus = "正在更新 auth 配置...",
                    saveStatus = "",
                    errorMessage = "",
                )
            }
            when (val result = apiRepository.refreshXiaohongshuCapture(baseUrl)) {
                is AppResult.Success -> {
                    val emptyKeys = result.data.emptyKeys
                    val missingHint = if (emptyKeys.isNotEmpty()) {
                        "，空字段 ${emptyKeys.joinToString(",")}"
                    } else {
                        ""
                    }
                    _xiaohongshuState.update {
                        it.copy(
                            isRefreshingCaptureConfig = false,
                            captureRefreshStatus = (
                                "已更新auth配置：${result.data.requestMethod} ${result.data.requestUrlHost}" +
                                    "（headers=${result.data.headersCount}$missingHint）"
                                ),
                        )
                    }
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isRefreshingCaptureConfig = false,
                            captureRefreshStatus = "",
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

    fun onNotesKeywordInputChange(newValue: String) {
        _notesState.update { it.copy(keywordInput = newValue) }
    }

    fun loadSavedNotes() {
        val baseUrl = requireBaseUrl {
            _notesState.update {
                it.copy(
                    isLoading = false,
                    errorMessage = "请先填写服务端地址。",
                )
            }
        } ?: return
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
        val baseUrl = requireBaseUrl {
            _notesState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
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
        val baseUrl = requireBaseUrl {
            _notesState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
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
        val baseUrl = requireBaseUrl {
            _notesState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
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
        val baseUrl = requireBaseUrl {
            _notesState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
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

    override fun onCleared() {
        autoSaveConfigJob?.cancel()
        super.onCleared()
    }

    private fun requireBaseUrl(onMissing: () -> Unit): String? {
        val baseUrl = normalizeCurrentBaseUrl()
        if (baseUrl.isNotEmpty()) {
            return baseUrl
        }
        onMissing()
        return null
    }

    private fun normalizeCurrentBaseUrl(): String {
        val normalized = UrlNormalizer.normalize(_settingsState.value.baseUrlInput)
        _settingsState.update { it.copy(baseUrlInput = normalized) }
        return normalized
    }

}
