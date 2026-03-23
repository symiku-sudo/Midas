package com.midas.client.ui.screen

import androidx.lifecycle.viewModelScope
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.NotesMergeCandidateItem
import com.midas.client.data.model.UnifiedNoteItem
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.util.AppResult
import com.midas.client.util.ErrorContext
import com.midas.client.util.ErrorMessageMapper
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

fun MainViewModel.onNotesKeywordInputChange(newValue: String) {
    _notesState.update { it.copy(keywordInput = newValue) }
    notesSearchJob?.cancel()
    notesSearchJob = viewModelScope.launch {
        delay(300)
        loadSavedNotes()
    }
}

fun MainViewModel.onNotesSourceFilterChange(newValue: String) {
    _notesState.update { it.copy(sourceFilter = newValue) }
    loadSavedNotes()
}

fun MainViewModel.onNotesDateWindowChange(days: Int) {
    _notesState.update { it.copy(dateWindowDays = days) }
    loadSavedNotes()
    loadNotesReview()
}

fun MainViewModel.onNotesMergedFilterChange(newValue: String) {
    _notesState.update { it.copy(mergedFilter = newValue) }
    loadSavedNotes()
}

fun MainViewModel.onNotesSortChange(sortBy: String, sortOrder: String) {
    _notesState.update {
        it.copy(
            sortBy = sortBy,
            sortOrder = sortOrder,
        )
    }
    loadSavedNotes()
}

fun MainViewModel.suggestMergeCandidates() {
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

fun MainViewModel.previewMergeCandidate(candidate: NotesMergeCandidateItem) {
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

fun MainViewModel.commitCurrentMerge() {
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
                        mergeCandidates = it.mergeCandidates.filterNot { candidateItem ->
                            candidateItem.source == preview.source &&
                                candidateItem.noteIds.any { noteId -> noteId in affectedNoteIds }
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

fun MainViewModel.rollbackLastMerge() {
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

fun MainViewModel.finalizeLastMerge() {
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

fun MainViewModel.loadSavedNotes() {
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
        val state = _notesState.value
        val savedFrom = when (state.dateWindowDays) {
            in 1..365 -> SimpleDateFormat("yyyy-MM-dd 00:00:00", Locale.US).format(
                Date(System.currentTimeMillis() - (state.dateWindowDays.toLong() - 1L) * 86_400_000L)
            )

            else -> ""
        }
        val merged = when (state.mergedFilter) {
            "merged" -> true
            "unmerged" -> false
            else -> null
        }
        when (
            val result = apiRepository.searchNotes(
                baseUrl = baseUrl,
                keyword = state.keywordInput.trim(),
                source = state.sourceFilter,
                savedFrom = savedFrom,
                merged = merged,
                sortBy = state.sortBy,
                sortOrder = state.sortOrder,
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
                        unifiedNotes = result.data.items,
                        bilibiliNotes = bilibiliItems,
                        xiaohongshuNotes = xhsItems,
                        actionStatus = if (state.keywordInput.trim().isBlank()) {
                            ""
                        } else {
                            "远端检索命中 ${result.data.total} 条笔记。"
                        },
                    )
                }
                loadNotesReview()
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

fun MainViewModel.loadNotesReview() {
    val baseUrl = settingsRepository.getServerBaseUrl().trim()
    if (baseUrl.isBlank()) {
        return
    }
    viewModelScope.launch {
        _notesState.update { it.copy(isReviewLoading = true) }
        val weekTopics = apiRepository.reviewNotesTopics(baseUrl, days = 7, limit = 6, perTopicLimit = 4)
        val monthTopics = apiRepository.reviewNotesTopics(baseUrl, days = 30, limit = 8, perTopicLimit = 4)
        val timeline = apiRepository.reviewNotesTimeline(baseUrl, days = 30, bucket = "day", limit = 10, perBucketLimit = 3)
        _notesState.update {
            it.copy(
                isReviewLoading = false,
                reviewTopicsWeek = (weekTopics as? AppResult.Success)?.data?.items.orEmpty(),
                reviewTopicsMonth = (monthTopics as? AppResult.Success)?.data?.items.orEmpty(),
                reviewTimeline = (timeline as? AppResult.Success)?.data?.items.orEmpty(),
            )
        }
    }
}

fun MainViewModel.loadRelatedNotes(item: UnifiedNoteItem) {
    val baseUrl = requireBaseUrl {
        _notesState.update { it.copy(isRelatedLoading = false, errorMessage = "请先填写服务端地址。") }
    } ?: return
    viewModelScope.launch {
        _notesState.update {
            it.copy(
                isRelatedLoading = true,
                relatedNotesTarget = item,
                relatedNotes = emptyList(),
                errorMessage = "",
            )
        }
        when (
            val result = apiRepository.getRelatedNotes(
                baseUrl = baseUrl,
                source = item.source,
                noteId = item.noteId,
                limit = 8,
                minScore = 0.2,
            )
        ) {
            is AppResult.Success -> {
                _notesState.update {
                    it.copy(
                        isRelatedLoading = false,
                        relatedNotesTarget = item,
                        relatedNotes = result.data.items,
                        errorMessage = "",
                    )
                }
            }

            is AppResult.Error -> {
                _notesState.update {
                    it.copy(
                        isRelatedLoading = false,
                        relatedNotes = emptyList(),
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

fun MainViewModel.deleteBilibiliSavedNote(noteId: String) {
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

fun MainViewModel.clearBilibiliSavedNotes() {
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

fun MainViewModel.deleteXiaohongshuSavedNote(noteId: String) {
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
                            context = ErrorContext.XIAOHONGSHU_JOB,
                        ),
                    )
                }
            }
        }
    }
}

fun MainViewModel.clearXiaohongshuSavedNotes() {
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
                            context = ErrorContext.XIAOHONGSHU_JOB,
                        ),
                    )
                }
            }
        }
    }
}

internal fun UnifiedNoteItem.toBilibiliSavedNote(): BilibiliSavedNote {
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

internal fun UnifiedNoteItem.toXiaohongshuSavedNote(): XiaohongshuSavedNote {
    return XiaohongshuSavedNote(
        noteId = noteId,
        title = title,
        sourceUrl = sourceUrl,
        summaryMarkdown = summaryMarkdown,
        savedAt = savedAt,
    )
}
