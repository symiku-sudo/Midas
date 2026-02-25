package com.midas.client.ui.screen

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.BorderStroke
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.ui.components.MarkdownText
import com.midas.client.util.ConfigFieldType
import com.midas.client.util.EditableConfigField

private enum class MainTab(val title: String) {
    BILIBILI("B站总结"),
    XHS("小红书同步"),
    NOTES("笔记库"),
    SETTINGS("设置"),
}

private enum class ConfigControlKind {
    TEXT,
    SWITCH,
    DROPDOWN,
}

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
        section = "小红书同步",
        title = "同步模式",
        description = "固定使用真实同步模式。",
        defaultValue = "web_readonly",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "web_readonly", label = "真实同步（web_readonly）"),
        ),
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.collection_id",
        section = "小红书同步",
        title = "收藏夹 ID",
        description = "真实同步时使用的小红书收藏夹 ID。",
        defaultValue = "",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.default_limit",
        section = "小红书同步",
        title = "默认同步条数",
        description = "未指定 limit 时使用这个值。",
        defaultValue = "20",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.max_limit",
        section = "小红书同步",
        title = "单次最大同步条数",
        description = "客户端可请求的上限，防止单次任务过大。",
        defaultValue = "30",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.random_delay_min_seconds",
        section = "小红书同步",
        title = "请求间最小随机间隔（秒）",
        description = "同一轮同步中，相邻两次请求之间的最小等待时间。",
        defaultValue = "3.0",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.random_delay_max_seconds",
        section = "小红书同步",
        title = "请求间最大随机间隔（秒）",
        description = "同一轮同步中，相邻两次请求之间的最大等待时间。",
        defaultValue = "10.0",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.min_live_sync_interval_seconds",
        section = "小红书同步",
        title = "两次真实同步最小间隔（秒）",
        description = "两次 web_readonly 真实同步任务之间的最短间隔。",
        defaultValue = "1800",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.request_timeout_seconds",
        section = "小红书同步",
        title = "小红书请求超时（秒）",
        description = "单次小红书上游请求的超时时间。",
        defaultValue = "30",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.circuit_breaker_failures",
        section = "小红书同步",
        title = "连续失败熔断阈值",
        description = "连续失败达到该次数时，本次同步任务会中断。",
        defaultValue = "3",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.web_readonly.detail_fetch_mode",
        section = "小红书同步",
        title = "详情抓取策略",
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

    var selectedTab by remember { mutableStateOf(MainTab.BILIBILI) }

    Scaffold(
        topBar = {
            Column {
                Text(
                    text = "Midas Client",
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                )
                TabRow(selectedTabIndex = selectedTab.ordinal) {
                    MainTab.entries.forEach { tab ->
                        Tab(
                            selected = selectedTab == tab,
                            onClick = { selectedTab = tab },
                            text = { Text(tab.title) },
                        )
                    }
                }
            }
        },
    ) { innerPadding ->
        when (selectedTab) {
            MainTab.SETTINGS -> {
                SettingsPanel(
                    state = settings,
                    onBaseUrlChange = viewModel::onBaseUrlInputChange,
                    onSave = viewModel::saveBaseUrl,
                    onTestConnection = viewModel::testConnection,
                    onConfigTextChange = viewModel::onEditableConfigFieldTextChange,
                    onConfigBooleanChange = viewModel::onEditableConfigFieldBooleanChange,
                    onResetConfig = viewModel::resetEditableConfig,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding)
                        .padding(16.dp),
                )
            }

            MainTab.BILIBILI -> {
                BilibiliPanel(
                    state = bilibili,
                    onVideoUrlChange = viewModel::onBilibiliUrlInputChange,
                    onSubmit = viewModel::submitBilibiliSummary,
                    onSaveNote = viewModel::saveCurrentBilibiliResult,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding)
                        .padding(16.dp),
                )
            }

            MainTab.XHS -> {
                XiaohongshuPanel(
                    state = xiaohongshu,
                    onLimitChange = viewModel::onXiaohongshuLimitInputChange,
                    onStartSync = viewModel::startXiaohongshuSync,
                    onSaveNotes = viewModel::saveCurrentXiaohongshuSummaries,
                    onPruneSyncedNoteIds = viewModel::pruneUnsavedXiaohongshuSyncedNotes,
                    onRefreshAuthConfig = viewModel::refreshXiaohongshuAuthConfig,
                    onSaveSingleNote = viewModel::saveSingleXiaohongshuSummary,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding)
                        .padding(16.dp),
                )
            }

            MainTab.NOTES -> {
                NotesPanel(
                    state = notes,
                    onKeywordChange = viewModel::onNotesKeywordInputChange,
                    onRefresh = viewModel::loadSavedNotes,
                    onDeleteBilibili = viewModel::deleteBilibiliSavedNote,
                    onClearBilibili = viewModel::clearBilibiliSavedNotes,
                    onDeleteXiaohongshu = viewModel::deleteXiaohongshuSavedNote,
                    onClearXiaohongshu = viewModel::clearXiaohongshuSavedNotes,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding)
                        .padding(16.dp),
                )
            }
        }
    }
}

