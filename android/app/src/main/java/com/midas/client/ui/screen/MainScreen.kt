package com.midas.client.ui.screen

import android.content.ClipData
import android.content.ClipboardManager
import android.net.Uri
import android.content.Intent
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.BorderStroke
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.midas.client.data.model.AsyncJobListItemData
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.FinanceFocusCard
import com.midas.client.data.model.FinanceNewsItem
import com.midas.client.data.model.FinanceWatchlistItem
import com.midas.client.data.model.NotesMergeCandidateItem
import com.midas.client.data.model.NotesMergePreviewData
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.ui.components.MarkdownText
import com.midas.client.util.ConfigFieldType
import com.midas.client.util.EditableConfigField
import kotlinx.coroutines.delay
import java.util.Locale

enum class TopSection(val title: String) {
    BILIBILI("B站"),
    XHS("小红书"),
    NOTES("笔记"),
    FINANCE("资产"),
    SETTINGS("设置"),
}

private enum class AssetPanelTab(val title: String) {
    MARKET("市场信号"),
    ASSET_STATS("资产总览"),
}

private enum class ConfigControlKind {
    TEXT,
    SWITCH,
    DROPDOWN,
}

private enum class ButtonTone {
    PRIMARY,
    SUCCESS,
    NEUTRAL,
}

private const val XIAOHONGSHU_SUMMARY_JOB_TYPE = "xiaohongshu_summarize_url"
private val SuccessStatusColor = Color(0xFF7BE5A6)
private val ErrorStatusColor = Color(0xFFFF9A9A)
private val WarningStatusColor = Color(0xFFFFD187)
private val LinkStatusColor = Color(0xFF8ED8FF)

private data class ConfigOption(
    val value: String,
    val label: String,
)

private data class ConfigFieldSpec(
    val path: String,
    val section: String,
    val title: String,
    val description: String,
    val defaultValue: String,
    val control: ConfigControlKind,
    val options: List<ConfigOption> = emptyList(),
)

private val configFieldSpecs = listOf(
    ConfigFieldSpec(
        path = "llm.model",
        section = "总结能力",
        title = "LLM 模型",
        description = "填写服务端可用模型名，例如 gemini-3-flash-preview。",
        defaultValue = "gemini-3-flash-preview",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "llm.timeout_seconds",
        section = "总结能力",
        title = "LLM 超时（秒）",
        description = "单次模型请求最长等待时间。",
        defaultValue = "120",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "asr.mode",
        section = "总结能力",
        title = "视频转写模式",
        description = "固定使用真实转写模式。",
        defaultValue = "faster_whisper",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "faster_whisper", label = "真实转写（faster_whisper）"),
        ),
    ),
    ConfigFieldSpec(
        path = "asr.model_size",
        section = "总结能力",
        title = "Whisper 模型大小",
        description = "模型越大通常越准，但速度更慢、占用更高。",
        defaultValue = "base",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "tiny", label = "tiny（最快）"),
            ConfigOption(value = "base", label = "base（默认）"),
            ConfigOption(value = "small", label = "small"),
            ConfigOption(value = "medium", label = "medium"),
            ConfigOption(value = "large-v3", label = "large-v3（最强）"),
        ),
    ),
    ConfigFieldSpec(
        path = "asr.device",
        section = "总结能力",
        title = "ASR 设备",
        description = "无 GPU 建议用 cpu；有 CUDA 环境可选 cuda。",
        defaultValue = "cpu",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "cpu", label = "CPU"),
            ConfigOption(value = "cuda", label = "CUDA"),
        ),
    ),
    ConfigFieldSpec(
        path = "asr.language",
        section = "总结能力",
        title = "转写语言",
        description = "当前仅支持中文或英文。",
        defaultValue = "zh",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "zh", label = "中文（zh）"),
            ConfigOption(value = "en", label = "英文（en）"),
        ),
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.mode",
        section = "小红书单篇",
        title = "单篇模式",
        description = "固定使用 web_readonly 单篇模式。",
        defaultValue = "web_readonly",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "web_readonly", label = "web_readonly"),
        ),
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.request_timeout_seconds",
        section = "小红书单篇",
        title = "单篇请求超时（秒）",
        description = "单篇总结请求小红书上游的超时时间。",
        defaultValue = "30",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.web_readonly.detail_fetch_mode",
        section = "小红书单篇",
        title = "单篇详情抓取策略",
        description = "auto=按需抓，always=总是抓，never=不抓详情。",
        defaultValue = "auto",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "auto", label = "按需抓取（auto）"),
            ConfigOption(value = "always", label = "总是抓取（always）"),
            ConfigOption(value = "never", label = "不抓详情（never）"),
        ),
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.web_readonly.max_images_per_note",
        section = "小红书单篇",
        title = "单篇最多读取图片数",
        description = "总结单篇时最多读取的图片数量。",
        defaultValue = "32",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.min_live_sync_interval_seconds",
        section = "小红书同步",
        title = "两次同步笔记最大间隔（秒）",
        description = "控制两次同步任务的间隔阈值，默认 120 秒。",
        defaultValue = "120",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "runtime.log_level",
        section = "运行与调试",
        title = "日志级别",
        description = "排查问题建议临时切到 DEBUG，平时建议 INFO。",
        defaultValue = "INFO",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "DEBUG", label = "DEBUG"),
            ConfigOption(value = "INFO", label = "INFO"),
            ConfigOption(value = "WARNING", label = "WARNING"),
            ConfigOption(value = "ERROR", label = "ERROR"),
        ),
    ),
    ConfigFieldSpec(
        path = "bilibili.max_video_minutes",
        section = "运行与调试",
        title = "B 站视频时长上限（分钟）",
        description = "超过该时长的视频将被拒绝处理。",
        defaultValue = "240",
        control = ConfigControlKind.TEXT,
    ),
)

