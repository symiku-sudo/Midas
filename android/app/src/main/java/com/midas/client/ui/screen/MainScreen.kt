package com.midas.client.ui.screen

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.midas.client.data.model.NotesMergeCandidateItem
import com.midas.client.data.model.UnifiedNoteItem
import com.midas.client.data.model.XiaohongshuSummaryItem
import kotlinx.coroutines.delay

enum class TopSection(val title: String) {
    FINANCE("财经"),
    BILIBILI("B站"),
    XHS("小红书"),
    NOTES("笔记"),
    SETTINGS("设置"),
}

internal enum class ButtonTone {
    PRIMARY,
    SUCCESS,
    NEUTRAL,
}

internal val SuccessStatusColor = Color(0xFF7BE5A6)
internal val ErrorStatusColor = Color(0xFFFF9A9A)
internal val WarningStatusColor = Color(0xFFFFD187)
internal val LinkStatusColor = Color(0xFF8ED8FF)
private const val WrappedTabThreshold = 4

@Composable
fun MainScreen(viewModel: MainViewModel) {
    val settings by viewModel.settingsState.collectAsStateWithLifecycle()
    val bilibili by viewModel.bilibiliState.collectAsStateWithLifecycle()
    val xiaohongshu by viewModel.xiaohongshuState.collectAsStateWithLifecycle()
    val notes by viewModel.notesState.collectAsStateWithLifecycle()
    val finance by viewModel.financeState.collectAsStateWithLifecycle()
    val assetImagesLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments(),
    ) { uris ->
        if (uris.isNotEmpty()) {
            viewModel.onAssetImagesSelected(uris)
        }
    }

    MainScreenContent(
        settings = settings,
        bilibili = bilibili,
        xiaohongshu = xiaohongshu,
        notes = notes,
        finance = finance,
        onAppForeground = viewModel::onAppForeground,
        onBaseUrlChange = viewModel::onBaseUrlInputChange,
        onAccessTokenChange = viewModel::onAccessTokenInputChange,
        onSaveBaseUrl = viewModel::saveBaseUrl,
        onTestConnection = viewModel::testConnection,
        onConfigTextChange = viewModel::onEditableConfigFieldTextChange,
        onConfigBooleanChange = viewModel::onEditableConfigFieldBooleanChange,
        onResetConfig = viewModel::resetEditableConfig,
        onBilibiliVideoUrlChange = viewModel::onBilibiliUrlInputChange,
        onSubmitBilibiliSummary = viewModel::submitBilibiliSummary,
        onSaveBilibiliNote = viewModel::saveCurrentBilibiliResult,
        onRefreshBilibiliJobs = viewModel::refreshBilibiliJobHistory,
        onOpenBilibiliJob = viewModel::openBilibiliJob,
        onRetryBilibiliJob = viewModel::retryBilibiliJob,
        onXiaohongshuUrlChange = viewModel::onXiaohongshuUrlInputChange,
        onSummarizeXiaohongshuUrl = viewModel::summarizeXiaohongshuByUrl,
        onRefreshXiaohongshuAuthConfig = viewModel::refreshXiaohongshuAuthConfig,
        onSaveSingleXiaohongshuNote = viewModel::saveSingleXiaohongshuSummary,
        onRefreshXiaohongshuJobs = viewModel::refreshXiaohongshuJobHistory,
        onOpenXiaohongshuJob = viewModel::openXiaohongshuJob,
        onRetryXiaohongshuJob = viewModel::retryXiaohongshuJob,
        onNotesKeywordChange = viewModel::onNotesKeywordInputChange,
        onNotesSourceFilterChange = viewModel::onNotesSourceFilterChange,
        onNotesDateWindowChange = viewModel::onNotesDateWindowChange,
        onNotesMergedFilterChange = viewModel::onNotesMergedFilterChange,
        onNotesSortChange = viewModel::onNotesSortChange,
        onRefreshNotes = viewModel::loadSavedNotes,
        onLoadRelatedNotes = viewModel::loadRelatedNotes,
        onDeleteBilibiliNote = viewModel::deleteBilibiliSavedNote,
        onClearBilibiliNotes = viewModel::clearBilibiliSavedNotes,
        onDeleteXiaohongshuNote = viewModel::deleteXiaohongshuSavedNote,
        onClearXiaohongshuNotes = viewModel::clearXiaohongshuSavedNotes,
        onSuggestMergeCandidates = viewModel::suggestMergeCandidates,
        onPreviewMergeCandidate = viewModel::previewMergeCandidate,
        onCommitCurrentMerge = viewModel::commitCurrentMerge,
        onRollbackLastMerge = viewModel::rollbackLastMerge,
        onFinalizeLastMerge = viewModel::finalizeLastMerge,
        onRefreshFinanceSignals = viewModel::loadFinanceSignals,
        onRefreshAssetStats = viewModel::refreshAssetStats,
        onAssetAmountChange = viewModel::onAssetAmountInputChange,
        onSaveAssetStats = viewModel::saveAssetStats,
        onDeleteAssetHistoryRecord = viewModel::deleteAssetHistoryRecord,
        onAssetSummaryCopied = viewModel::markAssetSummaryCopied,
        onGenerateFinanceNewsDigest = viewModel::generateFinanceNewsDigest,
        onToggleWatchlistNtfy = viewModel::setWatchlistNtfyEnabled,
        onFillAssetStatsFromImages = { assetImagesLauncher.launch(arrayOf("image/*")) },
        initialSection = TopSection.FINANCE,
    )
}