@Composable
private fun SettingsPanel(
    state: SettingsUiState,
    onBaseUrlChange: (String) -> Unit,
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
            label = { Text("服务端地址（如 http://192.168.1.5:8000/）") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = onSave) {
                Text("保存")
            }
            Button(onClick = onTestConnection, enabled = !state.isTesting) {
                Text(if (state.isTesting) "测试中..." else "连接测试")
            }
        }
        if (state.saveStatus.isNotBlank()) {
            Text(text = state.saveStatus, color = Color(0xFF2E7D32))
        }
        if (state.testStatus.isNotBlank()) {
            Text(text = state.testStatus)
        }

        HorizontalDivider()
        Text("运行配置", style = MaterialTheme.typography.titleSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = onResetConfig, enabled = !state.isConfigResetting) {
                Text(if (state.isConfigResetting) "恢复中..." else "恢复默认")
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
                Color(0xFFC62828)
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
        hasError -> Color(0xFFC62828)
        isCustomized -> Color(0xFF2E7D32)
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    val containerColor = when {
        hasError -> Color(0xFFFFEBEE)
        isCustomized -> Color(0xFFF1F8E9)
        else -> MaterialTheme.colorScheme.surface
    }
    val borderColor = when {
        hasError -> Color(0xFFEF5350)
        isCustomized -> Color(0xFF66BB6A)
        else -> MaterialTheme.colorScheme.outline.copy(alpha = 0.45f)
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor),
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
                    color = Color(0xFF2E7D32),
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
                    color = Color(0xFFC62828),
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
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = onSubmit, enabled = !state.isLoading) {
                Text(if (state.isLoading) "处理中..." else "开始总结")
            }
            Button(
                onClick = onSaveNote,
                enabled = !state.isSavingNote && state.result != null,
            ) {
                Text(if (state.isSavingNote) "保存中..." else "保存这次总结")
            }
        }
        if (state.isLoading) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CircularProgressIndicator(modifier = Modifier.height(20.dp))
                Text("高精度处理中，请耐心等待。")
            }
        }
        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = Color(0xFFC62828))
        }
        if (state.saveStatus.isNotBlank()) {
            Text(text = state.saveStatus, color = Color(0xFF2E7D32))
        }
        state.result?.let { result ->
            BilibiliResult(result)
        }
    }
}