@Composable
fun MainScreen(viewModel: MainViewModel) {
    val settings by viewModel.settingsState.collectAsStateWithLifecycle()
    val bilibili by viewModel.bilibiliState.collectAsStateWithLifecycle()
    val xiaohongshu by viewModel.xiaohongshuState.collectAsStateWithLifecycle()
    val notes by viewModel.notesState.collectAsStateWithLifecycle()
    val finance by viewModel.financeState.collectAsStateWithLifecycle()
    val assetImagePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents(),
        onResult = { uris -> viewModel.onAssetImagesSelected(uris) },
    )

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
        onRefreshNotes = viewModel::loadSavedNotes,
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
        onAssetAmountChange = viewModel::onAssetAmountInputChange,
        onSaveAssetStats = viewModel::saveAssetStats,
        onDeleteAssetHistoryRecord = viewModel::deleteAssetHistoryRecord,
        onAssetSummaryCopied = viewModel::markAssetSummaryCopied,
        onGenerateFinanceNewsDigest = viewModel::generateFinanceNewsDigest,
        onToggleWatchlistNtfy = viewModel::setWatchlistNtfyEnabled,
        onDismissFinanceFocusCard = viewModel::dismissFinanceFocusCard,
        onRestoreFinanceFocusCards = viewModel::restoreDismissedFinanceFocusCards,
        onFillAssetStatsFromImages = { assetImagePickerLauncher.launch("image/*") },
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
    onRefreshNotes: () -> Unit,
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
    onAssetAmountChange: (String, String) -> Unit = { _, _ -> },
    onSaveAssetStats: () -> Unit = {},
    onDeleteAssetHistoryRecord: (String) -> Unit = {},
    onAssetSummaryCopied: () -> Unit = {},
    onGenerateFinanceNewsDigest: () -> Unit = {},
    onToggleWatchlistNtfy: (Boolean) -> Unit = {},
    onDismissFinanceFocusCard: (FinanceFocusCard) -> Unit = {},
    onRestoreFinanceFocusCards: () -> Unit = {},
    onFillAssetStatsFromImages: () -> Unit = {},
    initialSection: TopSection = TopSection.BILIBILI,
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
                            TopSection.FINANCE -> "先看建议，再决定要不要展开细节"
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
                            when (selectedSection) {
                                TopSection.FINANCE -> onRefreshFinanceSignals()
                                else -> Unit
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
                    onRefresh = onRefreshFinanceSignals,
                    onAssetAmountChange = onAssetAmountChange,
                    onSaveAssetStats = onSaveAssetStats,
                    onDeleteAssetHistoryRecord = onDeleteAssetHistoryRecord,
                    onAssetSummaryCopied = onAssetSummaryCopied,
                    onGenerateFinanceNewsDigest = onGenerateFinanceNewsDigest,
                    onToggleWatchlistNtfy = onToggleWatchlistNtfy,
                    onDismissFocusCard = onDismissFinanceFocusCard,
                    onRestoreFocusCards = onRestoreFinanceFocusCards,
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
                    onRefresh = onRefreshNotes,
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
private fun GlassTabBar(
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

@Composable
private fun GlassCard(
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
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.45f)),
    ) {
        content()
    }
}

