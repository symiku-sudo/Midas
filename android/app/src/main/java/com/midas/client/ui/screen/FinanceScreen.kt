package com.midas.client.ui.screen

import android.content.ClipData
import android.content.ClipboardManager
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.midas.client.data.model.FinanceNewsItem
import com.midas.client.data.model.FinanceWatchlistItem
import com.midas.client.ui.components.MarkdownText
import java.util.Locale

private enum class AssetPanelTab(val title: String) {
    WATCHLIST("Watchlist"),
    ASSET_STATS("资产统计"),
}

@Composable
internal fun FinanceSignalsPanel(
    state: FinanceSignalsUiState,
    onRefresh: () -> Unit,
    onAssetAmountChange: (String, String) -> Unit,
    onSaveAssetStats: () -> Unit,
    onDeleteAssetHistoryRecord: (String) -> Unit,
    onAssetSummaryCopied: () -> Unit,
    onGenerateFinanceNewsDigest: () -> Unit,
    onToggleWatchlistNtfy: (Boolean) -> Unit,
    onFillAssetStatsFromImages: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var selectedAssetTab by remember { mutableStateOf(AssetPanelTab.WATCHLIST) }
    var showAllNews by remember { mutableStateOf(false) }

    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("财经", style = MaterialTheme.typography.titleMedium)
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

        GlassTabBar(
            selectedTabIndex = selectedAssetTab.ordinal,
            labels = AssetPanelTab.entries.map { it.title },
            onSelect = { index -> selectedAssetTab = AssetPanelTab.entries[index] },
        )

        if (selectedAssetTab == AssetPanelTab.WATCHLIST) {
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
        } else {
            AssetStatsCard(
                state = state,
                onAssetAmountChange = onAssetAmountChange,
                onSaveAssetStats = onSaveAssetStats,
                onDeleteAssetHistoryRecord = onDeleteAssetHistoryRecord,
                onAssetSummaryCopied = onAssetSummaryCopied,
                onFillAssetStatsFromImages = onFillAssetStatsFromImages,
            )
        }

        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = ErrorStatusColor)
        }
        if (state.statusMessage.isNotBlank()) {
            Text(text = state.statusMessage, color = SuccessStatusColor)
        }
    }
}

private fun formatAmountWanRmb(amount: Double): String {
    return "${"%.2f".format(Locale.US, amount)} 万元人民币"
}

private data class AssetBreakdownItem(
    val label: String,
    val amountWan: Double,
)

private fun collectNonZeroAssetBreakdown(
    drafts: List<AssetCategoryDraft>,
): List<AssetBreakdownItem> {
    return drafts.mapNotNull { draft ->
        val amount = draft.amountInput.trim().replace(",", "").toDoubleOrNull() ?: 0.0
        if (amount > 0.0) {
            AssetBreakdownItem(label = draft.label, amountWan = amount)
        } else {
            null
        }
    }.sortedByDescending { it.amountWan }
}

