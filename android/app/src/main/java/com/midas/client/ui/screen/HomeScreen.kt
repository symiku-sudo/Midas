package com.midas.client.ui.screen

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@Composable
fun HomeScreen(
    state: HomeUiState,
    onRefresh: () -> Unit,
    onOpenSection: (TopSection) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("总览", style = MaterialTheme.typography.titleMedium)
                Text(
                    text = if (state.generatedAt.isNotBlank()) {
                        "最近刷新：${state.generatedAt}"
                    } else {
                        "启动后先看这里，再决定进哪个功能页。"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            MidasButton(onClick = onRefresh, tone = ButtonTone.NEUTRAL) {
                SingleLineActionText(if (state.isLoading) "刷新中..." else "刷新总览")
            }
        }

        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("高频入口", style = MaterialTheme.typography.titleSmall)
                state.quickLinks.take(3).forEach { item ->
                    val section = when (item.target.lowercase()) {
                        "bilibili" -> TopSection.BILIBILI
                        "xiaohongshu" -> TopSection.XHS
                        "notes" -> TopSection.NOTES
                        "finance" -> TopSection.FINANCE
                        "settings" -> TopSection.SETTINGS
                        else -> TopSection.HOME
                    }
                    MidasButton(
                        onClick = { onOpenSection(section) },
                        modifier = Modifier.fillMaxWidth(),
                        tone = ButtonTone.NEUTRAL,
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(item.title, style = MaterialTheme.typography.labelMedium)
                            if (item.subtitle.isNotBlank()) {
                                Text(
                                    item.subtitle,
                                    style = MaterialTheme.typography.bodySmall,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                    }
                }
            }
        }

        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("最近任务", style = MaterialTheme.typography.titleSmall)
                if (state.recentTasks.isEmpty()) {
                    Text("暂无任务记录。", style = MaterialTheme.typography.bodySmall)
                } else {
                    state.recentTasks.take(4).forEachIndexed { index, item ->
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(
                                text = "${asyncJobTypeLabel(item.jobType)} · ${asyncJobStatusLabel(item.status)}",
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                text = item.message.ifBlank { item.submittedAt },
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        if (index < state.recentTasks.take(4).lastIndex) {
                            HorizontalDivider()
                        }
                    }
                }
            }
        }

        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("最近新增笔记", style = MaterialTheme.typography.titleSmall)
                if (state.recentNotes.isEmpty()) {
                    Text("暂无已保存笔记。", style = MaterialTheme.typography.bodySmall)
                } else {
                    state.recentNotes.take(4).forEachIndexed { index, item ->
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(
                                text = item.title.ifBlank { item.noteId },
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                text = "${item.source} · ${item.savedAt}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (index < state.recentNotes.take(4).lastIndex) {
                            HorizontalDivider()
                        }
                    }
                }
            }
        }

        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("今日财经建议", style = MaterialTheme.typography.titleSmall)
                if (state.financeFocusCards.isEmpty()) {
                    Text("暂无高优先级建议。", style = MaterialTheme.typography.bodySmall)
                } else {
                    state.financeFocusCards.take(3).forEachIndexed { index, item ->
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(
                                text = item.title,
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                text = item.portfolioImpactSummary.ifBlank { item.actionHint },
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        if (index < state.financeFocusCards.take(3).lastIndex) {
                            HorizontalDivider()
                        }
                    }
                    MidasButton(
                        onClick = { onOpenSection(TopSection.FINANCE) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        SingleLineActionText("进入资产页处理建议")
                    }
                }
            }
        }

        if (state.assetTotalAmountWan > 0) {
            Text(
                text = "当前资产总览：${"%.2f".format(state.assetTotalAmountWan)} 万",
                style = MaterialTheme.typography.bodySmall,
                color = SuccessStatusColor,
            )
        }
        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = ErrorStatusColor)
        }
    }
}