@Composable
private fun MidasButton(
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
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.42f)),
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
private fun SingleLineActionText(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        maxLines = 1,
        softWrap = false,
        overflow = TextOverflow.Ellipsis,
    )
}

@Composable
private fun SettingsPanel(
    state: SettingsUiState,
    onBaseUrlChange: (String) -> Unit,
    onAccessTokenChange: (String) -> Unit,
    onSave: () -> Unit,
    onTestConnection: () -> Unit,
    onConfigTextChange: (String, String) -> Unit,
    onConfigBooleanChange: (String, Boolean) -> Unit,
    onResetConfig: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("服务端设置", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = state.baseUrlInput,
            onValueChange = onBaseUrlChange,
            label = { Text("服务端地址（如 http://100.98.44.5:8000/）") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        OutlinedTextField(
            value = state.accessTokenInput,
            onValueChange = onAccessTokenChange,
            label = { Text("访问令牌（可选）") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MidasButton(onClick = onSave) {
                SingleLineActionText("保存")
            }
            MidasButton(
                onClick = onTestConnection,
                enabled = !state.isTesting,
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText(if (state.isTesting) "测试中..." else "连接测试")
            }
        }
        if (state.saveStatus.isNotBlank()) {
            Text(text = state.saveStatus, color = SuccessStatusColor)
        }
        if (state.testStatus.isNotBlank()) {
            Text(text = state.testStatus)
        }

        HorizontalDivider()
        Text("运行配置", style = MaterialTheme.typography.titleSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MidasButton(
                onClick = onResetConfig,
                enabled = !state.isConfigResetting,
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText(if (state.isConfigResetting) "恢复中..." else "恢复默认")
            }
            if (state.isConfigSaving) {
                Text("自动保存中...", style = MaterialTheme.typography.bodySmall)
            }
        }
        if (state.isConfigLoading) {
            Text("正在拉取配置...", style = MaterialTheme.typography.bodySmall)
        }
        EditableConfigFieldsPanel(
            fields = state.editableConfigFields,
            fieldErrors = state.configFieldErrors,
            onTextChange = onConfigTextChange,
            onBooleanChange = onConfigBooleanChange,
        )
        if (state.configStatus.isNotBlank()) {
            val statusColor = if (state.configFieldErrors.isNotEmpty()) {
                ErrorStatusColor
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            }
            Text(text = state.configStatus, color = statusColor)
        }
    }
}

@Composable
private fun EditableConfigFieldsPanel(
    fields: List<EditableConfigField>,
    fieldErrors: Map<String, String>,
    onTextChange: (String, String) -> Unit,
    onBooleanChange: (String, Boolean) -> Unit,
) {
    val fieldByPath = fields.associateBy { it.path }
    val visibleFields = configFieldSpecs.mapNotNull { spec ->
        fieldByPath[spec.path]?.let { field -> spec to field }
    }

    if (visibleFields.isEmpty()) {
        Text(
            text = "当前没有可展示的配置项，请检查服务端连接后重试。",
            style = MaterialTheme.typography.bodySmall,
        )
        return
    }

    val groups = visibleFields.groupBy { (spec, _) -> spec.section }
    groups.forEach { (sectionName, sectionFields) ->
        Text(
            text = sectionName,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        sectionFields.forEach { (spec, field) ->
            ConfigFieldEditor(
                spec = spec,
                field = field,
                errorMessage = fieldErrors[spec.path],
                onTextChange = onTextChange,
                onBooleanChange = onBooleanChange,
            )
        }
        HorizontalDivider()
    }
}

@Composable
private fun ConfigFieldEditor(
    spec: ConfigFieldSpec,
    field: EditableConfigField,
    errorMessage: String?,
    onTextChange: (String, String) -> Unit,
    onBooleanChange: (String, Boolean) -> Unit,
) {
    val hasError = !errorMessage.isNullOrBlank()
    val isCustomized = isConfigFieldCustomized(spec = spec, field = field)
    val indicatorText = when {
        hasError -> "格式错误"
        isCustomized -> "已修改"
        else -> "默认"
    }
    val indicatorColor = when {
        hasError -> ErrorStatusColor
        isCustomized -> SuccessStatusColor
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    val containerColor = when {
        hasError -> Color(0xFF4A1F2A)
        isCustomized -> Color(0xFF1D3D2F)
        else -> MaterialTheme.colorScheme.surface
    }
    val borderColor = when {
        hasError -> ErrorStatusColor.copy(alpha = 0.85f)
        isCustomized -> SuccessStatusColor.copy(alpha = 0.85f)
        else -> MaterialTheme.colorScheme.outline.copy(alpha = 0.45f)
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        colors = CardDefaults.cardColors(
            containerColor = containerColor,
            contentColor = MaterialTheme.colorScheme.onSurface,
        ),
        border = BorderStroke(1.dp, borderColor),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(text = spec.title, fontWeight = FontWeight.SemiBold)
                Text(
                    text = indicatorText,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    color = indicatorColor,
                )
            }
            Text(
                text = spec.description,
                style = MaterialTheme.typography.bodySmall,
            )
            if (isCustomized) {
                Text(
                    text = "默认值：${spec.defaultDisplayText()}",
                    style = MaterialTheme.typography.bodySmall,
                    color = SuccessStatusColor,
                )
            }

            when (spec.control) {
                ConfigControlKind.SWITCH -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(
                            text = if (field.boolValue) "当前：开启" else "当前：关闭",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Switch(
                            checked = field.boolValue,
                            onCheckedChange = { checked ->
                                onBooleanChange(spec.path, checked)
                            },
                        )
                    }
                }

                ConfigControlKind.DROPDOWN -> {
                    ConfigDropdownField(
                        path = spec.path,
                        options = spec.options,
                        currentValue = field.textValue,
                        isError = hasError,
                        onSelect = { selected ->
                            onTextChange(spec.path, selected)
                        },
                    )
                }

                ConfigControlKind.TEXT -> {
                    val isList = field.type == ConfigFieldType.LIST_JSON
                    OutlinedTextField(
                        value = field.textValue,
                        onValueChange = { value ->
                            onTextChange(spec.path, value)
                        },
                        isError = hasError,
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = !isList,
                        minLines = if (isList) 2 else 1,
                    )
                }
            }
            if (hasError) {
                Text(
                    text = errorMessage ?: "字段格式错误。",
                    style = MaterialTheme.typography.bodySmall,
                    color = ErrorStatusColor,
                )
            }
        }
    }
}

@Composable
private fun ConfigDropdownField(
    path: String,
    options: List<ConfigOption>,
    currentValue: String,
    isError: Boolean,
    onSelect: (String) -> Unit,
) {
    var expanded by remember(path) { mutableStateOf(false) }
    val matched = options.firstOrNull { option -> option.value == currentValue }
    val selectedLabel = matched?.label ?: if (currentValue.isNotBlank()) "当前值：$currentValue" else "请选择"

    Box(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = selectedLabel,
            onValueChange = {},
            readOnly = true,
            isError = isError,
            trailingIcon = { Text("▼") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .clickable { expanded = true },
        )
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(option.label) },
                    onClick = {
                        onSelect(option.value)
                        expanded = false
                    },
                )
            }
        }
    }
}