@Composable
private fun AssetStatsCard(
    state: FinanceSignalsUiState,
    onAssetAmountChange: (String, String) -> Unit,
    onSaveAssetStats: () -> Unit,
    onDeleteAssetHistoryRecord: (String) -> Unit,
    onAssetSummaryCopied: () -> Unit,
    onFillAssetStatsFromImages: () -> Unit,
) {
    val context = LocalContext.current
    var selectedHistoryId by remember { mutableStateOf<String?>(null) }
    val selectedHistory = state.assetHistory.firstOrNull { it.id == selectedHistoryId }
    val nonZeroBreakdown = collectNonZeroAssetBreakdown(state.assetDrafts)
    var showEditor by remember(state.assetHistory.size) {
        mutableStateOf(state.assetHistory.isEmpty() && nonZeroBreakdown.isEmpty())
    }
    var showHistory by remember(state.assetHistory.size) { mutableStateOf(false) }
    BackHandler(enabled = selectedHistoryId != null) {
        selectedHistoryId = null
    }

    if (selectedHistory != null) {
        AssetHistoryDetailPanel(
            record = selectedHistory,
            drafts = state.assetDrafts,
            onBack = { selectedHistoryId = null },
        )
        return
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("资产总览", style = MaterialTheme.typography.titleSmall)
                Text(
                    text = formatAmountWanRmb(state.assetTotalAmount),
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = if (state.assetHistory.isNotEmpty()) {
                        "最近保存：${state.assetHistory.first().savedAt}"
                    } else {
                        "最近保存：暂无历史记录"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "非零分类 ${nonZeroBreakdown.size} 项 · 历史记录 ${state.assetHistory.size} 条",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (nonZeroBreakdown.isEmpty()) {
                    Text(
                        "还没有录入资产分类，先展开下方“编辑资产分类”。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    nonZeroBreakdown.take(3).forEach { item ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(
                                text = item.label,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                text = formatAmountWanRmb(item.amountWan),
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                    }
                    if (nonZeroBreakdown.size > 3) {
                        Text(
                            "其余 ${nonZeroBreakdown.size - 3} 项已折叠到编辑区。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                MidasButton(
                    onClick = { showEditor = !showEditor },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("asset_toggle_editor_button"),
                    tone = if (showEditor) ButtonTone.NEUTRAL else ButtonTone.SUCCESS,
                ) {
                    SingleLineActionText(if (showEditor) "收起资产录入" else "编辑资产分类")
                }
                if (state.assetHistory.isNotEmpty()) {
                    MidasButton(
                        onClick = { showHistory = !showHistory },
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("asset_toggle_history_button"),
                        tone = ButtonTone.NEUTRAL,
                    ) {
                        SingleLineActionText(
                            if (showHistory) "收起历史记录" else "查看历史记录（${state.assetHistory.size}）",
                        )
                    }
                }
                MidasButton(
                    onClick = {
                        val text = buildAssetSummaryText(state)
                        val clipboard = context.getSystemService(ClipboardManager::class.java)
                        clipboard?.setPrimaryClip(ClipData.newPlainText("asset_summary", text))
                        onAssetSummaryCopied()
                    },
                    enabled = !state.isFillingAssetFromImages,
                    modifier = Modifier.fillMaxWidth(),
                    tone = ButtonTone.NEUTRAL,
                ) {
                    SingleLineActionText("复制资产情况")
                }
                if (state.assetErrorMessage.isNotBlank()) {
                    Text(text = state.assetErrorMessage, color = ErrorStatusColor)
                }
                if (state.assetStatusMessage.isNotBlank()) {
                    Text(text = state.assetStatusMessage, color = SuccessStatusColor)
                }
            }
        }

        if (showEditor) {
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("资产分类录入", style = MaterialTheme.typography.titleSmall)
                    Text(
                        "按风险从高到低排序，单位：万元人民币。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    state.assetDrafts.forEach { draft ->
                        OutlinedTextField(
                            value = draft.amountInput,
                            onValueChange = { value -> onAssetAmountChange(draft.key, value) },
                            label = { Text(draft.label) },
                            placeholder = { Text("例如：12.50（万元）") },
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("asset_amount_${draft.key}"),
                            singleLine = true,
                        )
                    }
                    MidasButton(
                        onClick = onSaveAssetStats,
                        enabled = !state.isSavingAssetStats && !state.isFillingAssetFromImages,
                        modifier = Modifier.fillMaxWidth(),
                        tone = ButtonTone.SUCCESS,
                    ) {
                        SingleLineActionText(
                            if (state.isSavingAssetStats) "保存中..." else "保存资产统计",
                        )
                    }
                    MidasButton(
                        onClick = onFillAssetStatsFromImages,
                        enabled = !state.isFillingAssetFromImages && !state.isSavingAssetStats,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("asset_fill_from_images_button"),
                    ) {
                        SingleLineActionText(
                            if (state.isFillingAssetFromImages) "识别中..." else "图片识别回填",
                        )
                    }
                    Text(
                        text = "支持最多上传 5 张图片，回填后不会自动保存。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        if (showHistory) {
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("历史记录（近到远）", style = MaterialTheme.typography.titleSmall)
                    state.assetHistory.forEach { record ->
                        AssetHistoryListItem(
                            record = record,
                            onOpen = { selectedHistoryId = record.id },
                            onDelete = { onDeleteAssetHistoryRecord(record.id) },
                        )
                    }
                }
            }
        }
    }
}

private fun buildAssetSummaryText(state: FinanceSignalsUiState): String {
    val lines = mutableListOf<String>()
    lines += "资产情况（单位：万元人民币）"
    var nonZeroCount = 0
    state.assetDrafts.forEach { draft ->
        val amount = draft.amountInput.trim().replace(",", "").toDoubleOrNull() ?: 0.0
        if (amount > 0.0) {
            lines += "${draft.label}：${formatAmountWanRmb(amount)}"
            nonZeroCount += 1
        }
    }
    if (nonZeroCount == 0) {
        lines += "暂无已填资产。"
    }
    lines += "总资产：${formatAmountWanRmb(state.assetTotalAmount)}"
    return lines.joinToString("\n")
}

@Composable
private fun AssetHistoryListItem(
    record: AssetHistoryRecord,
    onOpen: () -> Unit,
    onDelete: () -> Unit,
) {
    var menuExpanded by remember(record.id) { mutableStateOf(false) }
    GlassCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("asset_history_open_${record.id}")
            .clickable(onClick = onOpen),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text("保存时间：${record.savedAt}", style = MaterialTheme.typography.bodySmall)
                Text(
                    "总资产：${formatAmountWanRmb(record.totalAmountWan)}",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Box {
                IconButton(
                    onClick = { menuExpanded = true },
                    modifier = Modifier.testTag("asset_history_menu_${record.id}"),
                ) {
                    Text("⋮")
                }
                androidx.compose.material3.DropdownMenu(
                    expanded = menuExpanded,
                    onDismissRequest = { menuExpanded = false },
                ) {
                    androidx.compose.material3.DropdownMenuItem(
                        text = { Text("删除记录") },
                        onClick = {
                            menuExpanded = false
                            onDelete()
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun AssetHistoryDetailPanel(
    record: AssetHistoryRecord,
    drafts: List<AssetCategoryDraft>,
    onBack: () -> Unit,
) {
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("历史记录详情", style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MidasButton(onClick = onBack, tone = ButtonTone.NEUTRAL) {
                    SingleLineActionText("返回列表")
                }
            }
            Text("保存时间：${record.savedAt}", style = MaterialTheme.typography.bodySmall)
            Text(
                "总资产：${formatAmountWanRmb(record.totalAmountWan)}",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
            )
            HorizontalDivider()
            drafts.forEach { draft ->
                val amount = record.amounts[draft.key] ?: 0.0
                Text("${draft.label}：${formatAmountWanRmb(amount)}", style = MaterialTheme.typography.bodySmall)
            }
        }
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
                            if (item.publisher.isNotBlank()) {
                                Text(
                                    text = item.publisher,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                        if (item.relatedWatchlistNames.isNotEmpty()) {
                            Text(
                                text = "影响标的：${item.relatedWatchlistNames.joinToString(" / ")}",
                                style = MaterialTheme.typography.bodySmall,
                                color = WarningStatusColor,
                            )
                        }
                        if (item.matchedKeywords.isNotEmpty()) {
                            Text(
                                text = "关键词：${item.matchedKeywords.joinToString(" / ")}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
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