@Composable
@Suppress("UNUSED_PARAMETER")
fun MainScreenContent(
    settings: SettingsUiState,
    bilibili: BilibiliUiState,
    xiaohongshu: XiaohongshuUiState,
    notes: NotesUiState,
    finance: FinanceSignalsUiState = FinanceSignalsUiState(),
    onAppForeground: () -> Unit,
    onBaseUrlChange: (String) -> Unit,
    onAccessTokenChange: (String) -> Unit = {},
    onSaveBaseUrl: () -> Unit,
    onTestConnection: () -> Unit,
    onConfigTextChange: (String, String) -> Unit,
    onConfigBooleanChange: (String, Boolean) -> Unit,
    onResetConfig: () -> Unit,
    onBilibiliVideoUrlChange: (String) -> Unit,
    onSubmitBilibiliSummary: () -> Unit,
    onSaveBilibiliNote: () -> Unit,
    onRefreshBilibiliJobs: () -> Unit = {},
    onOpenBilibiliJob: (String) -> Unit = {},
    onRetryBilibiliJob: (String) -> Unit = {},
    onXiaohongshuUrlChange: (String) -> Unit,
    onSummarizeXiaohongshuUrl: () -> Unit,
    onRefreshXiaohongshuAuthConfig: () -> Unit,
    onSaveSingleXiaohongshuNote: (XiaohongshuSummaryItem) -> Unit,
    onRefreshXiaohongshuJobs: () -> Unit = {},
    onOpenXiaohongshuJob: (String) -> Unit = {},
    onRetryXiaohongshuJob: (String) -> Unit = {},
    onNotesKeywordChange: (String) -> Unit,
    onNotesSourceFilterChange: (String) -> Unit = {},
    onNotesDateWindowChange: (Int) -> Unit = {},
    onNotesMergedFilterChange: (String) -> Unit = {},
    onNotesSortChange: (String, String) -> Unit = { _, _ -> },
    onRefreshNotes: () -> Unit,
    onLoadRelatedNotes: (UnifiedNoteItem) -> Unit = {},
    onDeleteBilibiliNote: (String) -> Unit,
    onClearBilibiliNotes: () -> Unit = {},
    onDeleteXiaohongshuNote: (String) -> Unit,
    onClearXiaohongshuNotes: () -> Unit = {},
    onSuggestMergeCandidates: () -> Unit,
    onPreviewMergeCandidate: (NotesMergeCandidateItem) -> Unit,
    onCommitCurrentMerge: () -> Unit,
    onRollbackLastMerge: () -> Unit,
    onFinalizeLastMerge: () -> Unit,
    onRefreshFinanceSignals: () -> Unit = {},
    onRefreshAssetStats: () -> Unit = {},
    onAssetAmountChange: (String, String) -> Unit = { _, _ -> },
    onSaveAssetStats: () -> Unit = {},
    onDeleteAssetHistoryRecord: (String) -> Unit = {},
    onAssetSummaryCopied: () -> Unit = {},
    onGenerateFinanceNewsDigest: () -> Unit = {},
    onToggleWatchlistNtfy: (Boolean) -> Unit = {},
    onFillAssetStatsFromImages: () -> Unit = {},
    initialSection: TopSection = TopSection.FINANCE,
    enableLifecycleAutoRefresh: Boolean = true,
    enableFinanceAutoRefresh: Boolean = true,
    financeAutoRefreshIntervalMs: Long = 90_000L,
    enableCyclicTabs: Boolean = true,
    animateTabSwitch: Boolean = true,
) {
    val lifecycleOwner = LocalLifecycleOwner.current
    var selectedSection by remember { mutableStateOf(initialSection) }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (enableLifecycleAutoRefresh && event == Lifecycle.Event.ON_RESUME) {
                onAppForeground()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    LaunchedEffect(selectedSection, enableFinanceAutoRefresh, financeAutoRefreshIntervalMs) {
        if (!enableFinanceAutoRefresh || selectedSection != TopSection.FINANCE) {
            return@LaunchedEffect
        }
        while (true) {
            delay(financeAutoRefreshIntervalMs)
            onRefreshFinanceSignals()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        Color(0xFF091629),
                        Color(0xFF10304A),
                        Color(0xFF15465B),
                    )
                )
            ),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(Color(0x5535B6F8), Color.Transparent),
                        center = Offset(880f, 120f),
                        radius = 900f,
                    )
                ),
        )
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(Color(0x4476C8A4), Color.Transparent),
                        center = Offset(80f, 1600f),
                        radius = 980f,
                    )
                ),
        )

        Scaffold(
            containerColor = Color.Transparent,
            contentColor = MaterialTheme.colorScheme.onBackground,
            topBar = {
                Column(
                    modifier = Modifier
                        .statusBarsPadding()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        text = "Midas",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = when (selectedSection) {
                            TopSection.BILIBILI -> "B 站视频总结与任务回看"
                            TopSection.XHS -> "小红书单链接总结与结果保存"
                            TopSection.NOTES -> "统一笔记库、搜索与合并"
                            TopSection.FINANCE -> "Watchlist、新闻摘要与资产统计"
                            TopSection.SETTINGS -> "服务端连接、令牌与运行配置"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    GlassTabBar(
                        selectedTabIndex = selectedSection.ordinal,
                        labels = TopSection.entries.map { it.title },
                        onSelect = { index ->
                            selectedSection = TopSection.entries[index]
                            if (selectedSection == TopSection.FINANCE) {
                                onRefreshFinanceSignals()
                                onRefreshAssetStats()
                            }
                        },
                    )
                }
            },
        ) { innerPadding ->
            val contentModifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp)

            when (selectedSection) {
                TopSection.FINANCE -> FinanceSignalsPanel(
                    state = finance,
                    onRefresh = {
                        onRefreshFinanceSignals()
                        onRefreshAssetStats()
                    },
                    onAssetAmountChange = onAssetAmountChange,
                    onSaveAssetStats = onSaveAssetStats,
                    onDeleteAssetHistoryRecord = onDeleteAssetHistoryRecord,
                    onAssetSummaryCopied = onAssetSummaryCopied,
                    onGenerateFinanceNewsDigest = onGenerateFinanceNewsDigest,
                    onToggleWatchlistNtfy = onToggleWatchlistNtfy,
                    onFillAssetStatsFromImages = onFillAssetStatsFromImages,
                    modifier = contentModifier,
                )

                TopSection.SETTINGS -> SettingsPanel(
                    state = settings,
                    onBaseUrlChange = onBaseUrlChange,
                    onAccessTokenChange = onAccessTokenChange,
                    onSave = onSaveBaseUrl,
                    onTestConnection = onTestConnection,
                    onConfigTextChange = onConfigTextChange,
                    onConfigBooleanChange = onConfigBooleanChange,
                    onResetConfig = onResetConfig,
                    modifier = contentModifier,
                )

                TopSection.NOTES -> NotesPanel(
                    state = notes,
                    onKeywordChange = onNotesKeywordChange,
                    onSourceFilterChange = onNotesSourceFilterChange,
                    onDateWindowChange = onNotesDateWindowChange,
                    onMergedFilterChange = onNotesMergedFilterChange,
                    onSortChange = onNotesSortChange,
                    onRefresh = onRefreshNotes,
                    onLoadRelatedNotes = onLoadRelatedNotes,
                    onDeleteBilibili = onDeleteBilibiliNote,
                    onClearBilibili = onClearBilibiliNotes,
                    onDeleteXiaohongshu = onDeleteXiaohongshuNote,
                    onClearXiaohongshu = onClearXiaohongshuNotes,
                    onSuggestMergeCandidates = onSuggestMergeCandidates,
                    onPreviewMergeCandidate = onPreviewMergeCandidate,
                    onCommitCurrentMerge = onCommitCurrentMerge,
                    onRollbackLastMerge = onRollbackLastMerge,
                    onFinalizeLastMerge = onFinalizeLastMerge,
                    modifier = contentModifier,
                )

                TopSection.BILIBILI -> BilibiliPanel(
                    state = bilibili,
                    onVideoUrlChange = onBilibiliVideoUrlChange,
                    onSubmit = onSubmitBilibiliSummary,
                    onSaveNote = onSaveBilibiliNote,
                    onRefreshJobs = onRefreshBilibiliJobs,
                    onOpenJob = onOpenBilibiliJob,
                    onRetryJob = onRetryBilibiliJob,
                    modifier = contentModifier,
                )

                TopSection.XHS -> XiaohongshuPanel(
                    state = xiaohongshu,
                    onUrlChange = onXiaohongshuUrlChange,
                    onSummarizeUrl = onSummarizeXiaohongshuUrl,
                    onRefreshAuthConfig = onRefreshXiaohongshuAuthConfig,
                    onSaveSingleNote = onSaveSingleXiaohongshuNote,
                    onRefreshJobs = onRefreshXiaohongshuJobs,
                    onOpenJob = onOpenXiaohongshuJob,
                    onRetryJob = onRetryXiaohongshuJob,
                    modifier = contentModifier,
                )
            }
        }
    }
}