private fun isConfigFieldCustomized(spec: ConfigFieldSpec, field: EditableConfigField): Boolean {
    val expected = spec.defaultValue.trim()
    return when (spec.control) {
        ConfigControlKind.SWITCH -> {
            val expectedBool = expected.equals("true", ignoreCase = true)
            field.boolValue != expectedBool
        }

        ConfigControlKind.DROPDOWN -> field.textValue.trim() != expected
        ConfigControlKind.TEXT -> {
            val actual = field.textValue.trim()
            when (field.type) {
                ConfigFieldType.INTEGER -> {
                    val actualInt = actual.toLongOrNull()
                    val expectedInt = expected.toLongOrNull()
                    if (actualInt != null && expectedInt != null) {
                        actualInt != expectedInt
                    } else {
                        actual != expected
                    }
                }

                ConfigFieldType.DECIMAL -> {
                    val actualDec = actual.toDoubleOrNull()
                    val expectedDec = expected.toDoubleOrNull()
                    if (actualDec != null && expectedDec != null) {
                        actualDec != expectedDec
                    } else {
                        actual != expected
                    }
                }

                else -> actual != expected
            }
        }
    }
}

private fun ConfigFieldSpec.defaultDisplayText(): String {
    if (control == ConfigControlKind.SWITCH) {
        return if (defaultValue.equals("true", ignoreCase = true)) "开启" else "关闭"
    }
    val dropdownLabel = options.firstOrNull { it.value == defaultValue }?.label
    if (dropdownLabel != null) {
        return dropdownLabel
    }
    return if (defaultValue.isBlank()) "空" else defaultValue
}