@Composable
private fun BilibiliResult(result: BilibiliSummaryData) {
    val elapsedSeconds = result.elapsedMs / 1000.0
    Card(modifier = Modifier.fillMaxWidth()) {
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
    onLimitChange: (String) -> Unit,
    onStartSync: () -> Unit,
    onSaveNotes: () -> Unit,
    onPruneSyncedNoteIds: () -> Unit,
    onRefreshAuthConfig: () -> Unit,
    onSaveSingleNote: (XiaohongshuSummaryItem) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("小红书同步", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = state.limitInput,
            onValueChange = onLimitChange,
            label = { Text("本次同步条数") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = onStartSync, enabled = !state.isSyncing) {
                Text(if (state.isSyncing) "同步中..." else "同步最近收藏")
            }
            Button(
                onClick = onSaveNotes,
                enabled = !state.isSavingNotes && state.summaries.isNotEmpty(),
            ) {
                Text(if (state.isSavingNotes) "保存中..." else "批量保存本次结果")
            }
        }
        Button(
            onClick = onPruneSyncedNoteIds,
            enabled = !state.isPruningSyncedNoteIds && !state.isSyncing,
        ) {
            Text(if (state.isPruningSyncedNoteIds) "清理中..." else "清理无效ID")
        }
        Button(
            onClick = onRefreshAuthConfig,
            enabled = !state.isRefreshingCaptureConfig && !state.isSyncing,
        ) {
            Text(if (state.isRefreshingCaptureConfig) "更新中..." else "更新auth配置")
        }
        Text(
            text = "清理已被标记为“已同步”但你并未保存的笔记，下次同步时会重新尝试生成。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = "优先读取默认 HAR，失败后回退默认 cURL，自动更新小红书请求头。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (state.isSyncing) {
            if (state.progressTotal > 0) {
                val progress = (state.progressCurrent.toFloat() / state.progressTotal.toFloat()).coerceIn(0f, 1f)
                LinearProgressIndicator(progress = progress, modifier = Modifier.fillMaxWidth())
                Text("进度：${state.progressCurrent}/${state.progressTotal}")
            } else {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text("进度：准备中")
            }
            if (state.progressMessage.isNotBlank()) {
                Text(state.progressMessage)
            }
        }

        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = Color(0xFFC62828))
        }
        if (state.saveStatus.isNotBlank()) {
            Text(text = state.saveStatus, color = Color(0xFF2E7D32))
        }
        if (state.pruneStatus.isNotBlank()) {
            Text(text = state.pruneStatus, color = Color(0xFF2E7D32))
        }
        if (state.captureRefreshStatus.isNotBlank()) {
            Text(text = state.captureRefreshStatus, color = Color(0xFF2E7D32))
        }
        if (state.statsText.isNotBlank()) {
            Text(text = state.statsText, fontWeight = FontWeight.SemiBold)
        }

        state.summaries.forEach { summary ->
            XiaohongshuSummaryCard(
                item = summary,
                onSave = { onSaveSingleNote(summary) },
                isSaving = summary.noteId in state.savingSingleNoteIds,
                isSaved = summary.noteId in state.savedNoteIds,
                batchSaving = state.isSavingNotes,
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
    batchSaving: Boolean,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
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
                Button(
                    onClick = onSave,
                    enabled = !batchSaving && !isSaving && !isSaved,
                ) {
                    Text(
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
private fun NotesPanel(
    state: NotesUiState,
    onKeywordChange: (String) -> Unit,
    onRefresh: () -> Unit,
    onDeleteBilibili: (String) -> Unit,
    onClearBilibili: () -> Unit,
    onDeleteXiaohongshu: (String) -> Unit,
    onClearXiaohongshu: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var selectedDetail by remember { mutableStateOf<NoteDetailViewState?>(null) }
    val keyword = state.keywordInput.trim()
    val filteredBilibili = state.bilibiliNotes.filter { item ->
        keyword.isBlank() || item.title.contains(keyword, ignoreCase = true)
    }
    val filteredXhs = state.xiaohongshuNotes.filter { item ->
        keyword.isBlank() || item.title.contains(keyword, ignoreCase = true)
    }

    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (selectedDetail != null) {
            NoteDetailPanel(
                detail = selectedDetail!!,
                onBack = { selectedDetail = null },
            )
            return@Column
        }

        Text("已保存笔记", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = state.keywordInput,
            onValueChange = onKeywordChange,
            label = { Text("关键词检索（标题）") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = onRefresh, enabled = !state.isLoading) {
                Text(if (state.isLoading) "刷新中..." else "刷新笔记库")
            }
            Button(onClick = onClearBilibili, enabled = state.bilibiliNotes.isNotEmpty()) {
                Text("清空B站")
            }
            Button(onClick = onClearXiaohongshu, enabled = state.xiaohongshuNotes.isNotEmpty()) {
                Text("清空小红书")
            }
        }

        if (state.errorMessage.isNotBlank()) {
            Text(text = state.errorMessage, color = Color(0xFFC62828))
        }
        if (state.actionStatus.isNotBlank()) {
            Text(text = state.actionStatus, color = Color(0xFF2E7D32))
        }

        Text(
            text = "B站笔记（${filteredBilibili.size}/${state.bilibiliNotes.size}）",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        if (filteredBilibili.isEmpty()) {
            Text("暂无 B 站已保存笔记。", style = MaterialTheme.typography.bodySmall)
        }
        filteredBilibili.forEach { item ->
            SavedNoteListItem(
                title = item.title,
                savedAt = item.savedAt,
                onOpen = { selectedDetail = NoteDetailViewState.Bilibili(item) },
                onDelete = { onDeleteBilibili(item.noteId) },
            )
        }

        Text(
            text = "小红书笔记（${filteredXhs.size}/${state.xiaohongshuNotes.size}）",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        if (filteredXhs.isEmpty()) {
            Text("暂无小红书已保存笔记。", style = MaterialTheme.typography.bodySmall)
        }
        filteredXhs.forEach { item ->
            SavedNoteListItem(
                title = item.title,
                savedAt = item.savedAt,
                onOpen = { selectedDetail = NoteDetailViewState.Xiaohongshu(item) },
                onDelete = { onDeleteXiaohongshu(item.noteId) },
            )
        }
    }
}

@Composable
private fun SavedNoteListItem(
    title: String,
    savedAt: String,
    onOpen: () -> Unit,
    onDelete: () -> Unit,
) {
    var menuExpanded by remember(title, savedAt) { mutableStateOf(false) }

    Card(modifier = Modifier.fillMaxWidth()) {
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
                    modifier = Modifier.clickable(onClick = onOpen),
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

@Composable
private fun NoteDetailPanel(
    detail: NoteDetailViewState,
    onBack: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Button(onClick = onBack) {
            Text("返回标题列表")
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            when (detail) {
                is NoteDetailViewState.Bilibili -> {
                    BilibiliNoteDetail(note = detail.note)
                }

                is NoteDetailViewState.Xiaohongshu -> {
                    XiaohongshuNoteDetail(note = detail.note)
                }
            }
        }
    }
}

@Composable
private fun BilibiliNoteDetail(note: BilibiliSavedNote) {
    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(note.title, style = MaterialTheme.typography.titleSmall)
        Text("保存时间：${note.savedAt}", style = MaterialTheme.typography.bodySmall)
        Text(note.videoUrl, style = MaterialTheme.typography.bodySmall)
        HorizontalDivider()
        MarkdownText(markdown = note.summaryMarkdown, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
private fun XiaohongshuNoteDetail(note: XiaohongshuSavedNote) {
    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(note.title, style = MaterialTheme.typography.titleSmall)
        Text("保存时间：${note.savedAt}", style = MaterialTheme.typography.bodySmall)
        Text(note.sourceUrl, style = MaterialTheme.typography.bodySmall)
        HorizontalDivider()
        MarkdownText(markdown = note.summaryMarkdown, modifier = Modifier.fillMaxWidth())
    }
}
