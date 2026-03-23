package com.midas.client.ui.screen

import androidx.lifecycle.viewModelScope
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.util.AppResult
import com.midas.client.util.ErrorContext
import com.midas.client.util.ErrorMessageMapper
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

fun MainViewModel.onBilibiliUrlInputChange(newValue: String) {
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

fun MainViewModel.submitBilibiliSummary() {
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

fun MainViewModel.saveCurrentBilibiliResult() {
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

fun MainViewModel.onXiaohongshuUrlInputChange(newValue: String) {
    _xiaohongshuState.update {
        it.copy(
            urlInput = newValue,
            errorMessage = "",
            summarizeUrlStatus = "",
            currentJobId = "",
            currentJobType = "",
            saveStatus = "",
            captureRefreshStatus = "",
        )
    }
}

fun MainViewModel.summarizeXiaohongshuByUrl() {
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
                currentJobId = "",
                currentJobType = XIAOHONGSHU_CAPTURE_JOB_TYPE,
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
                awaitXiaohongshuSummaryJob(baseUrl, jobResult.data.jobId)
            }

            is AppResult.Error -> {
                _xiaohongshuState.update {
                    it.copy(
                        isSummarizingUrl = false,
                        errorMessage = ErrorMessageMapper.format(
                            code = jobResult.code,
                            message = jobResult.message,
                            context = ErrorContext.XIAOHONGSHU_JOB,
                        ),
                    )
                }
            }
        }
    }
}

fun MainViewModel.saveSingleXiaohongshuSummary(item: XiaohongshuSummaryItem) {
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
                            context = ErrorContext.XIAOHONGSHU_JOB,
                        ),
                    )
                }
            }
        }
    }
}

fun MainViewModel.submitXiaohongshuMobileAuth(cookie: String, userAgent: String) {
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
                            context = ErrorContext.XIAOHONGSHU_JOB,
                        ),
                    )
                }
            }
        }
    }
}

fun MainViewModel.refreshXiaohongshuAuthConfig() {
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
                            context = ErrorContext.XIAOHONGSHU_JOB,
                        ),
                    )
                }
            }
        }
    }
}

fun MainViewModel.refreshAsyncJobHistories() {
    val baseUrl = settingsRepository.getServerBaseUrl().trim()
    if (baseUrl.isBlank()) {
        return
    }
    viewModelScope.launch {
        refreshBilibiliAsyncJobs(baseUrl)
        refreshXiaohongshuAsyncJobs(baseUrl)
    }
}

fun MainViewModel.refreshBilibiliJobHistory() {
    val baseUrl = requireBaseUrl {
        _bilibiliState.update { it.copy(errorMessage = "请先填写服务端地址。") }
    } ?: return
    viewModelScope.launch {
        refreshBilibiliAsyncJobs(baseUrl)
    }
}

fun MainViewModel.refreshXiaohongshuJobHistory() {
    val baseUrl = requireBaseUrl {
        _xiaohongshuState.update { it.copy(errorMessage = "请先填写服务端地址。") }
    } ?: return
    viewModelScope.launch {
        refreshXiaohongshuAsyncJobs(baseUrl)
    }
}

fun MainViewModel.openBilibiliJob(jobId: String) {
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

fun MainViewModel.retryBilibiliJob(jobId: String) {
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

fun MainViewModel.openXiaohongshuJob(jobId: String) {
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
                currentJobId = normalizedJobId,
                currentJobType = "",
            )
        }
        awaitXiaohongshuSummaryJob(baseUrl, normalizedJobId)
    }
}

