package com.midas.client.ui.screen

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.ui.components.MarkdownText

@Composable
internal fun XiaohongshuPanel(
    state: XiaohongshuUiState,
    onUrlChange: (String) -> Unit,
    onSummarizeUrl: () -> Unit,
    onRefreshAuthConfig: () -> Unit,
    onSaveSingleNote: (XiaohongshuSummaryItem) -> Unit,
    onRefreshJobs: () -> Unit,
    onOpenJob: (String) -> Unit,
    onRetryJob: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("小红书链接总结", style = MaterialTheme.typography.titleMedium)

        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("单链接总结", style = MaterialTheme.typography.titleSmall)
                OutlinedTextField(
                    value = state.urlInput,
                    onValueChange = onUrlChange,
                    label = { Text("单篇笔记 URL") },
                    trailingIcon = {
                        if (state.urlInput.isNotBlank()) {
                            IconButton(
                                onClick = { onUrlChange("") },
                                modifier = Modifier.testTag("xhs_url_clear_button"),
                            ) {
                                Text("X")
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("xhs_url_input"),
                    singleLine = true,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    MidasButton(
                        onClick = onSummarizeUrl,
                        enabled = !state.isSummarizingUrl,
                        modifier = Modifier.weight(1f),
                    ) {
                        SingleLineActionText(
                            if (state.currentJobType == "xiaohongshu_summarize_url" && state.isSummarizingUrl) {
                                "总结中..."
                            } else {
                                "总结单篇"
                            },
                        )
                    }
                    MidasButton(
                        onClick = onRefreshAuthConfig,
                        enabled = !state.isRefreshingCaptureConfig,
                        tone = ButtonTone.NEUTRAL,
                        modifier = Modifier
                            .weight(1f)
                            .testTag("xhs_refresh_auth_button"),
                    ) {
                        SingleLineActionText(if (state.isRefreshingCaptureConfig) "更新中..." else "更新Auth")
                    }
                }
                Text(
                    text = "读取默认 HAR 或 cURL，自动更新小红书请求头；单篇失败时先刷新登录态。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (state.summarizeUrlStatus.isNotBlank()) {
                    Text(text = state.summarizeUrlStatus, color = SuccessStatusColor)
                }
            }
        }

        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = ErrorStatusColor)
        }
        if (state.currentJobId.isNotBlank()) {
            Text(
                text = "当前任务：${asyncJobTypeLabel(state.currentJobType)} · ${state.currentJobId}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (state.saveStatus.isNotBlank()) {
            Text(text = state.saveStatus, color = SuccessStatusColor)
        }
        if (state.captureRefreshStatus.isNotBlank()) {
            Text(text = state.captureRefreshStatus, color = SuccessStatusColor)
        }
        AsyncJobHistoryCard(
            title = "最近任务",
            jobs = state.recentJobs,
            isLoading = state.isRecentJobsLoading,
            statusText = state.recentJobsStatus,
            onRefresh = onRefreshJobs,
            onOpenJob = onOpenJob,
            onRetryJob = onRetryJob,
            listTestTag = "xhs_recent_jobs",
        )

        if (state.summaries.isNotEmpty()) {
            Text(
                text = "当前结果（${state.summaries.size} 条）",
                style = MaterialTheme.typography.titleSmall,
            )
        }
        state.summaries.forEach { summary ->
            XiaohongshuSummaryCard(
                item = summary,
                onSave = { onSaveSingleNote(summary) },
                isSaving = summary.noteId in state.savingSingleNoteIds,
                isSaved = summary.noteId in state.savedNoteIds,
            )
        }
    }
}

@Composable
private fun XiaohongshuSummaryCard(
    item: XiaohongshuSummaryItem,
    onSave: () -> Unit,
    isSaving: Boolean,
    isSaved: Boolean,
) {
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    item.title,
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.weight(1f),
                )
                MidasButton(
                    onClick = onSave,
                    enabled = !isSaving && !isSaved,
                    tone = ButtonTone.SUCCESS,
                    modifier = Modifier.testTag("xhs_save_single_${item.noteId}"),
                ) {
                    SingleLineActionText(
                        when {
                            isSaved -> "已保存"
                            isSaving -> "保存中..."
                            else -> "保存此篇"
                        },
                    )
                }
            }
            Text("ID: ${item.noteId}", style = MaterialTheme.typography.bodySmall)
            Text(item.sourceUrl, style = MaterialTheme.typography.bodySmall)
            HorizontalDivider()
            MarkdownText(markdown = item.summaryMarkdown, modifier = Modifier.fillMaxWidth())
        }
    }
}