@Composable
internal fun GlassTabBar(
    selectedTabIndex: Int,
    labels: List<String>,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.46f),
                shape = RoundedCornerShape(20.dp),
            )
            .padding(3.dp),
    ) {
        if (labels.size > WrappedTabThreshold) {
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("glass_tab_bar_scroll"),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                contentPadding = PaddingValues(horizontal = 2.dp),
            ) {
                itemsIndexed(labels) { index, label ->
                    GlassTabChip(
                        label = label,
                        selected = selectedTabIndex == index,
                        onClick = { onSelect(index) },
                        modifier = Modifier.widthIn(min = 104.dp),
                    )
                }
            }
        } else {
            TabRow(
                selectedTabIndex = selectedTabIndex,
                containerColor = Color.Transparent,
                divider = {},
                indicator = { tabPositions ->
                    TabRowDefaults.SecondaryIndicator(
                        modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTabIndex]),
                        height = 2.dp,
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.95f),
                    )
                },
            ) {
                labels.forEachIndexed { index, label ->
                    Tab(
                        selected = selectedTabIndex == index,
                        onClick = { onSelect(index) },
                        selectedContentColor = MaterialTheme.colorScheme.onSurface,
                        unselectedContentColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.76f),
                        text = { SingleLineActionText(label) },
                    )
                }
            }
        }
    }
}

