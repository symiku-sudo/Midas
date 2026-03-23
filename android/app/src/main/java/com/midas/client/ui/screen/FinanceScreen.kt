package com.midas.client.ui.screen

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.midas.client.data.model.FinanceFocusCard
import com.midas.client.data.model.FinanceNewsItem
import com.midas.client.data.model.FinanceWatchlistItem
import com.midas.client.ui.components.MarkdownText
import java.util.Locale

@Composable
internal fun FinanceSignalsPanel(
    state: FinanceSignalsUiState,
    onRefresh: () -> Unit,
    onGenerateFinanceNewsDigest: () -> Unit,
    onToggleWatchlistNtfy: (Boolean) -> Unit,
    onDismissFocusCard: (FinanceFocusCard) -> Unit,
    onRestoreFocusCards: () -> Unit,
    onUpdateFocusCardStatus: (String, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var showAllNews by remember { mutableStateOf(false) }

    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("财经信号", style = MaterialTheme.typography.titleMedium)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    text = if (state.updateTime.isNotBlank()) {
                        "更新时间：${state.updateTime}"
                    } else {
                        "更新时间：等待数据"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = if (state.newsLastFetchTime.isNotBlank()) {
                        if (state.newsIsStale) {
                            "新闻拉取：${state.newsLastFetchTime}（数据可能陈旧）"
                        } else {
                            "新闻拉取：${state.newsLastFetchTime}"
                        }
                    } else {
                        "新闻拉取：等待数据"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if (state.newsIsStale) {
                        WarningStatusColor
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
            }
            MidasButton(
                onClick = onRefresh,
                enabled = !state.isLoading,
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText(if (state.isLoading) "刷新中..." else "刷新")
            }
        }

        if (state.focusCards.isNotEmpty()) {
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("今日关注建议", style = MaterialTheme.typography.titleSmall)
                                Text(
                                    text = "先处理优先级高的，再决定要不要展开行情和新闻明细。",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            if (state.dismissedFocusCardCount > 0) {
                                MidasButton(
                                    onClick = onRestoreFocusCards,
                                    tone = ButtonTone.NEUTRAL,
                                ) {
                                    SingleLineActionText("恢复 ${state.dismissedFocusCardCount}")
                                }
                            }
                        }
                        FinanceFocusCardList(
                            items = state.focusCards,
                            onDismiss = onDismissFocusCard,
                            onStatusChange = { item, status ->
                                if (item.cardId.isNotBlank()) {
                                    onUpdateFocusCardStatus(item.cardId, status)
                                }
                            },
                        )
                    }
                }
            } else if (state.dismissedFocusCardCount > 0) {
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(
                            text = "今日建议已全部处理",
                            style = MaterialTheme.typography.titleSmall,
                        )
                        MidasButton(
                            onClick = onRestoreFocusCards,
                            tone = ButtonTone.NEUTRAL,
                        ) {
                            SingleLineActionText("恢复 ${state.dismissedFocusCardCount}")
                        }
                    }
                }
            }

            if (state.focusCardHistory.isNotEmpty()) {
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("建议历史", style = MaterialTheme.typography.titleSmall)
                        state.focusCardHistory.take(5).forEachIndexed { index, item ->
                            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(
                                    text = item.title,
                                    style = MaterialTheme.typography.bodySmall,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                Text(
                                    text = "${item.status} · ${item.lastSeenAt.ifBlank { item.statusUpdatedAt }}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            if (index < state.focusCardHistory.take(5).lastIndex) {
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
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text("Watchlist", style = MaterialTheme.typography.titleSmall)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(
                                text = if (state.watchlistNtfyEnabled) "ntfy 已开启" else "ntfy 已关闭",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Switch(
                                checked = state.watchlistNtfyEnabled,
                                onCheckedChange = onToggleWatchlistNtfy,
                                enabled = !state.isUpdatingWatchlistNtfy,
                            )
                        }
                    }
                    when {
                        state.isLoading && state.watchlistPreview.isEmpty() -> {
                            Text("正在拉取行情数据...", style = MaterialTheme.typography.bodySmall)
                        }

                        state.watchlistPreview.isEmpty() -> {
                            Text("暂无可展示的行情标的。", style = MaterialTheme.typography.bodySmall)
                        }

                        else -> {
                            state.watchlistPreview.forEach { item ->
                                FinanceWatchlistRow(item = item)
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
                    Text("24小时新闻摘要", style = MaterialTheme.typography.titleSmall)
                    Text(
                        "按钮触发；距上次生成不足 3 小时会直接复用。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = if (state.digestLastGeneratedAt.isNotBlank()) {
                            "上次生成：${state.digestLastGeneratedAt}"
                        } else {
                            "上次生成：暂无"
                        },
                        modifier = Modifier.testTag("finance_digest_last_generated_at"),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    MidasButton(
                        onClick = onGenerateFinanceNewsDigest,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("finance_digest_button"),
                        enabled = !state.isGeneratingNewsDigest,
                        tone = ButtonTone.NEUTRAL,
                    ) {
                        SingleLineActionText(
                            if (state.isGeneratingNewsDigest) "正在生成24小时摘要..." else "生成24小时摘要",
                        )
                    }
                    when {
                        state.isGeneratingNewsDigest && state.aiInsightText.isBlank() -> {
                            Text("正在生成摘要...", style = MaterialTheme.typography.bodySmall)
                        }

                        state.aiInsightText.isBlank() -> {
                            Text("点击上方按钮后查看过去 24 小时新闻总结。", style = MaterialTheme.typography.bodySmall)
                        }

                        else -> {
                            MarkdownText(
                                markdown = state.aiInsightText,
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                }
            }

            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text("今日金融与时政新闻 Top5", style = MaterialTheme.typography.titleSmall)
                        if (state.topNews.size > 3) {
                            MidasButton(
                                onClick = { showAllNews = !showAllNews },
                                tone = ButtonTone.NEUTRAL,
                            ) {
                                SingleLineActionText(if (showAllNews) "收起新闻" else "展开全部")
                            }
                        }
                    }
                    FinanceTopNewsList(
                        items = if (showAllNews) state.topNews else state.topNews.take(3),
                        isLoading = state.isLoading,
                    )
                }
        }

        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = ErrorStatusColor)
        }
        if (state.statusMessage.isNotBlank()) {
            Text(text = state.statusMessage, color = SuccessStatusColor)
        }
    }
}

