package com.midas.client.ui.screen

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.midas.client.data.model.AsyncJobListItemData
import com.midas.client.data.model.AssetSnapshotRecordData
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.FinanceFocusCard
import com.midas.client.data.model.FinanceNewsItem
import com.midas.client.data.model.FinanceWatchlistItem
import com.midas.client.data.model.NotesMergeCandidateItem
import com.midas.client.data.model.NotesMergeCommitData
import com.midas.client.data.model.NotesMergePreviewData
import com.midas.client.data.model.UnifiedNoteItem
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.data.model.XiaohongshuSyncData
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.data.network.ServerAuthState
import com.midas.client.data.repo.AssetImageUpload
import com.midas.client.data.repo.MidasRepository
import com.midas.client.data.repo.SettingsRepository
import com.midas.client.util.AssetImageCompressor
import com.midas.client.util.AppResult
import com.midas.client.util.EditableConfigField
import com.midas.client.util.EditableConfigFormMapper
import com.midas.client.util.ErrorContext
import com.midas.client.util.ErrorMessageMapper
import com.midas.client.util.UrlNormalizer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import kotlin.math.round

data class SettingsUiState(
    val baseUrlInput: String = "",
    val accessTokenInput: String = "",
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
    val isRecentJobsLoading: Boolean = false,
    val errorMessage: String = "",
    val submitStatus: String = "",
    val currentJobId: String = "",
    val recentJobsStatus: String = "",
    val saveStatus: String = "",
    val recentJobs: List<AsyncJobListItemData> = emptyList(),
    val result: BilibiliSummaryData? = null,
)

data class XiaohongshuUiState(
    val urlInput: String = "",
    val batchLimitInput: String = "10",
    val isSummarizingUrl: Boolean = false,
    val isRefreshingCaptureConfig: Boolean = false,
    val isRefreshingSyncMeta: Boolean = false,
    val isRecentJobsLoading: Boolean = false,
    val isSavingAllNotes: Boolean = false,
    val savingSingleNoteIds: Set<String> = emptySet(),
    val savedNoteIds: Set<String> = emptySet(),
    val errorMessage: String = "",
    val saveStatus: String = "",
    val captureRefreshStatus: String = "",
    val summarizeUrlStatus: String = "",
    val batchSyncStatus: String = "",
    val currentJobId: String = "",
    val currentJobType: String = "",
    val recentJobsStatus: String = "",
    val recentJobs: List<AsyncJobListItemData> = emptyList(),
    val batchCooldownAllowed: Boolean = true,
    val batchCooldownRemainingSeconds: Int = 0,
    val batchPendingCount: Int = 0,
    val batchScannedCount: Int = 0,
    val summaries: List<XiaohongshuSummaryItem> = emptyList(),
)

data class NotesUiState(
    val keywordInput: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String = "",
    val actionStatus: String = "",
    val mergeStatus: String = "",
    val isMergeSuggesting: Boolean = false,
    val mergeCandidates: List<NotesMergeCandidateItem> = emptyList(),
    val isMergePreviewLoading: Boolean = false,
    val mergePreview: NotesMergePreviewData? = null,
    val mergePreviewKey: String = "",
    val mergePreviewCache: Map<String, NotesMergePreviewData> = emptyMap(),
    val isMergeCommitting: Boolean = false,
    val isMergeRollingBack: Boolean = false,
    val isMergeFinalizing: Boolean = false,
    val lastMergeCommit: NotesMergeCommitData? = null,
    val bilibiliNotes: List<BilibiliSavedNote> = emptyList(),
    val xiaohongshuNotes: List<XiaohongshuSavedNote> = emptyList(),
)

data class AssetCategoryDraft(
    val key: String,
    val label: String,
    val amountInput: String = "",
)

data class AssetHistoryRecord(
    val id: String,
    val savedAt: String,
    val totalAmountWan: Double,
    val amounts: Map<String, Double>,
)

private data class AssetCategorySpec(
    val key: String,
    val label: String,
)

private val assetCategorySpecs = listOf(
    AssetCategorySpec(key = "stock", label = "股票"),
    AssetCategorySpec(key = "equity_fund", label = "股票基金"),
    AssetCategorySpec(key = "gold", label = "黄金"),
    AssetCategorySpec(key = "bond_and_bond_fund", label = "债券/债券基金"),
    AssetCategorySpec(key = "money_market_fund", label = "货币基金"),
    AssetCategorySpec(key = "bank_fixed_deposit", label = "银行定期存款"),
    AssetCategorySpec(key = "bank_current_deposit", label = "银行活期存款"),
    AssetCategorySpec(key = "housing_fund", label = "公积金"),
)
private const val MAX_ASSET_IMAGE_UPLOAD = 5
private const val ASYNC_JOB_POLL_INTERVAL_MS = 1500L
private const val ASYNC_JOB_POLL_MAX_ATTEMPTS = 800
private const val XIAOHONGSHU_SUMMARY_JOB_TYPE = "xiaohongshu_summarize_url"
private const val XIAOHONGSHU_SYNC_JOB_TYPE = "xiaohongshu_sync"

private fun defaultAssetDrafts(): List<AssetCategoryDraft> {
    return assetCategorySpecs.map { spec ->
        AssetCategoryDraft(
            key = spec.key,
            label = spec.label,
            amountInput = "",
        )
    }
}

