package com.midas.client.ui.screen

import android.app.Application
import android.net.Uri
import androidx.lifecycle.viewModelScope
import com.midas.client.data.model.AssetSnapshotRecordData
import com.midas.client.data.model.FinanceFocusCard
import com.midas.client.data.model.FinanceSignalsData
import com.midas.client.data.repo.AssetImageUpload
import com.midas.client.data.repo.SettingsRepository
import com.midas.client.util.AppResult
import com.midas.client.util.AssetImageCompressor
import com.midas.client.util.ErrorContext
import com.midas.client.util.ErrorMessageMapper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import kotlin.math.round

fun MainViewModel.onAppForeground() {
    loadSavedNotes()
    refreshAsyncJobHistories()
    loadFinanceSignals()
    loadAssetCurrent()
    loadAssetSnapshotHistory()
}

fun MainViewModel.refreshAssetStats() {
    loadAssetCurrent()
    loadAssetSnapshotHistory()
}

fun MainViewModel.onAssetAmountInputChange(categoryKey: String, newValue: String) {
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

fun MainViewModel.onAssetImagesSelected(uris: List<Uri>) {
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

fun MainViewModel.saveAssetStats() {
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

fun MainViewModel.deleteAssetHistoryRecord(recordId: String) {
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

fun MainViewModel.markAssetSummaryCopied() {
    _financeState.update {
        it.copy(
            assetErrorMessage = "",
            assetStatusMessage = "已复制资产情况。",
        )
    }
}

fun MainViewModel.loadFinanceSignals() {
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
                    loadFinanceFocusCardHistory()
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

fun MainViewModel.loadFinanceFocusCardHistory() {
    val baseUrl = settingsRepository.getServerBaseUrl().trim()
    if (baseUrl.isBlank()) {
        return
    }
    viewModelScope.launch {
        when (val result = apiRepository.getFinanceFocusCardHistory(baseUrl, limit = 50)) {
            is AppResult.Success -> {
                _financeState.update {
                    it.copy(focusCardHistory = result.data.items)
                }
            }

            is AppResult.Error -> Unit
        }
    }
}

fun MainViewModel.generateFinanceNewsDigest() {
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

fun MainViewModel.setWatchlistNtfyEnabled(enabled: Boolean) {
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

fun MainViewModel.dismissFinanceFocusCard(item: FinanceFocusCard) {
    val cardId = item.cardId.trim()
    if (cardId.isBlank()) {
        return
    }
    updateFinanceFocusCardStatus(cardId = cardId, status = "SEEN")
}

fun MainViewModel.restoreDismissedFinanceFocusCards() {
    val cardIds = _financeState.value.allFocusCards
        .filter { card -> card.status != "ACTIVE" }
        .map { card -> card.cardId.trim() }
        .filter { it.isNotEmpty() }
    if (cardIds.isEmpty()) {
        return
    }
    val baseUrl = requireBaseUrl {
        _financeState.update {
            it.copy(
                isUpdatingFocusCardStatus = false,
                errorMessage = "请先填写服务端地址。",
            )
        }
    } ?: return
    viewModelScope.launch {
        _financeState.update {
            it.copy(
                isUpdatingFocusCardStatus = true,
                errorMessage = "",
                statusMessage = "",
            )
        }
        cardIds.forEach { cardId ->
            apiRepository.updateFinanceFocusCardStatus(
                baseUrl = baseUrl,
                cardId = cardId,
                status = "ACTIVE",
            )
        }
        _financeState.update {
            it.copy(
                isUpdatingFocusCardStatus = false,
                statusMessage = "已恢复全部关注建议。",
                errorMessage = "",
            )
        }
        loadFinanceSignals()
        loadFinanceFocusCardHistory()
    }
}

fun MainViewModel.updateFinanceFocusCardStatus(cardId: String, status: String) {
    val baseUrl = requireBaseUrl {
        _financeState.update {
            it.copy(
                isUpdatingFocusCardStatus = false,
                errorMessage = "请先填写服务端地址。",
            )
        }
    } ?: return
    viewModelScope.launch {
        _financeState.update {
            it.copy(
                isUpdatingFocusCardStatus = true,
                errorMessage = "",
                statusMessage = "",
            )
        }
        when (
            val result = apiRepository.updateFinanceFocusCardStatus(
                baseUrl = baseUrl,
                cardId = cardId,
                status = status,
            )
        ) {
            is AppResult.Success -> {
                _financeState.update {
                    it.copy(
                        isUpdatingFocusCardStatus = false,
                        statusMessage = when (result.data.status) {
                            "WATCHING" -> "已标记为继续关注。"
                            "IGNORED_TODAY" -> "已忽略今日提醒。"
                            "SEEN" -> "已标记为已看过。"
                            else -> "已恢复为活跃建议。"
                        },
                        errorMessage = "",
                    )
                }
                loadFinanceSignals()
                loadFinanceFocusCardHistory()
            }

            is AppResult.Error -> {
                _financeState.update {
                    it.copy(
                        isUpdatingFocusCardStatus = false,
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

internal fun MainViewModel.applyFinanceSignalsData(
    current: FinanceSignalsUiState,
    data: FinanceSignalsData,
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
        historyCount = data.historyCount,
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

internal fun filterVisibleFinanceFocusCards(items: List<FinanceFocusCard>): List<FinanceFocusCard> {
    return items.filter { item ->
        item.status == "ACTIVE" || item.status == "WATCHING"
    }
}

internal fun MainViewModel.loadLocalAssetStats() {
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

internal fun MainViewModel.loadAssetSnapshotHistory() {
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

                is AppResult.Error -> Unit
            }
        } finally {
            assetHistoryJob = null
        }
    }
}

internal fun MainViewModel.loadAssetCurrent() {
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

                is AppResult.Error -> Unit
            }
        } finally {
            assetCurrentJob = null
        }
    }
}

internal fun buildAssetDrafts(amounts: Map<String, Double>): List<AssetCategoryDraft> {
    return assetCategorySpecs.map { spec ->
        val value = amounts[spec.key]
        AssetCategoryDraft(
            key = spec.key,
            label = spec.label,
            amountInput = if (value != null) formatAmountInput(value) else "",
        )
    }
}

internal fun buildAssetDraftsForAutoFill(amounts: Map<String, Double>): List<AssetCategoryDraft> {
    return assetCategorySpecs.map { spec ->
        val normalized = normalizeAmount2(amounts[spec.key] ?: 0.0)
        AssetCategoryDraft(
            key = spec.key,
            label = spec.label,
            amountInput = formatAmountFixed2(normalized),
        )
    }
}

internal fun computeAssetTotalAmount(drafts: List<AssetCategoryDraft>): Double {
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

internal fun formatAmountInput(amount: Double): String {
    if (amount == amount.toLong().toDouble()) {
        return amount.toLong().toString()
    }
    return "%.2f".format(Locale.US, amount).trimEnd('0').trimEnd('.')
}

internal fun formatAmountFixed2(amount: Double): String {
    return "%.2f".format(Locale.US, normalizeAmount2(amount))
}

internal fun normalizeAmount2(amount: Double): Double {
    if (!amount.isFinite() || amount < 0.0) {
        return 0.0
    }
    return round(amount * 100.0) / 100.0
}

internal fun formatAmountWan(amount: Double): String {
    return "${"%.2f".format(Locale.US, amount)} 万元人民币"
}

internal fun mapAssetHistory(
    records: List<SettingsRepository.AssetSnapshotRecord>,
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

internal fun mergeAssetHistory(
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

internal fun AssetSnapshotRecordData.toUiRecord(): AssetHistoryRecord {
    return AssetHistoryRecord(
        id = id,
        savedAt = savedAt,
        totalAmountWan = totalAmountWan,
        amounts = amounts,
    )
}

internal fun List<AssetHistoryRecord>.toSettingsRecords(): List<SettingsRepository.AssetSnapshotRecord> {
    return map { record ->
        SettingsRepository.AssetSnapshotRecord(
            id = record.id,
            savedAt = record.savedAt,
            totalAmountWan = record.totalAmountWan,
            amounts = record.amounts,
        )
    }
}

internal fun currentTimestamp(): String {
    val formatter = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
    return formatter.format(Date())
}