@Composable
private fun FinanceFocusCardList(
    items: List<FinanceFocusCard>,
    onDismiss: (FinanceFocusCard) -> Unit,
    onStatusChange: (FinanceFocusCard, String) -> Unit,
) {
    val groupedItems = items.groupBy { item -> item.actionType.uppercase(Locale.ROOT) }
    val orderedTypes = listOf("REVIEW_NOW", "FOLLOW_UP", "WAIT_CONFIRM", "MONITOR")
    val orderedGroups = orderedTypes.mapNotNull { type ->
        groupedItems[type]?.takeIf { group -> group.isNotEmpty() }?.let { group -> type to group }
    } + groupedItems.entries
        .filter { entry -> entry.key !in orderedTypes }
        .map { entry -> entry.key to entry.value }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        orderedGroups.forEachIndexed { groupIndex, (actionType, groupItems) ->
            Text(
                text = financeActionTypeGroupLabel(actionType),
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            groupItems.forEachIndexed { itemIndex, item ->
                FinanceFocusCardItem(
                    item = item,
                    onDismiss = { onDismiss(item) },
                    onStatusChange = { status -> onStatusChange(item, status) },
                )
                if (itemIndex < groupItems.lastIndex) {
                    HorizontalDivider()
                }
            }
            if (groupIndex < orderedGroups.lastIndex) {
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun FinanceFocusCardItem(
    item: FinanceFocusCard,
    onDismiss: () -> Unit,
    onStatusChange: (String) -> Unit,
) {
    val priorityColor = when (item.priority.uppercase(Locale.ROOT)) {
        "HIGH" -> ErrorStatusColor
        "LOW" -> LinkStatusColor
        else -> WarningStatusColor
    }
    val kindLabel = when (item.kind.uppercase(Locale.ROOT)) {
        "ALERT" -> "阈值提醒"
        "NEWS" -> "新闻关注"
        else -> item.kind
    }
    val actionTypeLabel = when (item.actionType.uppercase(Locale.ROOT)) {
        "REVIEW_NOW" -> "立即处理"
        "FOLLOW_UP" -> "继续跟进"
        "WAIT_CONFIRM" -> "等待确认"
        else -> "持续观察"
    }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = kindLabel,
                    style = MaterialTheme.typography.bodySmall,
                    color = priorityColor,
                    modifier = Modifier
                        .background(
                            color = priorityColor.copy(alpha = 0.14f),
                            shape = RoundedCornerShape(999.dp),
                        )
                        .padding(horizontal = 8.dp, vertical = 2.dp),
                )
                if (item.actionLabel.isNotBlank()) {
                    Text(
                        text = "${item.actionLabel} · $actionTypeLabel",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier
                            .background(
                                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
                                shape = RoundedCornerShape(999.dp),
                            )
                            .padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }
            MidasButton(
                onClick = onDismiss,
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText("已看过")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            MidasButton(
                onClick = { onStatusChange("WATCHING") },
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText("保持关注")
            }
            MidasButton(
                onClick = { onStatusChange("IGNORED_TODAY") },
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText("今日忽略")
            }
            if (item.status != "ACTIVE") {
                MidasButton(
                    onClick = { onStatusChange("ACTIVE") },
                    tone = ButtonTone.NEUTRAL,
                ) {
                    SingleLineActionText("取消忽略")
                }
            }
        }
        if (item.relatedWatchlistNames.isNotEmpty()) {
            Text(
                text = item.relatedWatchlistNames.joinToString(" / "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Text(
            text = item.title,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
        )
        if (item.summary.isNotBlank()) {
            Text(
                text = item.summary,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (item.actionHint.isNotBlank()) {
            Text(
                text = "建议动作：${item.actionHint}",
                style = MaterialTheme.typography.bodySmall,
                color = LinkStatusColor,
            )
        }
        if (item.portfolioImpactSummary.isNotBlank()) {
            Text(
                text = item.portfolioImpactSummary,
                style = MaterialTheme.typography.bodySmall,
                color = SuccessStatusColor,
            )
        }
        if (item.reasons.isNotEmpty()) {
            Text(
                text = "触发原因：${item.reasons.joinToString(" / ") { financeReasonLabel(it) }}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (item.statusUpdatedAt.isNotBlank() && item.status != "ACTIVE") {
            Text(
                text = "最近处理：${item.status} · ${item.statusUpdatedAt}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun financeActionTypeGroupLabel(actionType: String): String {
    return when (actionType.uppercase(Locale.ROOT)) {
        "REVIEW_NOW" -> "优先处理"
        "FOLLOW_UP" -> "继续跟进"
        "WAIT_CONFIRM" -> "等待确认"
        else -> "持续观察"
    }
}

private fun financeReasonLabel(code: String): String {
    return when (code.trim().lowercase(Locale.ROOT)) {
        "threshold_triggered" -> "阈值触发"
        "related_news_present" -> "已有关联新闻"
        "keyword_overlap" -> "关键词重合"
        "recent_alert_sent" -> "近期已告警"
        "news_impacts_watchlist" -> "新闻影响关注项"
        "linked_alert_active" -> "关联标的已触发阈值"
        "multi_asset_impact" -> "影响多个标的"
        else -> code
    }
}

@Composable
private fun FinanceWatchlistRow(item: FinanceWatchlistItem) {
    val priceText = item.price?.let { "%.2f".format(it) } ?: "N/A"
    val normalizedChange = item.changePct.trim().ifBlank { "N/A" }
    val normalizedHint = item.alertHint.trim()
    val changeColor = when {
        normalizedChange.startsWith("+") -> SuccessStatusColor
        normalizedChange.startsWith("-") -> ErrorStatusColor
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    val hintColor = if (item.alertActive) {
        ErrorStatusColor
    } else {
        MaterialTheme.colorScheme.onSurfaceVariant
    }
    val hintBackground = if (item.alertActive) {
        ErrorStatusColor.copy(alpha = 0.14f)
    } else {
        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.68f)
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = if (item.name.isNotBlank()) item.name else item.symbol,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = item.symbol,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (normalizedHint.isNotBlank()) {
                    Text(
                        text = "阈值 $normalizedHint",
                        style = MaterialTheme.typography.bodySmall,
                        color = hintColor,
                        modifier = Modifier
                            .background(
                                color = hintBackground,
                                shape = RoundedCornerShape(999.dp),
                            )
                            .padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }
            if (item.relatedNewsCount > 0) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "关联新闻 ${item.relatedNewsCount}",
                        style = MaterialTheme.typography.bodySmall,
                        color = LinkStatusColor,
                        modifier = Modifier
                            .background(
                                color = LinkStatusColor.copy(alpha = 0.12f),
                                shape = RoundedCornerShape(999.dp),
                            )
                            .padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                    if (item.relatedKeywords.isNotEmpty()) {
                        Text(
                            text = item.relatedKeywords.joinToString(" / "),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(priceText, style = MaterialTheme.typography.bodySmall)
            Text(
                normalizedChange,
                style = MaterialTheme.typography.bodySmall,
                color = changeColor,
            )
        }
    }
}

@Composable
private fun FinanceTopNewsList(
    items: List<FinanceNewsItem>,
    isLoading: Boolean,
) {
    when {
        isLoading && items.isEmpty() -> {
            Text("正在拉取今日新闻...", style = MaterialTheme.typography.bodySmall)
        }

        items.isEmpty() -> {
            Text("今日暂无可展示的金融或时政新闻。", style = MaterialTheme.typography.bodySmall)
        }

        else -> {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items.forEachIndexed { index, item ->
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "${index + 1}. ${item.title}",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (item.category.isNotBlank()) {
                                val categoryLabel = when (item.category.lowercase(Locale.getDefault())) {
                                    "finance" -> "金融"
                                    "politics" -> "时政"
                                    else -> item.category
                                }
                                Text(
                                    text = categoryLabel,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = LinkStatusColor,
                                    modifier = Modifier
                                        .background(
                                            color = LinkStatusColor.copy(alpha = 0.12f),
                                            shape = RoundedCornerShape(999.dp),
                                        )
                                        .padding(horizontal = 8.dp, vertical = 2.dp),
                                )
                            }
                            if (item.relatedWatchlistNames.isNotEmpty()) {
                                Text(
                                    text = "影响 ${item.relatedWatchlistNames.joinToString(" / ")}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = WarningStatusColor,
                                    modifier = Modifier
                                        .background(
                                            color = WarningStatusColor.copy(alpha = 0.12f),
                                            shape = RoundedCornerShape(999.dp),
                                        )
                                        .padding(horizontal = 8.dp, vertical = 2.dp),
                                )
                            }
                            val metaText = listOf(item.publisher, item.published)
                                .filter { it.isNotBlank() }
                                .joinToString(" · ")
                            if (metaText.isNotBlank()) {
                                Text(
                                    text = metaText,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    if (index < items.lastIndex) {
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}
