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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
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
    SETTINGS("设置"),
    BILIBILI("B站总结"),
    XHS("小红书同步"),
    NOTES("笔记库"),
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
    val control: ConfigControlKind,
    val options: List<ConfigOption> = emptyList(),
)

private val configFieldSpecs = listOf(
    ConfigFieldSpec(
        path = "llm.enabled",
        section = "总结能力",
        title = "启用 LLM 总结",
        description = "关闭后使用本地降级摘要，不请求模型。",
        control = ConfigControlKind.SWITCH,
    ),
    ConfigFieldSpec(
        path = "llm.model",
        section = "总结能力",
        title = "LLM 模型",
        description = "填写服务端可用模型名，例如 gemini-3-flash-preview。",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "llm.timeout_seconds",
        section = "总结能力",
        title = "LLM 超时（秒）",
        description = "单次模型请求最长等待时间。",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "asr.mode",
        section = "总结能力",
        title = "视频转写模式",
        description = "faster_whisper 为真实转写，mock 为调试文本。",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "faster_whisper", label = "真实转写（faster_whisper）"),
            ConfigOption(value = "mock", label = "调试模式（mock）"),
        ),
    ),
    ConfigFieldSpec(
        path = "asr.model_size",
        section = "总结能力",
        title = "Whisper 模型大小",
        description = "模型越大通常越准，但速度更慢、占用更高。",
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
        description = "Whisper 语言代码，中文填 zh，英文可填 en。",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.mode",
        section = "小红书同步",
        title = "同步模式",
        description = "web_readonly 为真实同步，mock 为本地示例数据。",
        control = ConfigControlKind.DROPDOWN,
        options = listOf(
            ConfigOption(value = "web_readonly", label = "真实同步（web_readonly）"),
            ConfigOption(value = "mock", label = "示例数据（mock）"),
        ),
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.collection_id",
        section = "小红书同步",
        title = "收藏夹 ID",
        description = "真实同步时使用的小红书收藏夹 ID。",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.default_limit",
        section = "小红书同步",
        title = "默认同步条数",
        description = "未指定 limit 时使用这个值。",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "xiaohongshu.max_limit",
        section = "小红书同步",
        title = "单次最大同步条数",
        description = "客户端可请求的上限，防止单次任务过大。",
        control = ConfigControlKind.TEXT,
    ),
    ConfigFieldSpec(
        path = "runtime.log_level",
        section = "运行与调试",
        title = "日志级别",
        description = "排查问题建议临时切到 DEBUG，平时建议 INFO。",
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
        control = ConfigControlKind.TEXT,
    ),
)

@Composable
fun MainScreen(viewModel: MainViewModel) {
    val settings by viewModel.settingsState.collectAsStateWithLifecycle()
    val bilibili by viewModel.bilibiliState.collectAsStateWithLifecycle()
    val xiaohongshu by viewModel.xiaohongshuState.collectAsStateWithLifecycle()
    val notes by viewModel.notesState.collectAsStateWithLifecycle()

    var selectedTab by remember { mutableStateOf(MainTab.SETTINGS) }

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
                    onLoadConfig = viewModel::loadEditableConfig,
                    onConfigTextChange = viewModel::onEditableConfigFieldTextChange,
                    onConfigBooleanChange = viewModel::onEditableConfigFieldBooleanChange,
                    onSaveConfig = viewModel::saveEditableConfig,
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
                    onConfirmLiveChange = viewModel::onXiaohongshuConfirmLiveChange,
                    onStartSync = viewModel::startXiaohongshuSync,
                    onSaveNotes = viewModel::saveCurrentXiaohongshuSummaries,
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
    onLoadConfig: () -> Unit,
    onConfigTextChange: (String, String) -> Unit,
    onConfigBooleanChange: (String, Boolean) -> Unit,
    onSaveConfig: () -> Unit,
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
            Button(onClick = onLoadConfig, enabled = !state.isConfigLoading) {
                Text(if (state.isConfigLoading) "加载中..." else "加载配置")
            }
            Button(
                onClick = onSaveConfig,
                enabled = !state.isConfigSaving && state.editableConfigFields.isNotEmpty(),
            ) {
                Text(if (state.isConfigSaving) "保存中..." else "保存配置")
            }
            Button(onClick = onResetConfig, enabled = !state.isConfigResetting) {
                Text(if (state.isConfigResetting) "恢复中..." else "恢复默认")
            }
        }
        EditableConfigFieldsPanel(
            fields = state.editableConfigFields,
            onTextChange = onConfigTextChange,
            onBooleanChange = onConfigBooleanChange,
        )
        if (state.configStatus.isNotBlank()) {
            Text(text = state.configStatus)
        }
    }
}