@Composable
private fun GlassTabChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val containerColor = if (selected) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.18f)
    } else {
        MaterialTheme.colorScheme.surface.copy(alpha = 0.18f)
    }
    val borderColor = if (selected) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.72f)
    } else {
        MaterialTheme.colorScheme.outline.copy(alpha = 0.34f)
    }
    val textColor = if (selected) {
        MaterialTheme.colorScheme.onSurface
    } else {
        MaterialTheme.colorScheme.onSurface.copy(alpha = 0.82f)
    }

    Box(
        modifier = modifier
            .defaultMinSize(minHeight = 42.dp)
            .border(width = 1.dp, color = borderColor, shape = RoundedCornerShape(16.dp))
            .background(color = containerColor, shape = RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
            color = textColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
internal fun GlassCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.58f),
            contentColor = MaterialTheme.colorScheme.onSurface,
        ),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.45f),
        ),
    ) {
        content()
    }
}

@Composable
internal fun MidasButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    tone: ButtonTone = ButtonTone.PRIMARY,
    content: @Composable RowScope.() -> Unit,
) {
    val colors = when (tone) {
        ButtonTone.PRIMARY -> ButtonDefaults.buttonColors(
            containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.92f),
            contentColor = Color(0xFFF1F8FF),
            disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
            disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.72f),
        )

        ButtonTone.SUCCESS -> ButtonDefaults.buttonColors(
            containerColor = Color(0xFF1F8668),
            contentColor = Color(0xFFEFFEF7),
            disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
            disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.72f),
        )

        ButtonTone.NEUTRAL -> ButtonDefaults.buttonColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.82f),
            contentColor = MaterialTheme.colorScheme.onSurface,
            disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
            disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.72f),
        )
    }

    Button(
        onClick = onClick,
        modifier = modifier,
        enabled = enabled,
        shape = RoundedCornerShape(14.dp),
        colors = colors,
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.42f),
        ),
        elevation = ButtonDefaults.buttonElevation(
            defaultElevation = 5.dp,
            pressedElevation = 1.dp,
            disabledElevation = 0.dp,
        ),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp),
        content = content,
    )
}

@Composable
internal fun SingleLineActionText(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        maxLines = 1,
        softWrap = false,
        overflow = TextOverflow.Ellipsis,
    )
}
