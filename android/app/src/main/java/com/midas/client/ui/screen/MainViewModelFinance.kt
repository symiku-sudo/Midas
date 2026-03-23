package com.midas.client.ui.screen

import androidx.lifecycle.viewModelScope
import com.midas.client.data.model.FinanceFocusCard
import com.midas.client.data.model.FinanceSignalsData
import com.midas.client.util.AppResult
import com.midas.client.util.ErrorContext
import com.midas.client.util.ErrorMessageMapper
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

fun MainViewModel.onAppForeground() {
    loadSavedNotes()
    refreshAsyncJobHistories()
    loadFinanceSignals()
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