data class FinanceSignalsUiState(
    val isLoading: Boolean = false,
    val updateTime: String = "",
    val newsLastFetchTime: String = "",
    val newsIsStale: Boolean = false,
    val allFocusCards: List<FinanceFocusCard> = emptyList(),
    val focusCards: List<FinanceFocusCard> = emptyList(),
    val dismissedFocusCardCount: Int = 0,
    val watchlistPreview: List<FinanceWatchlistItem> = emptyList(),
    val topNews: List<FinanceNewsItem> = emptyList(),
    val watchlistNtfyEnabled: Boolean = false,
    val isUpdatingWatchlistNtfy: Boolean = false,
    val isGeneratingNewsDigest: Boolean = false,
    val digestLastGeneratedAt: String = "",
    val aiInsightText: String = "",
    val assetDrafts: List<AssetCategoryDraft> = defaultAssetDrafts(),
    val assetTotalAmount: Double = 0.0,
    val isSavingAssetStats: Boolean = false,
    val isFillingAssetFromImages: Boolean = false,
    val assetErrorMessage: String = "",
    val assetStatusMessage: String = "",
    val assetHistory: List<AssetHistoryRecord> = emptyList(),
    val errorMessage: String = "",
    val statusMessage: String = "",
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val settingsRepository = SettingsRepository(application)
    private val apiRepository = MidasRepository()
    private var dismissedFinanceFocusCardKeys = settingsRepository
        .getDismissedFinanceFocusCardKeys()
        .toMutableSet()

    private val _settingsState = MutableStateFlow(
        SettingsUiState(
            baseUrlInput = settingsRepository.getServerBaseUrl(),
            accessTokenInput = settingsRepository.getServerAccessToken(),
        )
    )
    val settingsState: StateFlow<SettingsUiState> = _settingsState.asStateFlow()

    private val _bilibiliState = MutableStateFlow(BilibiliUiState())
    val bilibiliState: StateFlow<BilibiliUiState> = _bilibiliState.asStateFlow()

    private val _xiaohongshuState = MutableStateFlow(XiaohongshuUiState())
    val xiaohongshuState: StateFlow<XiaohongshuUiState> = _xiaohongshuState.asStateFlow()

    private val _notesState = MutableStateFlow(NotesUiState())
    val notesState: StateFlow<NotesUiState> = _notesState.asStateFlow()

    private val _financeState = MutableStateFlow(FinanceSignalsUiState())
    val financeState: StateFlow<FinanceSignalsUiState> = _financeState.asStateFlow()

    private var autoSaveConfigJob: Job? = null
    private var financeSignalsJob: Job? = null
    private var assetCurrentJob: Job? = null
    private var assetHistoryJob: Job? = null
    private var notesSearchJob: Job? = null
    private var bilibiliSummaryJob: Job? = null
    private var xiaohongshuSummaryJob: Job? = null

    init {
        ServerAuthState.updateAccessToken(settingsRepository.getServerAccessToken())
        loadLocalAssetStats()
        loadEditableConfig()
        loadSavedNotes()
        refreshAsyncJobHistories()
        loadFinanceSignals()
        loadAssetCurrent()
        loadAssetSnapshotHistory()
    }

    fun onAppForeground() {
        loadSavedNotes()
        refreshAsyncJobHistories()
        loadFinanceSignals()
        loadAssetCurrent()
        loadAssetSnapshotHistory()
    }

    fun onAssetAmountInputChange(categoryKey: String, newValue: String) {
        _financeState.update { state ->
            val nextDrafts = state.assetDrafts.map { draft ->
                if (draft.key == categoryKey) {
                    draft.copy(amountInput = newValue)
                } else {
                    draft
                }
            }
            state.copy(
                assetDrafts = nextDrafts,
                assetTotalAmount = computeAssetTotalAmount(nextDrafts),
                assetErrorMessage = "",
                assetStatusMessage = "",
            )
        }
    }

    fun onAssetImagesSelected(uris: List<Uri>) {
        val selectedUris = uris
        if (selectedUris.isEmpty()) {
            return
        }
        val baseUrl = requireBaseUrl {
            _financeState.update {
                it.copy(
                    isFillingAssetFromImages = false,
                    assetErrorMessage = "请先填写服务端地址。",
                    assetStatusMessage = "",
                )
            }
        } ?: return

        val trimmedUris = selectedUris.take(MAX_ASSET_IMAGE_UPLOAD)
        val ignoredCount = selectedUris.size - trimmedUris.size
        viewModelScope.launch {
            _financeState.update {
                it.copy(
                    isFillingAssetFromImages = true,
                    assetErrorMessage = "",
                    assetStatusMessage = if (ignoredCount > 0) {
                        "最多支持 $MAX_ASSET_IMAGE_UPLOAD 张图片，已忽略 $ignoredCount 张。"
                    } else {
                        "正在识别资产图片..."
                    },
                )
            }
            val app = getApplication<Application>()
            val compressed = withContext(Dispatchers.IO) {
                trimmedUris.mapIndexedNotNull { index, uri ->
                    AssetImageCompressor.compressToJpeg(
                        context = app,
                        uri = uri,
                        fallbackName = "asset_image_${index + 1}.jpg",
                    )
                }
            }
            if (compressed.isEmpty()) {
                _financeState.update {
                    it.copy(
                        isFillingAssetFromImages = false,
                        assetErrorMessage = "图片压缩失败，请更换清晰截图后重试。",
                        assetStatusMessage = "",
                    )
                }
                return@launch
            }

            val uploadPayload = compressed.map { item ->
                AssetImageUpload(
                    fileName = item.fileName,
                    bytes = item.bytes,
                    mimeType = item.mimeType,
                )
            }
            when (val result = apiRepository.fillAssetStatsFromImages(baseUrl, uploadPayload)) {
                is AppResult.Success -> {
                    val nextDrafts = buildAssetDraftsForAutoFill(result.data.categoryAmounts)
                    val total = computeAssetTotalAmount(nextDrafts)
                    _financeState.update {
                        it.copy(
                            isFillingAssetFromImages = false,
                            assetDrafts = nextDrafts,
                            assetTotalAmount = total,
                            assetErrorMessage = "",
                            assetStatusMessage = "图片识别完成（${result.data.imageCount} 张），请确认后手动保存。",
                        )
                    }
                }

                is AppResult.Error -> {
                    _financeState.update {
                        it.copy(
                            isFillingAssetFromImages = false,
                            assetErrorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.ASSET,
                            ),
                            assetStatusMessage = "",
                        )
                    }
                }
            }
        }
    }

    fun saveAssetStats() {
        val baseUrl = requireBaseUrl {
            _financeState.update {
                it.copy(
                    isSavingAssetStats = false,
                    isFillingAssetFromImages = false,
                    assetErrorMessage = "请先填写服务端地址。",
                    assetStatusMessage = "",
                )
            }
        } ?: return
        val drafts = _financeState.value.assetDrafts
        val invalidLabels = mutableListOf<String>()
        val amounts = linkedMapOf<String, Double>()

        drafts.forEach { draft ->
            val raw = draft.amountInput.trim()
            if (raw.isBlank()) {
                return@forEach
            }
            val normalized = raw.replace(",", "")
            val amount = normalized.toDoubleOrNull()
            if (amount == null || !amount.isFinite() || amount < 0.0) {
                invalidLabels += draft.label
            } else {
                amounts[draft.key] = amount
            }
        }

        if (invalidLabels.isNotEmpty()) {
            val fields = invalidLabels.joinToString("、")
            _financeState.update {
                it.copy(
                    isSavingAssetStats = false,
                    isFillingAssetFromImages = false,
                    assetErrorMessage = "以下分类金额格式不正确：$fields",
                    assetStatusMessage = "",
                )
            }
            return
        }

        _financeState.update {
            it.copy(
                isSavingAssetStats = true,
                isFillingAssetFromImages = false,
                assetErrorMessage = "",
                assetStatusMessage = "",
            )
        }

        val total = amounts.values.sum()
        val snapshotId = UUID.randomUUID().toString()
        val savedAt = currentTimestamp()
        viewModelScope.launch {
            when (val currentResult = apiRepository.saveAssetCurrent(baseUrl, total, amounts)) {
                is AppResult.Success -> {
                    when (
                        val snapshotResult = apiRepository.saveAssetSnapshot(
                            baseUrl = baseUrl,
                            id = snapshotId,
                            savedAt = savedAt,
                            totalAmountWan = total,
                            amounts = amounts,
                        )
                    ) {
                        is AppResult.Success -> {
                            settingsRepository.saveAssetCategoryAmounts(currentResult.data.amounts)
                            val nextHistory = mergeAssetHistory(
                                current = _financeState.value.assetHistory,
                                incoming = listOf(snapshotResult.data.toUiRecord()),
                            )
                            settingsRepository.saveAssetSnapshotHistory(nextHistory.toSettingsRecords())
                            val normalizedDrafts = buildAssetDrafts(currentResult.data.amounts)
                            _financeState.update {
                                it.copy(
                                    isSavingAssetStats = false,
                                    isFillingAssetFromImages = false,
                                    assetDrafts = normalizedDrafts,
                                    assetTotalAmount = currentResult.data.totalAmountWan,
                                    assetErrorMessage = "",
                                    assetHistory = nextHistory,
                                    assetStatusMessage = if (amounts.isEmpty()) {
                                        "已清空资产统计。"
                                    } else {
                                        "已保存资产统计：${amounts.size} 类，合计 ${formatAmountWan(total)}。"
                                    },
                                )
                            }
                        }

                        is AppResult.Error -> {
                            settingsRepository.saveAssetCategoryAmounts(currentResult.data.amounts)
                            val normalizedDrafts = buildAssetDrafts(currentResult.data.amounts)
                            _financeState.update {
                                it.copy(
                                    isSavingAssetStats = false,
                                    isFillingAssetFromImages = false,
                                    assetDrafts = normalizedDrafts,
                                    assetTotalAmount = currentResult.data.totalAmountWan,
                                    assetErrorMessage = ErrorMessageMapper.format(
                                        code = snapshotResult.code,
                                        message = snapshotResult.message,
                                        context = ErrorContext.ASSET,
                                    ),
                                    assetStatusMessage = "当前资产已保存，但历史快照保存失败。",
                                )
                            }
                        }
                    }
                }

                is AppResult.Error -> {
                    _financeState.update {
                        it.copy(
                            isSavingAssetStats = false,
                            isFillingAssetFromImages = false,
                            assetErrorMessage = ErrorMessageMapper.format(
                                code = currentResult.code,
                                message = currentResult.message,
                                context = ErrorContext.ASSET,
                            ),
                            assetStatusMessage = "",
                        )
                    }
                }
            }
        }
    }

    fun deleteAssetHistoryRecord(recordId: String) {
        val trimmed = recordId.trim()
        if (trimmed.isBlank()) {
            return
        }
        val baseUrl = requireBaseUrl {
            _financeState.update {
                it.copy(
                    assetErrorMessage = "请先填写服务端地址。",
                    assetStatusMessage = "",
                )
            }
        } ?: return
        viewModelScope.launch {
            when (val result = apiRepository.deleteAssetSnapshot(baseUrl, trimmed)) {
                is AppResult.Success -> {
                    if (result.data.deletedCount <= 0) {
                        _financeState.update {
                            it.copy(
                                assetErrorMessage = "未找到可删除的历史记录。",
                                assetStatusMessage = "",
                            )
                        }
                        return@launch
                    }
                    val next = _financeState.value.assetHistory.filterNot { it.id == trimmed }
                    settingsRepository.saveAssetSnapshotHistory(next.toSettingsRecords())
                    _financeState.update {
                        it.copy(
                            assetHistory = next,
                            assetErrorMessage = "",
                            assetStatusMessage = "已删除 1 条历史记录。",
                        )
                    }
                }

                is AppResult.Error -> {
                    _financeState.update {
                        it.copy(
                            assetErrorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.ASSET,
                            ),
                            assetStatusMessage = "",
                        )
                    }
                }
            }
        }
    }

    fun markAssetSummaryCopied() {
        _financeState.update {
            it.copy(
                assetErrorMessage = "",
                assetStatusMessage = "已复制资产情况。",
            )
        }
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

    fun onAccessTokenInputChange(newValue: String) {
        _settingsState.update {
            it.copy(
                accessTokenInput = newValue,
                saveStatus = "",
                testStatus = "",
                configStatus = "",
            )
        }
    }

    fun saveBaseUrl() {
        val normalized = settingsRepository.saveServerBaseUrl(_settingsState.value.baseUrlInput)
        val token = settingsRepository.saveServerAccessToken(_settingsState.value.accessTokenInput)
        _settingsState.update {
            it.copy(
                baseUrlInput = normalized,
                accessTokenInput = token,
                saveStatus = if (token.isBlank()) {
                    "已保存服务端地址。"
                } else {
                    "已保存服务端地址和访问令牌。"
                },
            )
        }
        loadEditableConfig()
        refreshAsyncJobHistories()
        loadFinanceSignals()
        loadAssetCurrent()
        loadAssetSnapshotHistory()
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
        _bilibiliState.update {
            it.copy(
                videoUrlInput = newValue,
                errorMessage = "",
                submitStatus = "",
                currentJobId = "",
                saveStatus = "",
            )
        }
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

        bilibiliSummaryJob?.cancel()
        bilibiliSummaryJob = viewModelScope.launch {
            _bilibiliState.update {
                it.copy(
                    isLoading = true,
                    errorMessage = "",
                    submitStatus = "",
                    saveStatus = "",
                    currentJobId = "",
                    result = null,
                )
            }
            when (val jobResult = apiRepository.createBilibiliSummaryJob(baseUrl, videoUrl)) {
                is AppResult.Success -> {
                    _bilibiliState.update {
                        it.copy(
                            currentJobId = jobResult.data.jobId,
                            submitStatus = "任务已提交，正在后台总结...（${jobResult.data.jobId.take(8)}）",
                        )
                    }
                    refreshBilibiliAsyncJobs(baseUrl)
                    awaitBilibiliSummaryJob(baseUrl, jobResult.data.jobId)
                }

                is AppResult.Error -> {
                    _bilibiliState.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = ErrorMessageMapper.format(
                                code = jobResult.code,
                                message = jobResult.message,
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
                batchSyncStatus = "",
                currentJobId = "",
                currentJobType = "",
                saveStatus = "",
                captureRefreshStatus = "",
            )
        }
    }

    fun onXiaohongshuBatchLimitInputChange(newValue: String) {
        _xiaohongshuState.update {
            it.copy(
                batchLimitInput = newValue,
                errorMessage = "",
                batchSyncStatus = "",
                saveStatus = "",
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

        xiaohongshuSummaryJob?.cancel()
        xiaohongshuSummaryJob = viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isSummarizingUrl = true,
                    errorMessage = "",
                    summarizeUrlStatus = "",
                    batchSyncStatus = "",
                    currentJobId = "",
                    currentJobType = XIAOHONGSHU_SUMMARY_JOB_TYPE,
                    saveStatus = "",
                    captureRefreshStatus = "",
                )
            }
            when (val jobResult = apiRepository.createXiaohongshuSummaryJob(baseUrl, url)) {
                is AppResult.Success -> {
                    _xiaohongshuState.update {
                        it.copy(
                            currentJobId = jobResult.data.jobId,
                            currentJobType = jobResult.data.jobType,
                            summarizeUrlStatus = "任务已提交，正在后台总结...（${jobResult.data.jobId.take(8)}）",
                        )
                    }
                    refreshXiaohongshuAsyncJobs(baseUrl)
                    refreshXiaohongshuSyncMeta(baseUrl)
                    awaitXiaohongshuSummaryJob(baseUrl, jobResult.data.jobId)
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSummarizingUrl = false,
                            errorMessage = ErrorMessageMapper.format(
                                code = jobResult.code,
                                message = jobResult.message,
                                context = ErrorContext.XIAOHONGSHU_SYNC,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun startXiaohongshuBatchSync() {
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        val limitInput = _xiaohongshuState.value.batchLimitInput.trim()
        val limit = if (limitInput.isBlank()) {
            null
        } else {
            limitInput.toIntOrNull()
        }
        if (limitInput.isNotBlank() && (limit == null || limit <= 0 || limit > 100)) {
            _xiaohongshuState.update {
                it.copy(errorMessage = "批量同步数量需为 1-100 之间的整数。")
            }
            return
        }

        xiaohongshuSummaryJob?.cancel()
        xiaohongshuSummaryJob = viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isSummarizingUrl = true,
                    errorMessage = "",
                    summarizeUrlStatus = "",
                    batchSyncStatus = "",
                    saveStatus = "",
                    captureRefreshStatus = "",
                    currentJobId = "",
                    currentJobType = XIAOHONGSHU_SYNC_JOB_TYPE,
                )
            }
            when (val jobResult = apiRepository.createXiaohongshuSyncJob(baseUrl, limit, confirmLive = true)) {
                is AppResult.Success -> {
                    _xiaohongshuState.update {
                        it.copy(
                            currentJobId = jobResult.data.jobId,
                            currentJobType = jobResult.data.jobType,
                            batchSyncStatus = if (jobResult.data.progressTotal > 0) {
                                "批量同步已提交，目标 ${jobResult.data.progressTotal} 条。"
                            } else {
                                "批量同步已提交，正在后台执行..."
                            },
                        )
                    }
                    refreshXiaohongshuAsyncJobs(baseUrl)
                    refreshXiaohongshuSyncMeta(baseUrl)
                    awaitXiaohongshuSummaryJob(baseUrl, jobResult.data.jobId)
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSummarizingUrl = false,
                            currentJobType = "",
                            errorMessage = ErrorMessageMapper.format(
                                code = jobResult.code,
                                message = jobResult.message,
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

    fun saveAllXiaohongshuSummaries() {
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(saveStatus = "请先填写服务端地址。") }
        } ?: return
        val current = _xiaohongshuState.value
        val pendingItems = current.summaries.filter { it.noteId !in current.savedNoteIds }
        if (pendingItems.isEmpty()) {
            _xiaohongshuState.update { it.copy(saveStatus = "当前没有待保存的批量结果。") }
            return
        }

        viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isSavingAllNotes = true,
                    saveStatus = "",
                    errorMessage = "",
                )
            }
            when (val result = apiRepository.saveXiaohongshuNotes(baseUrl, pendingItems)) {
                is AppResult.Success -> {
                    val savedIds = pendingItems.map { item -> item.noteId }.toSet()
                    _xiaohongshuState.update {
                        it.copy(
                            isSavingAllNotes = false,
                            savedNoteIds = it.savedNoteIds + savedIds,
                            saveStatus = "已批量保存 ${result.data.savedCount} 篇小红书笔记。",
                        )
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSavingAllNotes = false,
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

    fun refreshAsyncJobHistories() {
        val baseUrl = settingsRepository.getServerBaseUrl().trim()
        if (baseUrl.isBlank()) {
            return
        }
        viewModelScope.launch {
            refreshBilibiliAsyncJobs(baseUrl)
            refreshXiaohongshuAsyncJobs(baseUrl)
            refreshXiaohongshuSyncMeta(baseUrl)
        }
    }

    fun refreshBilibiliJobHistory() {
        val baseUrl = requireBaseUrl {
            _bilibiliState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        viewModelScope.launch {
            refreshBilibiliAsyncJobs(baseUrl)
        }
    }

    fun refreshXiaohongshuJobHistory() {
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        viewModelScope.launch {
            refreshXiaohongshuAsyncJobs(baseUrl)
            refreshXiaohongshuSyncMeta(baseUrl)
        }
    }

    fun refreshXiaohongshuSyncMeta() {
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        viewModelScope.launch {
            refreshXiaohongshuSyncMeta(baseUrl)
        }
    }

    fun openBilibiliJob(jobId: String) {
        val normalizedJobId = jobId.trim()
        if (normalizedJobId.isEmpty()) {
            return
        }
        val baseUrl = requireBaseUrl {
            _bilibiliState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        bilibiliSummaryJob?.cancel()
        bilibiliSummaryJob = viewModelScope.launch {
            _bilibiliState.update {
                it.copy(
                    isLoading = true,
                    errorMessage = "",
                    submitStatus = "正在加载任务结果...（${normalizedJobId.take(8)}）",
                    currentJobId = normalizedJobId,
                )
            }
            awaitBilibiliSummaryJob(baseUrl, normalizedJobId)
        }
    }

    fun retryBilibiliJob(jobId: String) {
        val normalizedJobId = jobId.trim()
        if (normalizedJobId.isEmpty()) {
            return
        }
        val baseUrl = requireBaseUrl {
            _bilibiliState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        bilibiliSummaryJob?.cancel()
        bilibiliSummaryJob = viewModelScope.launch {
            _bilibiliState.update {
                it.copy(
                    isLoading = true,
                    errorMessage = "",
                    submitStatus = "",
                    saveStatus = "",
                    result = null,
                )
            }
            when (val result = apiRepository.retryAsyncJob(baseUrl, normalizedJobId)) {
                is AppResult.Success -> {
                    _bilibiliState.update {
                        it.copy(
                            currentJobId = result.data.jobId,
                            submitStatus = "已重新提交后台总结...（${result.data.jobId.take(8)}）",
                        )
                    }
                    refreshBilibiliAsyncJobs(baseUrl)
                    awaitBilibiliSummaryJob(baseUrl, result.data.jobId)
                }

                is AppResult.Error -> {
                    _bilibiliState.update {
                        it.copy(
                            isLoading = false,
                            submitStatus = "",
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

    fun openXiaohongshuJob(jobId: String) {
        val normalizedJobId = jobId.trim()
        if (normalizedJobId.isEmpty()) {
            return
        }
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        xiaohongshuSummaryJob?.cancel()
        xiaohongshuSummaryJob = viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isSummarizingUrl = true,
                    errorMessage = "",
                    summarizeUrlStatus = "正在加载任务结果...（${normalizedJobId.take(8)}）",
                    batchSyncStatus = "",
                    currentJobId = normalizedJobId,
                    currentJobType = "",
                )
            }
            awaitXiaohongshuSummaryJob(baseUrl, normalizedJobId)
        }
    }

    fun retryXiaohongshuJob(jobId: String) {
        val normalizedJobId = jobId.trim()
        if (normalizedJobId.isEmpty()) {
            return
        }
        val baseUrl = requireBaseUrl {
            _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
        } ?: return
        xiaohongshuSummaryJob?.cancel()
        xiaohongshuSummaryJob = viewModelScope.launch {
            _xiaohongshuState.update {
                it.copy(
                    isSummarizingUrl = true,
                    errorMessage = "",
                    summarizeUrlStatus = "",
                    batchSyncStatus = "",
                    saveStatus = "",
                    captureRefreshStatus = "",
                )
            }
            when (val result = apiRepository.retryAsyncJob(baseUrl, normalizedJobId)) {
                is AppResult.Success -> {
                    _xiaohongshuState.update {
                        it.copy(
                            currentJobId = result.data.jobId,
                            currentJobType = result.data.jobType,
                            summarizeUrlStatus = if (result.data.jobType == XIAOHONGSHU_SUMMARY_JOB_TYPE) {
                                "已重新提交后台总结...（${result.data.jobId.take(8)}）"
                            } else {
                                ""
                            },
                            batchSyncStatus = if (result.data.jobType == XIAOHONGSHU_SYNC_JOB_TYPE) {
                                "已重新提交批量同步...（${result.data.jobId.take(8)}）"
                            } else {
                                ""
                            },
                        )
                    }
                    refreshXiaohongshuAsyncJobs(baseUrl)
                    refreshXiaohongshuSyncMeta(baseUrl)
                    awaitXiaohongshuSummaryJob(baseUrl, result.data.jobId)
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSummarizingUrl = false,
                            summarizeUrlStatus = "",
                            batchSyncStatus = "",
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
        notesSearchJob?.cancel()
        notesSearchJob = viewModelScope.launch {
            delay(300)
            loadSavedNotes()
        }
    }

    fun suggestMergeCandidates() {
        val baseUrl = requireBaseUrl {
            _notesState.update {
                it.copy(
                    isMergeSuggesting = false,
                    errorMessage = "请先填写服务端地址。",
                )
            }
        } ?: return
        viewModelScope.launch {
            _notesState.update {
                it.copy(
                    isMergeSuggesting = true,
                    isMergePreviewLoading = false,
                    isMergeCommitting = false,
                    isMergeRollingBack = false,
                    isMergeFinalizing = false,
                    mergePreview = null,
                    mergePreviewKey = "",
                    mergePreviewCache = emptyMap(),
                    lastMergeCommit = null,
                    errorMessage = "",
                    mergeStatus = "正在分析可合并候选...",
                )
            }
            when (val result = apiRepository.suggestMergeCandidates(baseUrl = baseUrl)) {
                is AppResult.Success -> {
                    val strongOnly = filterStrongMergeCandidates(result.data.items)
                    val message = if (strongOnly.isEmpty()) {
                        "未发现可合并候选。"
                    } else {
                        "已发现 ${strongOnly.size} 组候选，请先预览后再确认合并。"
                    }
                    _notesState.update {
                        it.copy(
                            isMergeSuggesting = false,
                            mergeCandidates = strongOnly,
                            mergeStatus = message,
                            errorMessage = "",
                        )
                    }
                }

                is AppResult.Error -> {
                    _notesState.update {
                        it.copy(
                            isMergeSuggesting = false,
                            mergeStatus = "",
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.NOTES_MERGE,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun previewMergeCandidate(candidate: NotesMergeCandidateItem) {
        val candidateKey = buildMergeCandidateKey(
            source = candidate.source,
            noteIds = candidate.noteIds,
        )
        val cachedPreview = _notesState.value.mergePreviewCache[candidateKey]
        if (cachedPreview != null) {
            _notesState.update {
                it.copy(
                    isMergePreviewLoading = false,
                    mergePreview = cachedPreview,
                    mergePreviewKey = candidateKey,
                    lastMergeCommit = null,
                    errorMessage = "",
                    mergeStatus = "已加载缓存预览。",
                )
            }
            return
        }
        val baseUrl = requireBaseUrl {
            _notesState.update {
                it.copy(
                    isMergePreviewLoading = false,
                    errorMessage = "请先填写服务端地址。",
                )
            }
        } ?: return
        viewModelScope.launch {
            _notesState.update {
                it.copy(
                    isMergePreviewLoading = true,
                    mergePreview = null,
                    mergePreviewKey = "",
                    lastMergeCommit = null,
                    errorMessage = "",
                    mergeStatus = "正在生成合并预览...",
                )
            }
            when (
                val result = apiRepository.previewMerge(
                    baseUrl = baseUrl,
                    source = candidate.source,
                    noteIds = candidate.noteIds,
                )
            ) {
                is AppResult.Success -> {
                    _notesState.update {
                        it.copy(
                            isMergePreviewLoading = false,
                            mergePreview = result.data,
                            mergePreviewKey = candidateKey,
                            mergePreviewCache = it.mergePreviewCache + (candidateKey to result.data),
                            mergeStatus = "预览已生成，请在预览页确认是否合并。",
                            errorMessage = "",
                        )
                    }
                }

                is AppResult.Error -> {
                    _notesState.update {
                        it.copy(
                            isMergePreviewLoading = false,
                            mergePreview = null,
                            mergePreviewKey = "",
                            mergeStatus = "",
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.NOTES_MERGE,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun commitCurrentMerge() {
        val baseUrl = requireBaseUrl {
            _notesState.update {
                it.copy(
                    isMergeCommitting = false,
                    errorMessage = "请先填写服务端地址。",
                )
            }
        } ?: return
        val preview = _notesState.value.mergePreview
        if (preview == null) {
            _notesState.update {
                it.copy(
                    mergeStatus = "请先选择候选并生成预览。",
                )
            }
            return
        }
        viewModelScope.launch {
            _notesState.update {
                it.copy(
                    isMergeCommitting = true,
                    isMergeFinalizing = false,
                    errorMessage = "",
                    mergeStatus = "正在提交合并...",
                )
            }
            val commitResult = apiRepository.commitMerge(
                baseUrl = baseUrl,
                source = preview.source,
                noteIds = preview.noteIds,
                mergedTitle = preview.mergedTitle,
                mergedSummaryMarkdown = preview.mergedSummaryMarkdown,
            )
            if (commitResult is AppResult.Error) {
                _notesState.update {
                    it.copy(
                        isMergeCommitting = false,
                        isMergeFinalizing = false,
                        mergeStatus = "",
                        errorMessage = ErrorMessageMapper.format(
                            code = commitResult.code,
                            message = commitResult.message,
                            context = ErrorContext.NOTES_MERGE,
                        ),
                    )
                }
                return@launch
            }

            val commitData = (commitResult as AppResult.Success).data
            _notesState.update {
                it.copy(
                    isMergeCommitting = false,
                    isMergeFinalizing = true,
                    lastMergeCommit = commitData,
                    mergeStatus = "已创建合并笔记，正在确认并清理原笔记...",
                    actionStatus = "已创建合并笔记：${commitData.mergedNoteId}",
                    errorMessage = "",
                )
            }

            when (val finalizeResult = apiRepository.finalizeMerge(baseUrl = baseUrl, mergeId = commitData.mergeId)) {
                is AppResult.Success -> {
                    val affectedNoteIds = commitData.sourceNoteIds
                        .map { it.trim() }
                        .filter { it.isNotEmpty() }
                        .ifEmpty { preview.noteIds }
                        .toSet()
                    _notesState.update {
                        it.copy(
                            isMergeFinalizing = false,
                            isMergeSuggesting = true,
                            lastMergeCommit = null,
                            mergePreview = null,
                            mergePreviewKey = "",
                            mergePreviewCache = emptyMap(),
                            mergeCandidates = it.mergeCandidates.filterNot { candidate ->
                                candidate.source == preview.source &&
                                    candidate.noteIds.any { noteId -> noteId in affectedNoteIds }
                            },
                            mergeStatus = "已确认合并结果，正在刷新建议列表...",
                            actionStatus = "已确认 merge_id=${finalizeResult.data.mergeId}，删除原笔记 ${finalizeResult.data.deletedSourceCount} 条。",
                            errorMessage = "",
                        )
                    }
                    when (
                        val suggestResult = apiRepository.suggestMergeCandidates(
                            baseUrl = baseUrl,
                            source = preview.source,
                        )
                    ) {
                        is AppResult.Success -> {
                            val strongOnly = filterStrongMergeCandidates(suggestResult.data.items)
                            val message = if (strongOnly.isEmpty()) {
                                "已确认合并结果，当前无可合并候选。"
                            } else {
                                "已确认合并结果，剩余 ${strongOnly.size} 组候选。"
                            }
                            _notesState.update {
                                it.copy(
                                    isMergeSuggesting = false,
                                    mergeCandidates = strongOnly,
                                    mergeStatus = message,
                                    errorMessage = "",
                                )
                            }
                        }

                        is AppResult.Error -> {
                            _notesState.update {
                                it.copy(
                                    isMergeSuggesting = false,
                                    mergeStatus = "已确认合并结果，但刷新建议失败。",
                                    errorMessage = ErrorMessageMapper.format(
                                        code = suggestResult.code,
                                        message = suggestResult.message,
                                        context = ErrorContext.NOTES_MERGE,
                                    ),
                                )
                            }
                        }
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    val rollbackHint = when (
                        apiRepository.rollbackMerge(
                            baseUrl = baseUrl,
                            mergeId = commitData.mergeId,
                        )
                    ) {
                        is AppResult.Success -> "已自动回退此次未完成合并，请重试。"
                        is AppResult.Error -> "自动回退失败，请手动处理 merge_id=${commitData.mergeId}。"
                    }
                    _notesState.update {
                        it.copy(
                            isMergeFinalizing = false,
                            lastMergeCommit = null,
                            mergeStatus = "",
                            errorMessage = "${ErrorMessageMapper.format(
                                code = finalizeResult.code,
                                message = finalizeResult.message,
                                context = ErrorContext.NOTES_MERGE,
                            )} $rollbackHint",
                        )
                    }
                    loadSavedNotes()
                }
            }
        }
    }

    fun rollbackLastMerge() {
        val baseUrl = requireBaseUrl {
            _notesState.update {
                it.copy(
                    isMergeRollingBack = false,
                    errorMessage = "请先填写服务端地址。",
                )
            }
        } ?: return
        val mergeId = _notesState.value.lastMergeCommit?.mergeId
        if (mergeId.isNullOrBlank()) {
            _notesState.update { it.copy(mergeStatus = "当前没有可回退的合并记录。") }
            return
        }
        viewModelScope.launch {
            _notesState.update {
                it.copy(
                    isMergeRollingBack = true,
                    errorMessage = "",
                    mergeStatus = "正在回退此次合并...",
                )
            }
            when (val result = apiRepository.rollbackMerge(baseUrl = baseUrl, mergeId = mergeId)) {
                is AppResult.Success -> {
                    _notesState.update {
                        it.copy(
                            isMergeRollingBack = false,
                            lastMergeCommit = null,
                            mergePreview = null,
                            mergePreviewKey = "",
                            mergeStatus = "回退成功，已恢复为合并前状态。",
                            actionStatus = "已回退 merge_id=${result.data.mergeId}",
                            errorMessage = "",
                        )
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _notesState.update {
                        it.copy(
                            isMergeRollingBack = false,
                            mergeStatus = "",
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.NOTES_MERGE,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun finalizeLastMerge() {
        val baseUrl = requireBaseUrl {
            _notesState.update {
                it.copy(
                    isMergeFinalizing = false,
                    errorMessage = "请先填写服务端地址。",
                )
            }
        } ?: return
        val mergeId = _notesState.value.lastMergeCommit?.mergeId
        if (mergeId.isNullOrBlank()) {
            _notesState.update { it.copy(mergeStatus = "当前没有可确认的合并记录。") }
            return
        }
        viewModelScope.launch {
            _notesState.update {
                it.copy(
                    isMergeFinalizing = true,
                    errorMessage = "",
                    mergeStatus = "正在确认合并结果（破坏性）...",
                )
            }
            when (val result = apiRepository.finalizeMerge(baseUrl = baseUrl, mergeId = mergeId)) {
                is AppResult.Success -> {
                    _notesState.update {
                        it.copy(
                            isMergeFinalizing = false,
                            lastMergeCommit = null,
                            mergePreview = null,
                            mergePreviewKey = "",
                            mergeCandidates = emptyList(),
                            mergeStatus = "已确认合并结果，原笔记已执行破坏性清理。",
                            actionStatus = "已确认 merge_id=${result.data.mergeId}，删除原笔记 ${result.data.deletedSourceCount} 条。",
                            errorMessage = "",
                        )
                    }
                    loadSavedNotes()
                }

                is AppResult.Error -> {
                    _notesState.update {
                        it.copy(
                            isMergeFinalizing = false,
                            mergeStatus = "",
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.NOTES_MERGE,
                            ),
                        )
                    }
                }
            }
        }
    }

    fun loadFinanceSignals() {
        val baseUrl = requireBaseUrl {
            _financeState.update {
                it.copy(
                    isLoading = false,
                    errorMessage = "请先填写服务端地址。",
                    statusMessage = "",
                )
            }
        } ?: return
        if (financeSignalsJob?.isActive == true) {
            return
        }
        financeSignalsJob = viewModelScope.launch {
            try {
                _financeState.update {
                    it.copy(
                        isLoading = true,
                        errorMessage = "",
                        statusMessage = "",
                    )
                }
                when (val result = apiRepository.getFinanceSignals(baseUrl)) {
                    is AppResult.Success -> {
                        val status = if (result.data.updateTime.isNotBlank()) {
                            "最近更新：${result.data.updateTime}"
                        } else {
                            "已拉取财经信号面板数据。"
                        }
                        _financeState.update {
                            applyFinanceSignalsData(
                                current = it,
                                data = result.data,
                                isLoading = false,
                                statusMessage = status,
                            )
                        }
                    }

                    is AppResult.Error -> {
                        _financeState.update {
                            it.copy(
                                isLoading = false,
                                newsIsStale = true,
                                errorMessage = ErrorMessageMapper.format(
                                    code = result.code,
                                    message = result.message,
                                    context = ErrorContext.CONNECTION,
                                ),
                                statusMessage = "",
                            )
                        }
                    }
                }
            } finally {
                financeSignalsJob = null
            }
        }
    }

    fun generateFinanceNewsDigest() {
        val baseUrl = requireBaseUrl {
            _financeState.update {
                it.copy(
                    isGeneratingNewsDigest = false,
                    errorMessage = "请先填写服务端地址。",
                    statusMessage = "",
                )
            }
        } ?: return
        if (_financeState.value.isGeneratingNewsDigest) {
            return
        }
        viewModelScope.launch {
            _financeState.update {
                it.copy(
                    isGeneratingNewsDigest = true,
                    errorMessage = "",
                    statusMessage = "正在生成24小时新闻摘要...",
                )
            }
            when (val result = apiRepository.triggerFinanceNewsDigest(baseUrl)) {
                is AppResult.Success -> {
                    val digestStatus = result.data.newsDebug.digestStatus
                    val status = when (digestStatus) {
                        "reused_recent" -> "距上次摘要不足 3 小时，已复用上次结果。"
                        "local_fallback" -> "LLM 不可用，已返回本地摘要。"
                        "fallback" -> "摘要生成失败，已回退本地摘要。"
                        else -> "24小时新闻摘要已更新。"
                    }
                    _financeState.update {
                        applyFinanceSignalsData(
                            current = it,
                            data = result.data,
                            isGeneratingNewsDigest = false,
                            statusMessage = status,
                        )
                    }
                }

                is AppResult.Error -> {
                    _financeState.update {
                        it.copy(
                            isGeneratingNewsDigest = false,
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.CONNECTION,
                            ),
                            statusMessage = "",
                        )
                    }
                }
            }
        }
    }

    fun setWatchlistNtfyEnabled(enabled: Boolean) {
        val baseUrl = requireBaseUrl {
            _financeState.update {
                it.copy(
                    isUpdatingWatchlistNtfy = false,
                    errorMessage = "请先填写服务端地址。",
                    statusMessage = "",
                )
            }
        } ?: return
        viewModelScope.launch {
            _financeState.update {
                it.copy(
                    isUpdatingWatchlistNtfy = true,
                    watchlistNtfyEnabled = enabled,
                    errorMessage = "",
                    statusMessage = "",
                )
            }
            when (val result = apiRepository.updateFinanceWatchlistNtfy(baseUrl, enabled)) {
                is AppResult.Success -> {
                    _financeState.update {
                        it.copy(
                            isUpdatingWatchlistNtfy = false,
                            watchlistNtfyEnabled = result.data.enabled,
                            statusMessage = if (result.data.enabled) {
                                "Watchlist ntfy 通知已开启。"
                            } else {
                                "Watchlist ntfy 通知已关闭。"
                            },
                        )
                    }
                }

                is AppResult.Error -> {
                    _financeState.update {
                        it.copy(
                            isUpdatingWatchlistNtfy = false,
                            watchlistNtfyEnabled = !enabled,
                            errorMessage = ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.CONNECTION,
                            ),
                            statusMessage = "",
                        )
                    }
                }
            }
        }
    }

    fun dismissFinanceFocusCard(item: FinanceFocusCard) {
        val key = buildFinanceFocusCardKey(item)
        if (key.isBlank()) {
            return
        }
        dismissedFinanceFocusCardKeys.add(key)
        settingsRepository.saveDismissedFinanceFocusCardKeys(dismissedFinanceFocusCardKeys)
        _financeState.update { state ->
            val visibleCards = filterVisibleFinanceFocusCards(state.allFocusCards)
            state.copy(
                focusCards = visibleCards,
                dismissedFocusCardCount = state.allFocusCards.size - visibleCards.size,
                statusMessage = "已处理 1 条关注建议。",
                errorMessage = "",
            )
        }
    }

    fun restoreDismissedFinanceFocusCards() {
        dismissedFinanceFocusCardKeys.clear()
        settingsRepository.saveDismissedFinanceFocusCardKeys(dismissedFinanceFocusCardKeys)
        _financeState.update { state ->
            state.copy(
                focusCards = state.allFocusCards,
                dismissedFocusCardCount = 0,
                statusMessage = if (state.allFocusCards.isEmpty()) {
                    state.statusMessage
                } else {
                    "已恢复全部关注建议。"
                },
                errorMessage = "",
            )
        }
    }

    private fun applyFinanceSignalsData(
        current: FinanceSignalsUiState,
        data: com.midas.client.data.model.FinanceSignalsData,
        isLoading: Boolean = current.isLoading,
        isGeneratingNewsDigest: Boolean = current.isGeneratingNewsDigest,
        statusMessage: String = current.statusMessage,
    ): FinanceSignalsUiState {
        val visibleFocusCards = filterVisibleFinanceFocusCards(data.focusCards)
        return current.copy(
            isLoading = isLoading,
            updateTime = data.updateTime,
            newsLastFetchTime = data.newsLastFetchTime,
            newsIsStale = data.newsStale,
            allFocusCards = data.focusCards,
            focusCards = visibleFocusCards,
            dismissedFocusCardCount = data.focusCards.size - visibleFocusCards.size,
            watchlistPreview = data.watchlistPreview,
            topNews = data.topNews,
            watchlistNtfyEnabled = data.watchlistNtfyEnabled,
            isGeneratingNewsDigest = isGeneratingNewsDigest,
            digestLastGeneratedAt = data.newsDebug.digestLastGeneratedAt,
            aiInsightText = data.aiInsightText,
            errorMessage = "",
            statusMessage = statusMessage,
        )
    }

    private fun filterVisibleFinanceFocusCards(
        items: List<FinanceFocusCard>,
    ): List<FinanceFocusCard> {
        return items.filterNot { item ->
            buildFinanceFocusCardKey(item) in dismissedFinanceFocusCardKeys
        }
    }

    private fun buildFinanceFocusCardKey(item: FinanceFocusCard): String {
        val title = item.title.trim()
        if (title.isBlank()) {
            return ""
        }
        val scope = (item.relatedSymbols + item.relatedWatchlistNames)
            .map { value -> value.trim() }
            .filter { value -> value.isNotEmpty() }
            .sorted()
            .joinToString("|")
        return listOf(
            item.kind.trim().uppercase(Locale.ROOT),
            item.actionType.trim().uppercase(Locale.ROOT),
            title,
            scope,
        ).joinToString("::")
    }

    private fun loadLocalAssetStats() {
        val amounts = settingsRepository.getAssetCategoryAmounts()
        val history = settingsRepository.getAssetSnapshotHistory()
        val drafts = buildAssetDrafts(amounts)
        _financeState.update {
            it.copy(
                assetDrafts = drafts,
                assetTotalAmount = computeAssetTotalAmount(drafts),
                assetErrorMessage = "",
                assetStatusMessage = "",
                assetHistory = mapAssetHistory(history),
            )
        }
    }

    private fun loadAssetSnapshotHistory() {
        val baseUrl = settingsRepository.getServerBaseUrl().trim()
        if (baseUrl.isBlank()) {
            return
        }
        if (assetHistoryJob?.isActive == true) {
            return
        }
        assetHistoryJob = viewModelScope.launch {
            try {
                when (val result = apiRepository.listAssetSnapshots(baseUrl)) {
                    is AppResult.Success -> {
                        var serverHistory = result.data.items.map { it.toUiRecord() }
                        val localHistory = mapAssetHistory(settingsRepository.getAssetSnapshotHistory())
                        if (localHistory.isNotEmpty()) {
                            val serverIds = serverHistory.map { it.id }.toSet()
                            val pendingMigration = localHistory.filter { it.id !in serverIds }
                            if (pendingMigration.isNotEmpty()) {
                                pendingMigration.forEach { record ->
                                    when (
                                        apiRepository.saveAssetSnapshot(
                                            baseUrl = baseUrl,
                                            id = record.id,
                                            savedAt = record.savedAt,
                                            totalAmountWan = record.totalAmountWan,
                                            amounts = record.amounts,
                                        )
                                    ) {
                                        is AppResult.Success -> Unit
                                        is AppResult.Error -> return@launch
                                    }
                                }
                                when (val refreshed = apiRepository.listAssetSnapshots(baseUrl)) {
                                    is AppResult.Success -> {
                                        serverHistory = refreshed.data.items.map { it.toUiRecord() }
                                    }
                                    is AppResult.Error -> return@launch
                                }
                            }
                        }

                        settingsRepository.saveAssetSnapshotHistory(serverHistory.toSettingsRecords())
                        val localAmounts = settingsRepository.getAssetCategoryAmounts()
                        if (localAmounts.isEmpty() && serverHistory.isNotEmpty()) {
                            val latest = serverHistory.first()
                            settingsRepository.saveAssetCategoryAmounts(latest.amounts)
                            val drafts = buildAssetDrafts(latest.amounts)
                            _financeState.update {
                                it.copy(
                                    assetDrafts = drafts,
                                    assetTotalAmount = computeAssetTotalAmount(drafts),
                                    assetHistory = serverHistory,
                                    assetErrorMessage = "",
                                )
                            }
                        } else {
                            _financeState.update {
                                it.copy(
                                    assetHistory = serverHistory,
                                    assetErrorMessage = "",
                                )
                            }
                        }
                    }

                    is AppResult.Error -> {
                        // Keep local cache visible; history is now server-backed but local cache
                        // remains as a read fallback until the server is reachable.
                    }
                }
            } finally {
                assetHistoryJob = null
            }
        }
    }

    private fun loadAssetCurrent() {
        val baseUrl = settingsRepository.getServerBaseUrl().trim()
        if (baseUrl.isBlank()) {
            return
        }
        if (assetCurrentJob?.isActive == true) {
            return
        }
        assetCurrentJob = viewModelScope.launch {
            try {
                when (val result = apiRepository.getAssetCurrent(baseUrl)) {
                    is AppResult.Success -> {
                        var currentAmounts = result.data.amounts
                        var currentTotal = result.data.totalAmountWan
                        val localAmounts = settingsRepository.getAssetCategoryAmounts()
                        if (currentAmounts.isEmpty() && localAmounts.isNotEmpty()) {
                            when (
                                val migrated = apiRepository.saveAssetCurrent(
                                    baseUrl = baseUrl,
                                    totalAmountWan = localAmounts.values.sum(),
                                    amounts = localAmounts,
                                )
                            ) {
                                is AppResult.Success -> {
                                    currentAmounts = migrated.data.amounts
                                    currentTotal = migrated.data.totalAmountWan
                                }
                                is AppResult.Error -> return@launch
                            }
                        }

                        settingsRepository.saveAssetCategoryAmounts(currentAmounts)
                        val drafts = buildAssetDrafts(currentAmounts)
                        _financeState.update {
                            it.copy(
                                assetDrafts = drafts,
                                assetTotalAmount = if (currentAmounts.isEmpty()) {
                                    computeAssetTotalAmount(drafts)
                                } else {
                                    currentTotal
                                },
                                assetErrorMessage = "",
                            )
                        }
                    }

                    is AppResult.Error -> {
                        // Keep local cached amounts visible when server is temporarily unreachable.
                    }
                }
            } finally {
                assetCurrentJob = null
            }
        }
    }

    private fun buildAssetDrafts(amounts: Map<String, Double>): List<AssetCategoryDraft> {
        return assetCategorySpecs.map { spec ->
            val value = amounts[spec.key]
            AssetCategoryDraft(
                key = spec.key,
                label = spec.label,
                amountInput = if (value != null) formatAmountInput(value) else "",
            )
        }
    }

    private fun buildAssetDraftsForAutoFill(amounts: Map<String, Double>): List<AssetCategoryDraft> {
        return assetCategorySpecs.map { spec ->
            val normalized = normalizeAmount2(amounts[spec.key] ?: 0.0)
            AssetCategoryDraft(
                key = spec.key,
                label = spec.label,
                amountInput = formatAmountFixed2(normalized),
            )
        }
    }

    private fun computeAssetTotalAmount(drafts: List<AssetCategoryDraft>): Double {
        return drafts.sumOf { draft ->
            val value = draft.amountInput.trim().replace(",", "")
            val amount = value.toDoubleOrNull()
            if (amount != null && amount.isFinite() && amount >= 0.0) {
                amount
            } else {
                0.0
            }
        }
    }

    private fun formatAmountInput(amount: Double): String {
        if (amount == amount.toLong().toDouble()) {
            return amount.toLong().toString()
        }
        return "%.2f".format(Locale.US, amount).trimEnd('0').trimEnd('.')
    }

    private fun formatAmountFixed2(amount: Double): String {
        return "%.2f".format(Locale.US, normalizeAmount2(amount))
    }

    private fun normalizeAmount2(amount: Double): Double {
        if (!amount.isFinite() || amount < 0.0) {
            return 0.0
        }
        return round(amount * 100.0) / 100.0
    }

    private fun formatAmountWan(amount: Double): String {
        return "${"%.2f".format(Locale.US, amount)} 万元人民币"
    }

    private fun mapAssetHistory(
        records: List<SettingsRepository.AssetSnapshotRecord>
    ): List<AssetHistoryRecord> {
        return records.sortedByDescending { it.savedAt }
            .map { record ->
                AssetHistoryRecord(
                    id = record.id,
                    savedAt = record.savedAt,
                    totalAmountWan = record.totalAmountWan,
                    amounts = record.amounts,
                )
            }
    }

    private fun mergeAssetHistory(
        current: List<AssetHistoryRecord>,
        incoming: List<AssetHistoryRecord>,
    ): List<AssetHistoryRecord> {
        val byId = linkedMapOf<String, AssetHistoryRecord>()
        (incoming + current).forEach { record ->
            if (record.id.isNotBlank()) {
                byId[record.id] = record
            }
        }
        return byId.values.sortedByDescending { it.savedAt }
    }

    private fun AssetSnapshotRecordData.toUiRecord(): AssetHistoryRecord {
        return AssetHistoryRecord(
            id = id,
            savedAt = savedAt,
            totalAmountWan = totalAmountWan,
            amounts = amounts,
        )
    }

    private fun List<AssetHistoryRecord>.toSettingsRecords(): List<SettingsRepository.AssetSnapshotRecord> {
        return map { record ->
            SettingsRepository.AssetSnapshotRecord(
                id = record.id,
                savedAt = record.savedAt,
                totalAmountWan = record.totalAmountWan,
                amounts = record.amounts,
            )
        }
    }

    private suspend fun refreshBilibiliAsyncJobs(baseUrl: String) {
        _bilibiliState.update {
            it.copy(
                isRecentJobsLoading = true,
                recentJobsStatus = "",
            )
        }
        when (
            val result = apiRepository.listAsyncJobs(
                baseUrl = baseUrl,
                limit = 6,
                jobType = "bilibili_summarize",
            )
        ) {
            is AppResult.Success -> {
                _bilibiliState.update {
                    it.copy(
                        isRecentJobsLoading = false,
                        recentJobs = result.data.items,
                        recentJobsStatus = if (result.data.items.isEmpty()) {
                            "暂无最近任务。"
                        } else {
                            ""
                        },
                    )
                }
            }

            is AppResult.Error -> {
                _bilibiliState.update {
                    it.copy(
                        isRecentJobsLoading = false,
                        recentJobsStatus = ErrorMessageMapper.format(
                            code = result.code,
                            message = result.message,
                            context = ErrorContext.BILIBILI,
                        ),
                    )
                }
            }
        }
    }

    private suspend fun refreshXiaohongshuAsyncJobs(baseUrl: String) {
        _xiaohongshuState.update {
            it.copy(
                isRecentJobsLoading = true,
                recentJobsStatus = "",
            )
        }
        when (
            val result = apiRepository.listAsyncJobs(
                baseUrl = baseUrl,
                limit = 6,
                jobType = "$XIAOHONGSHU_SUMMARY_JOB_TYPE,$XIAOHONGSHU_SYNC_JOB_TYPE",
            )
        ) {
            is AppResult.Success -> {
                _xiaohongshuState.update {
                    it.copy(
                        isRecentJobsLoading = false,
                        recentJobs = result.data.items,
                        recentJobsStatus = if (result.data.items.isEmpty()) {
                            "暂无最近任务。"
                        } else {
                            ""
                        },
                    )
                }
            }

            is AppResult.Error -> {
                _xiaohongshuState.update {
                    it.copy(
                        isRecentJobsLoading = false,
                        recentJobsStatus = ErrorMessageMapper.format(
                            code = result.code,
                            message = result.message,
                            context = ErrorContext.XIAOHONGSHU_SYNC,
                        ),
                    )
                }
            }
        }
    }

    private suspend fun refreshXiaohongshuSyncMeta(baseUrl: String) {
        _xiaohongshuState.update {
            it.copy(
                isRefreshingSyncMeta = true,
                errorMessage = "",
            )
        }

        val cooldownResult = apiRepository.getXiaohongshuSyncCooldown(baseUrl)
        val pendingResult = apiRepository.getXiaohongshuPendingCount(baseUrl)
        _xiaohongshuState.update { state ->
            var nextState = state.copy(isRefreshingSyncMeta = false)
            when (cooldownResult) {
                is AppResult.Success -> {
                    nextState = nextState.copy(
                        batchCooldownAllowed = cooldownResult.data.allowed,
                        batchCooldownRemainingSeconds = cooldownResult.data.remainingSeconds,
                    )
                }

                is AppResult.Error -> {
                    nextState = nextState.copy(
                        errorMessage = ErrorMessageMapper.format(
                            code = cooldownResult.code,
                            message = cooldownResult.message,
                            context = ErrorContext.XIAOHONGSHU_SYNC,
                        ),
                    )
                }
            }
            when (pendingResult) {
                is AppResult.Success -> {
                    nextState = nextState.copy(
                        batchPendingCount = pendingResult.data.pendingCount,
                        batchScannedCount = pendingResult.data.scannedCount,
                    )
                }

                is AppResult.Error -> {
                    if (nextState.errorMessage.isBlank()) {
                        nextState = nextState.copy(
                            errorMessage = ErrorMessageMapper.format(
                                code = pendingResult.code,
                                message = pendingResult.message,
                                context = ErrorContext.XIAOHONGSHU_SYNC,
                            ),
                        )
                    }
                }
            }
            nextState
        }
    }

    private fun currentTimestamp(): String {
        val formatter = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
        return formatter.format(Date())
    }

    private fun UnifiedNoteItem.toBilibiliSavedNote(): BilibiliSavedNote {
        return BilibiliSavedNote(
            noteId = noteId,
            title = title,
            videoUrl = sourceUrl,
            summaryMarkdown = summaryMarkdown,
            elapsedMs = 0,
            transcriptChars = 0,
            savedAt = savedAt,
        )
    }

    private fun UnifiedNoteItem.toXiaohongshuSavedNote(): XiaohongshuSavedNote {
        return XiaohongshuSavedNote(
            noteId = noteId,
            title = title,
            sourceUrl = sourceUrl,
            summaryMarkdown = summaryMarkdown,
            savedAt = savedAt,
        )
    }

    private suspend fun awaitBilibiliSummaryJob(baseUrl: String, jobId: String) {
        repeat(ASYNC_JOB_POLL_MAX_ATTEMPTS) { attempt ->
            when (val status = apiRepository.getAsyncJob(baseUrl, jobId)) {
                is AppResult.Success -> {
                    when (status.data.status) {
                        "PENDING", "RUNNING" -> {
                            _bilibiliState.update {
                                it.copy(
                                    submitStatus = if (status.data.status == "PENDING") {
                                        "任务排队中...（${jobId.take(8)}）"
                                    } else {
                                        "后台总结中...（${jobId.take(8)}）"
                                    },
                                )
                            }
                            if (attempt < ASYNC_JOB_POLL_MAX_ATTEMPTS - 1) {
                                delay(ASYNC_JOB_POLL_INTERVAL_MS)
                            }
                        }

                        "SUCCEEDED" -> {
                            val parsed = status.data.result?.toBilibiliSummaryData()
                            if (parsed == null) {
                                _bilibiliState.update {
                                    it.copy(
                                        isLoading = false,
                                        submitStatus = "",
                                        errorMessage = "任务完成，但结果格式无法识别。",
                                    )
                                }
                            } else {
                                _bilibiliState.update {
                                    it.copy(
                                        isLoading = false,
                                        result = parsed,
                                        submitStatus = "总结完成，可直接保存。",
                                    )
                                }
                            }
                            refreshBilibiliAsyncJobs(baseUrl)
                            return
                        }

                        else -> {
                            _bilibiliState.update {
                                it.copy(
                                    isLoading = false,
                                    submitStatus = "",
                                    errorMessage = status.data.error?.message
                                        ?: status.data.message.ifBlank { "后台总结失败。" },
                                )
                            }
                            refreshBilibiliAsyncJobs(baseUrl)
                            return
                        }
                    }
                }

                is AppResult.Error -> {
                    _bilibiliState.update {
                        it.copy(
                            isLoading = false,
                            submitStatus = "",
                            errorMessage = ErrorMessageMapper.format(
                                code = status.code,
                                message = status.message,
                                context = ErrorContext.BILIBILI,
                            ),
                        )
                    }
                    refreshBilibiliAsyncJobs(baseUrl)
                    return
                }
            }
        }
        _bilibiliState.update {
            it.copy(
                isLoading = false,
                submitStatus = "",
                errorMessage = "后台任务等待超时，请稍后重试。任务ID：$jobId",
            )
        }
        refreshBilibiliAsyncJobs(baseUrl)
    }

    private suspend fun awaitXiaohongshuSummaryJob(baseUrl: String, jobId: String) {
        repeat(ASYNC_JOB_POLL_MAX_ATTEMPTS) { attempt ->
            when (val status = apiRepository.getAsyncJob(baseUrl, jobId)) {
                is AppResult.Success -> {
                    val jobType = status.data.jobType.trim().ifBlank { XIAOHONGSHU_SUMMARY_JOB_TYPE }
                    when (status.data.status) {
                        "PENDING", "RUNNING" -> {
                            val previewSummaries = status.data.result?.toXiaohongshuSummaryItems().orEmpty()
                            _xiaohongshuState.update {
                                val nextSummaries = if (previewSummaries.isEmpty()) {
                                    it.summaries
                                } else {
                                    mergeXiaohongshuSummaries(it.summaries, previewSummaries)
                                }
                                it.copy(
                                    summaries = nextSummaries,
                                    currentJobId = jobId,
                                    currentJobType = jobType,
                                    summarizeUrlStatus = if (jobType == XIAOHONGSHU_SUMMARY_JOB_TYPE) {
                                        if (status.data.status == "PENDING") {
                                            "任务排队中...（${jobId.take(8)}）"
                                        } else {
                                            "后台总结中...（${jobId.take(8)}）"
                                        }
                                    } else {
                                        ""
                                    },
                                    batchSyncStatus = if (jobType == XIAOHONGSHU_SYNC_JOB_TYPE) {
                                        formatXiaohongshuBatchStatus(status.data.status, status.data.progress?.current, status.data.progress?.total, status.data.message, jobId)
                                    } else {
                                        it.batchSyncStatus
                                    },
                                )
                            }
                            if (attempt < ASYNC_JOB_POLL_MAX_ATTEMPTS - 1) {
                                delay(ASYNC_JOB_POLL_INTERVAL_MS)
                            }
                        }

                        "SUCCEEDED" -> {
                            if (jobType == XIAOHONGSHU_SYNC_JOB_TYPE) {
                                val parsed = status.data.result?.toXiaohongshuSyncData()
                                if (parsed == null) {
                                    _xiaohongshuState.update {
                                        it.copy(
                                            isSummarizingUrl = false,
                                            currentJobType = jobType,
                                            batchSyncStatus = "",
                                            errorMessage = "批量任务完成，但结果格式无法识别。",
                                        )
                                    }
                                } else {
                                    _xiaohongshuState.update {
                                        it.copy(
                                            isSummarizingUrl = false,
                                            currentJobType = jobType,
                                            summaries = mergeXiaohongshuSummaries(it.summaries, parsed.summaries),
                                            summarizeUrlStatus = "",
                                            batchSyncStatus = "批量同步完成：新增 ${parsed.newCount} 条，跳过 ${parsed.skippedCount} 条，失败 ${parsed.failedCount} 条。",
                                        )
                                    }
                                }
                            } else {
                                val parsed = status.data.result?.toXiaohongshuSummaryItem()
                                if (parsed == null) {
                                    _xiaohongshuState.update {
                                        it.copy(
                                            isSummarizingUrl = false,
                                            currentJobType = jobType,
                                            summarizeUrlStatus = "",
                                            errorMessage = "任务完成，但结果格式无法识别。",
                                        )
                                    }
                                } else {
                                    _xiaohongshuState.update {
                                        it.copy(
                                            isSummarizingUrl = false,
                                            currentJobType = jobType,
                                            summaries = mergeXiaohongshuSummaries(it.summaries, listOf(parsed)),
                                            summarizeUrlStatus = "单篇笔记总结完成，可直接保存。",
                                            batchSyncStatus = "",
                                        )
                                    }
                                }
                            }
                            refreshXiaohongshuAsyncJobs(baseUrl)
                            refreshXiaohongshuSyncMeta(baseUrl)
                            return
                        }

                        else -> {
                            _xiaohongshuState.update {
                                it.copy(
                                    isSummarizingUrl = false,
                                    currentJobType = jobType,
                                    summarizeUrlStatus = if (jobType == XIAOHONGSHU_SUMMARY_JOB_TYPE) "" else it.summarizeUrlStatus,
                                    batchSyncStatus = if (jobType == XIAOHONGSHU_SYNC_JOB_TYPE) "" else it.batchSyncStatus,
                                    errorMessage = status.data.error?.message
                                        ?: status.data.message.ifBlank { "后台总结失败。" },
                                )
                            }
                            refreshXiaohongshuAsyncJobs(baseUrl)
                            refreshXiaohongshuSyncMeta(baseUrl)
                            return
                        }
                    }
                }

                is AppResult.Error -> {
                    _xiaohongshuState.update {
                        it.copy(
                            isSummarizingUrl = false,
                            summarizeUrlStatus = "",
                            batchSyncStatus = "",
                            errorMessage = ErrorMessageMapper.format(
                                code = status.code,
                                message = status.message,
                                context = ErrorContext.XIAOHONGSHU_SYNC,
                            ),
                        )
                    }
                    refreshXiaohongshuAsyncJobs(baseUrl)
                    refreshXiaohongshuSyncMeta(baseUrl)
                    return
                }
            }
        }
        _xiaohongshuState.update {
            it.copy(
                isSummarizingUrl = false,
                summarizeUrlStatus = "",
                batchSyncStatus = "",
                errorMessage = "后台任务等待超时，请稍后重试。任务ID：$jobId",
            )
        }
        refreshXiaohongshuAsyncJobs(baseUrl)
        refreshXiaohongshuSyncMeta(baseUrl)
    }

    private fun Map<String, Any?>.toBilibiliSummaryData(): BilibiliSummaryData? {
        val videoUrl = stringValue("video_url")
        val summaryMarkdown = stringValue("summary_markdown")
        val elapsedMs = intValue("elapsed_ms")
        val transcriptChars = intValue("transcript_chars")
        if (videoUrl.isBlank() || summaryMarkdown.isBlank()) {
            return null
        }
        return BilibiliSummaryData(
            videoUrl = videoUrl,
            summaryMarkdown = summaryMarkdown,
            elapsedMs = elapsedMs,
            transcriptChars = transcriptChars,
        )
    }

    private fun Map<String, Any?>.toXiaohongshuSummaryItem(): XiaohongshuSummaryItem? {
        val noteId = stringValue("note_id")
        val title = stringValue("title")
        val sourceUrl = stringValue("source_url")
        val summaryMarkdown = stringValue("summary_markdown")
        if (noteId.isBlank() || sourceUrl.isBlank() || summaryMarkdown.isBlank()) {
            return null
        }
        return XiaohongshuSummaryItem(
            noteId = noteId,
            title = title,
            sourceUrl = sourceUrl,
            summaryMarkdown = summaryMarkdown,
        )
    }

    private fun Map<String, Any?>.toXiaohongshuSummaryItems(): List<XiaohongshuSummaryItem> {
        val rawList = this["summaries"] as? List<*> ?: return emptyList()
        return rawList.mapNotNull { rawItem ->
            (rawItem as? Map<*, *>)?.entries
                ?.associate { entry -> entry.key.toString() to entry.value }
                ?.toXiaohongshuSummaryItem()
        }
    }

    private fun Map<String, Any?>.toXiaohongshuSyncData(): XiaohongshuSyncData? {
        val requestedLimit = intValue("requested_limit")
        val summaries = toXiaohongshuSummaryItems()
        if (requestedLimit <= 0 && summaries.isEmpty()) {
            return null
        }
        return XiaohongshuSyncData(
            requestedLimit = requestedLimit,
            fetchedCount = intValue("fetched_count"),
            newCount = intValue("new_count"),
            skippedCount = intValue("skipped_count"),
            failedCount = intValue("failed_count"),
            circuitOpened = boolValue("circuit_opened"),
            summaries = summaries,
        )
    }

    private fun mergeXiaohongshuSummaries(
        existing: List<XiaohongshuSummaryItem>,
        incoming: List<XiaohongshuSummaryItem>,
    ): List<XiaohongshuSummaryItem> {
        val merged = linkedMapOf<String, XiaohongshuSummaryItem>()
        (incoming + existing).forEach { item ->
            val key = item.noteId.trim()
            if (key.isNotEmpty()) {
                merged[key] = item
            }
        }
        return merged.values.toList()
    }

    private fun formatXiaohongshuBatchStatus(
        status: String,
        current: Int?,
        total: Int?,
        message: String,
        jobId: String,
    ): String {
        val safeCurrent = current ?: 0
        val safeTotal = total ?: 0
        if (status == "PENDING") {
            return "批量任务排队中...（${jobId.take(8)}）"
        }
        if (safeTotal > 0) {
            val suffix = message.takeIf { it.isNotBlank() }?.let { " · $it" }.orEmpty()
            return "批量同步中（$safeCurrent/$safeTotal）$suffix"
        }
        return message.ifBlank { "批量同步中...（${jobId.take(8)}）" }
    }

    private fun Map<String, Any?>.stringValue(key: String): String {
        return when (val value = this[key]) {
            null -> ""
            is String -> value.trim()
            else -> value.toString().trim()
        }
    }

    private fun Map<String, Any?>.intValue(key: String): Int {
        val value = this[key] ?: return 0
        return when (value) {
            is Int -> value
            is Long -> value.toInt()
            is Double -> value.toInt()
            is Float -> value.toInt()
            is String -> value.toIntOrNull() ?: 0
            else -> 0
        }
    }

    private fun Map<String, Any?>.boolValue(key: String): Boolean {
        return when (val value = this[key]) {
            is Boolean -> value
            is String -> value.equals("true", ignoreCase = true)
            is Number -> value.toInt() != 0
            else -> false
        }
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
            when (
                val result = apiRepository.searchNotes(
                    baseUrl = baseUrl,
                    keyword = _notesState.value.keywordInput.trim(),
                    limit = 200,
                    offset = 0,
                )
            ) {
                is AppResult.Success -> {
                    val bilibiliItems = result.data.items
                        .filter { item -> item.source == "bilibili" }
                        .map { item -> item.toBilibiliSavedNote() }
                    val xhsItems = result.data.items
                        .filter { item -> item.source == "xiaohongshu" }
                        .map { item -> item.toXiaohongshuSavedNote() }
                    _xiaohongshuState.update { current ->
                        current.copy(savedNoteIds = xhsItems.map { item -> item.noteId }.toSet())
                    }
                    _notesState.update {
                        it.copy(
                            isLoading = false,
                            bilibiliNotes = bilibiliItems,
                            xiaohongshuNotes = xhsItems,
                            actionStatus = if (_notesState.value.keywordInput.trim().isBlank()) {
                                ""
                            } else {
                                "远端检索命中 ${result.data.total} 条笔记。"
                            },
                        )
                    }
                }

                is AppResult.Error -> {
                    _notesState.update {
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
        notesSearchJob?.cancel()
        bilibiliSummaryJob?.cancel()
        xiaohongshuSummaryJob?.cancel()
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

    private fun buildMergeCandidateKey(source: String, noteIds: List<String>): String {
        val normalizedIds = noteIds
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .sorted()
        return "${source.trim().lowercase()}::${normalizedIds.joinToString("|")}"
    }

    private fun filterStrongMergeCandidates(
        candidates: List<NotesMergeCandidateItem>,
    ): List<NotesMergeCandidateItem> {
        return candidates.filter { it.relationLevel == "STRONG" }
    }

}