fun MainViewModel.retryXiaohongshuJob(jobId: String) {
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
                saveStatus = "",
                captureRefreshStatus = "",
            )
        }
        when (val result = apiRepository.retryAsyncJob(baseUrl, normalizedJobId)) {
            is AppResult.Success -> {
                if (result.data.jobType != XIAOHONGSHU_CAPTURE_JOB_TYPE) {
                    _xiaohongshuState.update {
                        it.copy(
                            isSummarizingUrl = false,
                            currentJobId = "",
                            currentJobType = "",
                            errorMessage = "该任务类型已下线，请改用单链接总结。",
                        )
                    }
                    refreshXiaohongshuAsyncJobs(baseUrl)
                    return@launch
                }
                _xiaohongshuState.update {
                    it.copy(
                        currentJobId = result.data.jobId,
                        currentJobType = result.data.jobType,
                        summarizeUrlStatus = "已重新提交后台总结...（${result.data.jobId.take(8)}）",
                    )
                }
                refreshXiaohongshuAsyncJobs(baseUrl)
                awaitXiaohongshuSummaryJob(baseUrl, result.data.jobId)
            }

            is AppResult.Error -> {
                _xiaohongshuState.update {
                    it.copy(
                        isSummarizingUrl = false,
                        summarizeUrlStatus = "",
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

internal suspend fun MainViewModel.refreshBilibiliAsyncJobs(baseUrl: String) {
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

internal suspend fun MainViewModel.refreshXiaohongshuAsyncJobs(baseUrl: String) {
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
            jobType = XIAOHONGSHU_CAPTURE_JOB_TYPE,
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
                        context = ErrorContext.XIAOHONGSHU_JOB,
                    ),
                )
            }
        }
    }
}

internal suspend fun MainViewModel.awaitBilibiliSummaryJob(baseUrl: String, jobId: String) {
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

internal suspend fun MainViewModel.awaitXiaohongshuSummaryJob(baseUrl: String, jobId: String) {
    repeat(ASYNC_JOB_POLL_MAX_ATTEMPTS) { attempt ->
        when (val status = apiRepository.getAsyncJob(baseUrl, jobId)) {
            is AppResult.Success -> {
                when (status.data.status) {
                    "PENDING", "RUNNING" -> {
                        _xiaohongshuState.update {
                            it.copy(
                                currentJobId = jobId,
                                currentJobType = XIAOHONGSHU_CAPTURE_JOB_TYPE,
                                summarizeUrlStatus = if (status.data.status == "PENDING") {
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
                        val parsed = status.data.result?.toXiaohongshuSummaryItem()
                        if (parsed == null) {
                            _xiaohongshuState.update {
                                it.copy(
                                    isSummarizingUrl = false,
                                    currentJobType = XIAOHONGSHU_CAPTURE_JOB_TYPE,
                                    summarizeUrlStatus = "",
                                    errorMessage = "任务完成，但结果格式无法识别。",
                                )
                            }
                        } else {
                            _xiaohongshuState.update {
                                it.copy(
                                    isSummarizingUrl = false,
                                    currentJobType = XIAOHONGSHU_CAPTURE_JOB_TYPE,
                                    summaries = mergeXiaohongshuSummaries(it.summaries, listOf(parsed)),
                                    summarizeUrlStatus = "单篇笔记总结完成，可直接保存。",
                                )
                            }
                        }
                        refreshXiaohongshuAsyncJobs(baseUrl)
                        return
                    }

                    else -> {
                        _xiaohongshuState.update {
                            it.copy(
                                isSummarizingUrl = false,
                                currentJobType = XIAOHONGSHU_CAPTURE_JOB_TYPE,
                                summarizeUrlStatus = "",
                                errorMessage = status.data.error?.message
                                    ?: status.data.message.ifBlank { "后台总结失败。" },
                            )
                        }
                        refreshXiaohongshuAsyncJobs(baseUrl)
                        return
                    }
                }
            }

            is AppResult.Error -> {
                _xiaohongshuState.update {
                    it.copy(
                        isSummarizingUrl = false,
                        summarizeUrlStatus = "",
                        errorMessage = ErrorMessageMapper.format(
                            code = status.code,
                            message = status.message,
                            context = ErrorContext.XIAOHONGSHU_JOB,
                        ),
                    )
                }
                refreshXiaohongshuAsyncJobs(baseUrl)
                return
            }
        }
    }
    _xiaohongshuState.update {
        it.copy(
            isSummarizingUrl = false,
            summarizeUrlStatus = "",
            errorMessage = "后台任务等待超时，请稍后重试。任务ID：$jobId",
        )
    }
    refreshXiaohongshuAsyncJobs(baseUrl)
}

internal fun Map<String, Any?>.toBilibiliSummaryData(): BilibiliSummaryData? {
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

internal fun Map<String, Any?>.toXiaohongshuSummaryItem(): XiaohongshuSummaryItem? {
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

internal fun mergeXiaohongshuSummaries(
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

internal fun Map<String, Any?>.stringValue(key: String): String {
    return when (val value = this[key]) {
        null -> ""
        is String -> value.trim()
        else -> value.toString().trim()
    }
}

internal fun Map<String, Any?>.intValue(key: String): Int {
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