@Composable
private fun EditableConfigFieldsPanel(
    fields: List<EditableConfigField>,
    onTextChange: (String, String) -> Unit,
    onBooleanChange: (String, Boolean) -> Unit,
) {
    val fieldByPath = fields.associateBy { it.path }
    val visibleFields = configFieldSpecs.mapNotNull { spec ->
        fieldByPath[spec.path]?.let { field -> spec to field }
    }

    if (visibleFields.isEmpty()) {
        Text(
            text = "当前没有可展示的配置项，请先点击“加载配置”。",
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
    onTextChange: (String, String) -> Unit,
    onBooleanChange: (String, Boolean) -> Unit,
) {
    when (spec.control) {
        ConfigControlKind.SWITCH -> {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(text = spec.title, fontWeight = FontWeight.SemiBold)
                    Text(
                        text = spec.description,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
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
                spec = spec,
                currentValue = field.textValue,
                onSelect = { selected ->
                    onTextChange(spec.path, selected)
                },
            )
        }

        ConfigControlKind.TEXT -> {
            val isList = field.type == ConfigFieldType.LIST_JSON
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(text = spec.title, fontWeight = FontWeight.SemiBold)
                Text(
                    text = spec.description,
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = field.textValue,
                    onValueChange = { value ->
                        onTextChange(spec.path, value)
                    },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = !isList,
                    minLines = if (isList) 2 else 1,
                )
            }
        }
    }
}

@Composable
private fun ConfigDropdownField(
    spec: ConfigFieldSpec,
    currentValue: String,
    onSelect: (String) -> Unit,
) {
    var expanded by remember(spec.path) { mutableStateOf(false) }
    val selectedLabel = spec.options.firstOrNull { option -> option.value == currentValue }?.label
        ?: currentValue.ifBlank { "请选择" }

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(text = spec.title, fontWeight = FontWeight.SemiBold)
        Text(
            text = spec.description,
            style = MaterialTheme.typography.bodySmall,
        )
        Box(modifier = Modifier.fillMaxWidth()) {
            OutlinedTextField(
                value = selectedLabel,
                onValueChange = {},
                readOnly = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = true },
            )
            DropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false },
            ) {
                spec.options.forEach { option ->
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
            label = { Text("输入 B 站视频链接") },
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
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("链接：${result.videoUrl}", style = MaterialTheme.typography.bodySmall)
            Text(
                "耗时：${result.elapsedMs} ms，转写字数：${result.transcriptChars}",
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
    onConfirmLiveChange: (Boolean) -> Unit,
    onStartSync: () -> Unit,
    onSaveNotes: () -> Unit,
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
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("确认真实同步请求")
                Text(
                    text = "仅在服务端 mode=web_readonly 时需要打开",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Switch(
                checked = state.confirmLive,
                onCheckedChange = onConfirmLiveChange,
            )
        }
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
        if (state.statsText.isNotBlank()) {
            Text(text = state.statsText, fontWeight = FontWeight.SemiBold)
        }

        state.summaries.forEach { summary ->
            XiaohongshuSummaryCard(summary)
        }
    }
}

@Composable
private fun XiaohongshuSummaryCard(item: XiaohongshuSummaryItem) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(item.title, style = MaterialTheme.typography.titleSmall)
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
    val keyword = state.keywordInput.trim()
    val filteredBilibili = state.bilibiliNotes.filter { item ->
        keyword.isBlank() || listOf(item.title, item.videoUrl, item.summaryMarkdown)
            .any { value -> value.contains(keyword, ignoreCase = true) }
    }
    val filteredXhs = state.xiaohongshuNotes.filter { item ->
        keyword.isBlank() || listOf(item.title, item.sourceUrl, item.summaryMarkdown)
            .any { value -> value.contains(keyword, ignoreCase = true) }
    }

    Column(
        modifier = modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("已保存笔记", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = state.keywordInput,
            onValueChange = onKeywordChange,
            label = { Text("关键词检索（标题/链接/内容）") },
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
            BilibiliSavedNoteCard(item = item, onDelete = onDeleteBilibili)
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
            XiaohongshuSavedNoteCard(item = item, onDelete = onDeleteXiaohongshu)
        }
    }
}

@Composable
private fun BilibiliSavedNoteCard(
    item: BilibiliSavedNote,
    onDelete: (String) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(item.title, style = MaterialTheme.typography.titleSmall)
            Text("ID: ${item.noteId}", style = MaterialTheme.typography.bodySmall)
            Text(item.videoUrl, style = MaterialTheme.typography.bodySmall)
            Text("保存时间：${item.savedAt}", style = MaterialTheme.typography.bodySmall)
            HorizontalDivider()
            MarkdownText(markdown = item.summaryMarkdown, modifier = Modifier.fillMaxWidth())
            Button(onClick = { onDelete(item.noteId) }) {
                Text("删除此笔记")
            }
        }
    }
}

@Composable
private fun XiaohongshuSavedNoteCard(
    item: XiaohongshuSavedNote,
    onDelete: (String) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(item.title, style = MaterialTheme.typography.titleSmall)
            Text("ID: ${item.noteId}", style = MaterialTheme.typography.bodySmall)
            Text(item.sourceUrl, style = MaterialTheme.typography.bodySmall)
            Text("保存时间：${item.savedAt}", style = MaterialTheme.typography.bodySmall)
            HorizontalDivider()
            MarkdownText(markdown = item.summaryMarkdown, modifier = Modifier.fillMaxWidth())
            Button(onClick = { onDelete(item.noteId) }) {
                Text("删除此笔记")
            }
        }
    }
}
