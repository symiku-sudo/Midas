package com.midas.client.ui.screen

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.midas.client.data.model.AsyncJobListItemData
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.ui.components.MarkdownText
import java.util.Locale

@Composable
internal fun BilibiliPanel(
    state: BilibiliUiState,
    onVideoUrlChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onSaveNote: () -> Unit,
    onRefreshJobs: () -> Unit,
    onOpenJob: (String) -> Unit,
    onRetryJob: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("B 站视频总结", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = state.videoUrlInput,
            onValueChange = onVideoUrlChange,
            label = { Text("输入 B 站视频链接或 BV 号") },
            supportingText = {
                Text("示例：BV1xx411c7mD 或 https://www.bilibili.com/video/BV1xx411c7mD")
            },
            trailingIcon = {
                if (state.videoUrlInput.isNotBlank()) {
                    IconButton(
                        onClick = { onVideoUrlChange("") },
                        modifier = Modifier.testTag("bilibili_url_clear_button"),
                    ) {
                        Text("X")
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MidasButton(onClick = onSubmit, enabled = !state.isLoading) {
                SingleLineActionText(if (state.isLoading) "处理中..." else "开始总结")
            }
            MidasButton(
                onClick = onSaveNote,
                enabled = !state.isSavingNote && state.result != null,
                tone = ButtonTone.SUCCESS,
            ) {
                SingleLineActionText(if (state.isSavingNote) "保存中..." else "保存总结")
            }
        }
        if (state.isLoading) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CircularProgressIndicator(modifier = Modifier.height(20.dp))
                Text("高精度处理中，请耐心等待。")
            }
        }
        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = ErrorStatusColor)
        }
        if (state.submitStatus.isNotBlank()) {
            Text(text = state.submitStatus, color = LinkStatusColor)
        }
        if (state.saveStatus.isNotBlank()) {
            Text(text = state.saveStatus, color = SuccessStatusColor)
        }
        AsyncJobHistoryCard(
            title = "最近任务",
            jobs = state.recentJobs,
            isLoading = state.isRecentJobsLoading,
            statusText = state.recentJobsStatus,
            onRefresh = onRefreshJobs,
            onOpenJob = onOpenJob,
            onRetryJob = onRetryJob,
            listTestTag = "bilibili_recent_jobs",
        )
        state.result?.let { result ->
            BilibiliResult(result)
        }
    }
}

@Composable
private fun BilibiliResult(result: BilibiliSummaryData) {
    val elapsedSeconds = result.elapsedMs / 1000.0
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("链接：${result.videoUrl}", style = MaterialTheme.typography.bodySmall)
            Text(
                "耗时：${"%.1f".format(elapsedSeconds)} s，转写字数：${result.transcriptChars}",
                style = MaterialTheme.typography.bodySmall,
            )
            HorizontalDivider()
            MarkdownText(markdown = result.summaryMarkdown, modifier = Modifier.fillMaxWidth())
        }
    }
}

@Composable
internal fun AsyncJobHistoryCard(
    title: String,
    jobs: List<AsyncJobListItemData>,
    isLoading: Boolean,
    statusText: String,
    onRefresh: () -> Unit,
    onOpenJob: (String) -> Unit,
    onRetryJob: (String) -> Unit,
    listTestTag: String,
) {
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(title, style = MaterialTheme.typography.titleSmall)
                MidasButton(
                    onClick = onRefresh,
                    enabled = !isLoading,
                    tone = ButtonTone.NEUTRAL,
                ) {
                    SingleLineActionText(if (isLoading) "刷新中..." else "刷新任务")
                }
            }
            if (statusText.isNotBlank()) {
                Text(
                    text = statusText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (jobs.isEmpty() && !isLoading && statusText.isBlank()) {
                Text("暂无最近任务。", style = MaterialTheme.typography.bodySmall)
            }
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .then(Modifier.testTag(listTestTag)),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                jobs.forEach { item ->
                    AsyncJobHistoryItem(
                        item = item,
                        onOpenJob = onOpenJob,
                        onRetryJob = onRetryJob,
                    )
                }
            }
        }
    }
}

@Composable
private fun AsyncJobHistoryItem(
    item: AsyncJobListItemData,
    onOpenJob: (String) -> Unit,
    onRetryJob: (String) -> Unit,
) {
    val statusColor = asyncJobStatusColor(item.status)
    val statusLabel = asyncJobStatusLabel(item.status)
    val primaryActionLabel = when (item.status) {
        "SUCCEEDED" -> "查看结果"
        "PENDING", "RUNNING" -> "继续等待"
        else -> ""
    }
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = "${asyncJobTypeLabel(item.jobType)} · $statusLabel",
                    style = MaterialTheme.typography.bodyMedium,
                    color = statusColor,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = item.jobId.take(8),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                text = "提交：${item.submittedAt}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (item.finishedAt.isNotBlank()) {
                Text(
                    text = "结束：${item.finishedAt}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (item.retryOfJobId.isNotBlank()) {
                Text(
                    text = "重试自：${item.retryOfJobId.take(8)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = LinkStatusColor,
                )
            }
            item.progress?.let { progress ->
                if (progress.total > 0) {
                    Text(
                        text = "进度：${progress.current}/${progress.total}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Text(
                text = item.message,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (primaryActionLabel.isNotBlank()) {
                    MidasButton(
                        onClick = { onOpenJob(item.jobId) },
                        tone = ButtonTone.NEUTRAL,
                        modifier = Modifier.testTag("job_open_${item.jobId}"),
                    ) {
                        SingleLineActionText(primaryActionLabel)
                    }
                }
                if (item.status == "FAILED" || item.status == "INTERRUPTED") {
                    MidasButton(
                        onClick = { onRetryJob(item.jobId) },
                        tone = ButtonTone.NEUTRAL,
                        modifier = Modifier.testTag("job_retry_${item.jobId}"),
                    ) {
                        SingleLineActionText("重试")
                    }
                }
            }
        }
    }
}

internal fun asyncJobTypeLabel(jobType: String): String {
    return when (jobType.trim().lowercase(Locale.ROOT)) {
        "bilibili_summarize" -> "B站总结"
        "xiaohongshu_summarize_url" -> "小红书单篇"
        else -> "后台任务"
    }
}

internal fun asyncJobStatusLabel(status: String): String {
    return when (status.trim().uppercase(Locale.ROOT)) {
        "PENDING" -> "排队中"
        "RUNNING" -> "执行中"
        "SUCCEEDED" -> "已完成"
        "FAILED" -> "失败"
        "INTERRUPTED" -> "中断"
        else -> status.ifBlank { "未知" }
    }
}

private fun asyncJobStatusColor(status: String): Color {
    return when (status.trim().uppercase(Locale.ROOT)) {
        "SUCCEEDED" -> SuccessStatusColor
        "FAILED", "INTERRUPTED" -> ErrorStatusColor
        "PENDING" -> WarningStatusColor
        else -> LinkStatusColor
    }
}