@Composable
private fun BilibiliPanel(
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
private fun XiaohongshuPanel(
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
                            if (state.currentJobType == XIAOHONGSHU_SUMMARY_JOB_TYPE && state.isSummarizingUrl) {
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
                        }
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

@Composable
private fun AsyncJobHistoryCard(
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

private fun asyncJobTypeLabel(jobType: String): String {
    return when (jobType.trim().lowercase(Locale.ROOT)) {
        "bilibili_summarize" -> "B站总结"
        "xiaohongshu_summarize_url" -> "小红书单篇"
        else -> "后台任务"
    }
}

private fun asyncJobStatusLabel(status: String): String {
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

@Composable
private fun FinanceSignalsPanel(
    state: FinanceSignalsUiState,
    onRefresh: () -> Unit,
    onAssetAmountChange: (String, String) -> Unit,
    onSaveAssetStats: () -> Unit,
    onDeleteAssetHistoryRecord: (String) -> Unit,
    onAssetSummaryCopied: () -> Unit,
    onGenerateFinanceNewsDigest: () -> Unit,
    onToggleWatchlistNtfy: (Boolean) -> Unit,
    onDismissFocusCard: (FinanceFocusCard) -> Unit,
    onRestoreFocusCards: () -> Unit,
    onFillAssetStatsFromImages: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var selectedAssetTab by remember { mutableStateOf(AssetPanelTab.MARKET) }
    var showAllNews by remember { mutableStateOf(false) }

    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("资产系统", style = MaterialTheme.typography.titleMedium)
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

        if (selectedAssetTab == AssetPanelTab.MARKET) {
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

@Composable
private fun FinanceFocusCardList(
    items: List<FinanceFocusCard>,
    onDismiss: (FinanceFocusCard) -> Unit,
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
                SingleLineActionText("已处理")
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
        if (item.reasons.isNotEmpty()) {
            Text(
                text = "触发原因：${item.reasons.joinToString(" / ") { financeReasonLabel(it) }}",
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
                            if (showHistory) {
                                "收起历史记录"
                            } else {
                                "查看历史记录（${state.assetHistory.size}）"
                            },
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
                            onValueChange = { value ->
                                onAssetAmountChange(draft.key, value)
                            },
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
                DropdownMenu(
                    expanded = menuExpanded,
                    onDismissRequest = { menuExpanded = false },
                ) {
                    DropdownMenuItem(
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
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
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

@Composable
@Suppress("UNUSED_PARAMETER")
private fun NotesPanel(
    state: NotesUiState,
    onKeywordChange: (String) -> Unit,
    onRefresh: () -> Unit,
    onDeleteBilibili: (String) -> Unit,
    onClearBilibili: () -> Unit,
    onDeleteXiaohongshu: (String) -> Unit,
    onClearXiaohongshu: () -> Unit,
    onSuggestMergeCandidates: () -> Unit,
    onPreviewMergeCandidate: (NotesMergeCandidateItem) -> Unit,
    onCommitCurrentMerge: () -> Unit,
    onRollbackLastMerge: () -> Unit,
    onFinalizeLastMerge: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var selectedDetail by remember { mutableStateOf<NoteDetailViewState?>(null) }
    var selectedMergeCandidate by remember { mutableStateOf<NotesMergeCandidateItem?>(null) }
    val scrollState = rememberScrollState()
    val context = LocalContext.current
    val keyword = state.keywordInput.trim()
    val filteredBilibili = state.bilibiliNotes.filter { item ->
        keyword.isBlank() ||
            item.title.contains(keyword, ignoreCase = true) ||
            item.summaryMarkdown.contains(keyword, ignoreCase = true)
    }
    val filteredXhs = state.xiaohongshuNotes.filter { item ->
        keyword.isBlank() ||
            item.title.contains(keyword, ignoreCase = true) ||
            item.summaryMarkdown.contains(keyword, ignoreCase = true)
    }

    LaunchedEffect(selectedDetail, selectedMergeCandidate) {
        if (selectedDetail != null || selectedMergeCandidate != null) {
            scrollState.scrollTo(0)
        }
    }

    Column(
        modifier = modifier.verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        BackHandler(enabled = selectedDetail != null) {
            selectedDetail = null
        }
        BackHandler(enabled = selectedMergeCandidate != null) {
            selectedMergeCandidate = null
        }

        if (selectedDetail != null) {
            NoteDetailPanel(
                detail = selectedDetail!!,
                onOpenSourceUrl = { sourceUrl ->
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(sourceUrl))
                    context.startActivity(intent)
                },
            )
            return@Column
        }

        if (selectedMergeCandidate != null) {
            MergePreviewPanel(
                candidate = selectedMergeCandidate!!,
                preview = state.mergePreview,
                isPreviewLoading = state.isMergePreviewLoading,
                isConfirmingMerge = state.isMergeCommitting || state.isMergeFinalizing,
                onConfirmMerge = {
                    onCommitCurrentMerge()
                    selectedMergeCandidate = null
                },
            )
            return@Column
        }

        Text("已保存笔记", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = state.keywordInput,
            onValueChange = onKeywordChange,
            label = { Text("关键词检索（标题+内容）") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MidasButton(
                onClick = onRefresh,
                enabled = !state.isLoading,
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText(if (state.isLoading) "刷新中..." else "刷新笔记库")
            }
            MidasButton(
                onClick = onSuggestMergeCandidates,
                enabled = !state.isMergeSuggesting && !state.isMergeCommitting,
            ) {
                SingleLineActionText(if (state.isMergeSuggesting) "分析中..." else "合并笔记")
            }
        }

        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = ErrorStatusColor)
        }
        if (state.actionStatus.isNotBlank()) {
            Text(text = state.actionStatus, color = SuccessStatusColor)
        }
        if (state.mergeStatus.isNotBlank()) {
            Text(text = state.mergeStatus, color = SuccessStatusColor)
        }

        if (state.mergeCandidates.isNotEmpty()) {
            Text(
                text = "智能合并候选（${state.mergeCandidates.size}）",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            state.mergeCandidates.forEach { item ->
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = (
                                "来源：${if (item.source == "bilibili") "B站" else "小红书"}  "
                                    + "相似度：${"%.2f".format(item.score)}  "
                                    + "相关级别：${if (item.relationLevel == "STRONG") "强相关" else "弱相关"}"
                                ),
                            style = MaterialTheme.typography.bodySmall,
                        )
                        item.notes.forEach { note ->
                            Text(
                                text = "• ${note.title} (${note.noteId})",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        MidasButton(
                            onClick = {
                                selectedMergeCandidate = item
                                onPreviewMergeCandidate(item)
                            },
                            enabled = !state.isMergePreviewLoading,
                            tone = ButtonTone.NEUTRAL,
                        ) {
                            SingleLineActionText(if (state.isMergePreviewLoading) "预览中..." else "预览合并")
                        }
                    }
                }
            }
        }

        Text(
            text = "B站笔记（${filteredBilibili.size}/${state.bilibiliNotes.size}）",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        if (state.bilibiliNotes.isNotEmpty()) {
            MidasButton(
                onClick = onClearBilibili,
                enabled = !state.isLoading,
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText("清空 B站")
            }
        }
        if (filteredBilibili.isEmpty()) {
            Text("暂无 B 站已保存笔记。", style = MaterialTheme.typography.bodySmall)
        }
        filteredBilibili.forEach { item ->
            SavedNoteListItem(
                title = item.title,
                savedAt = item.savedAt,
                openTag = "saved_note_open_${item.noteId}",
                onOpen = { selectedDetail = NoteDetailViewState.Bilibili(item) },
                onDelete = { onDeleteBilibili(item.noteId) },
            )
        }

        Text(
            text = "小红书笔记（${filteredXhs.size}/${state.xiaohongshuNotes.size}）",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        if (state.xiaohongshuNotes.isNotEmpty()) {
            MidasButton(
                onClick = onClearXiaohongshu,
                enabled = !state.isLoading,
                tone = ButtonTone.NEUTRAL,
            ) {
                SingleLineActionText("清空 小红书")
            }
        }
        if (filteredXhs.isEmpty()) {
            Text("暂无小红书已保存笔记。", style = MaterialTheme.typography.bodySmall)
        }
        filteredXhs.forEach { item ->
            SavedNoteListItem(
                title = item.title,
                savedAt = item.savedAt,
                openTag = "saved_note_open_${item.noteId}",
                onOpen = { selectedDetail = NoteDetailViewState.Xiaohongshu(item) },
                onDelete = { onDeleteXiaohongshu(item.noteId) },
            )
        }
    }
}

@Composable
private fun MergePreviewPanel(
    candidate: NotesMergeCandidateItem,
    preview: NotesMergePreviewData?,
    isPreviewLoading: Boolean,
    isConfirmingMerge: Boolean,
    onConfirmMerge: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("合并预览", style = MaterialTheme.typography.titleSmall)
                Text(
                    text = (
                        "来源：${if (candidate.source == "bilibili") "B站" else "小红书"}  "
                            + "相似度：${"%.2f".format(candidate.score)}  "
                            + "相关级别：${if (candidate.relationLevel == "STRONG") "强相关" else "弱相关"}"
                        ),
                    style = MaterialTheme.typography.bodySmall,
                )
                candidate.notes.forEach { note ->
                    Text(
                        text = "• ${note.title} (${note.noteId})",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                HorizontalDivider()
                when {
                    isPreviewLoading -> {
                        Text("正在生成合并预览...", style = MaterialTheme.typography.bodySmall)
                    }

                    preview != null -> {
                        Text("标题：${preview.mergedTitle}", style = MaterialTheme.typography.bodySmall)
                        if (preview.conflictMarkers.isNotEmpty()) {
                            Text(
                                text = "冲突标记：${preview.conflictMarkers.joinToString("、")}",
                                style = MaterialTheme.typography.bodySmall,
                                color = WarningStatusColor,
                            )
                        }
                        MarkdownText(
                            markdown = preview.mergedSummaryMarkdown,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            MidasButton(
                                onClick = onConfirmMerge,
                                enabled = !isConfirmingMerge,
                                tone = ButtonTone.SUCCESS,
                            ) {
                                SingleLineActionText(
                                    if (isConfirmingMerge) "处理中..." else "确认合并并删除原笔记",
                                )
                            }
                        }
                    }

                    else -> {
                        Text("预览加载失败，请返回重试。", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun SavedNoteListItem(
    title: String,
    savedAt: String,
    openTag: String = "",
    onOpen: () -> Unit,
    onDelete: () -> Unit,
) {
    var menuExpanded by remember(title, savedAt) { mutableStateOf(false) }

    GlassCard(
        modifier = Modifier
            .fillMaxWidth()
            .then(if (openTag.isBlank()) Modifier else Modifier.testTag(openTag))
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
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text("保存时间：$savedAt", style = MaterialTheme.typography.bodySmall)
            }
            Box {
                IconButton(onClick = { menuExpanded = true }) {
                    Text("⋮")
                }
                DropdownMenu(
                    expanded = menuExpanded,
                    onDismissRequest = { menuExpanded = false },
                ) {
                    DropdownMenuItem(
                        text = { Text("删除") },
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

private sealed interface NoteDetailViewState {
    data class Bilibili(val note: BilibiliSavedNote) : NoteDetailViewState
    data class Xiaohongshu(val note: XiaohongshuSavedNote) : NoteDetailViewState
}

private fun isMergeNoteId(noteId: String): Boolean {
    return noteId.trim().startsWith("merged_note_")
}

@Composable
private fun NoteDetailPanel(
    detail: NoteDetailViewState,
    onOpenSourceUrl: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        GlassCard(modifier = Modifier.fillMaxWidth()) {
            when (detail) {
                is NoteDetailViewState.Bilibili -> {
                    BilibiliNoteDetail(note = detail.note, onOpenSourceUrl = onOpenSourceUrl)
                }

                is NoteDetailViewState.Xiaohongshu -> {
                    XiaohongshuNoteDetail(note = detail.note, onOpenSourceUrl = onOpenSourceUrl)
                }
            }
        }
    }
}

@Composable
private fun BilibiliNoteDetail(
    note: BilibiliSavedNote,
    onOpenSourceUrl: (String) -> Unit,
) {
    val isMergeNote = isMergeNoteId(note.noteId)
    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(note.title, style = MaterialTheme.typography.titleSmall)
        Text("保存时间：${note.savedAt}", style = MaterialTheme.typography.bodySmall)
        if (isMergeNote) {
            Text(
                "Merge Note · 来源请见正文末尾链接",
                style = MaterialTheme.typography.bodySmall,
                color = LinkStatusColor,
            )
        } else {
            Text(
                note.videoUrl,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("bili_source_url_detail")
                    .clickable { onOpenSourceUrl(note.videoUrl) },
            )
        }
        HorizontalDivider()
        MarkdownText(markdown = note.summaryMarkdown, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
private fun XiaohongshuNoteDetail(
    note: XiaohongshuSavedNote,
    onOpenSourceUrl: (String) -> Unit,
) {
    val isMergeNote = isMergeNoteId(note.noteId)
    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(note.title, style = MaterialTheme.typography.titleSmall)
        Text("保存时间：${note.savedAt}", style = MaterialTheme.typography.bodySmall)
        if (isMergeNote) {
            Text(
                "Merge Note · 来源请见正文末尾链接",
                style = MaterialTheme.typography.bodySmall,
                color = LinkStatusColor,
            )
        } else {
            Text(
                note.sourceUrl,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("xhs_source_url_detail")
                    .clickable { onOpenSourceUrl(note.sourceUrl) },
            )
        }
        HorizontalDivider()
        MarkdownText(markdown = note.summaryMarkdown, modifier = Modifier.fillMaxWidth())
    }
}
