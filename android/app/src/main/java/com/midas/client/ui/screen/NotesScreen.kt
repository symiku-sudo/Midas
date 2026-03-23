package com.midas.client.ui.screen

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.NotesMergeCandidateItem
import com.midas.client.data.model.NotesMergePreviewData
import com.midas.client.data.model.UnifiedNoteItem
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.ui.components.MarkdownText

@Composable
@Suppress("UNUSED_PARAMETER")
internal fun NotesPanel(
    state: NotesUiState,
    onKeywordChange: (String) -> Unit,
    onSourceFilterChange: (String) -> Unit,
    onDateWindowChange: (Int) -> Unit,
    onMergedFilterChange: (String) -> Unit,
    onSortChange: (String, String) -> Unit,
    onRefresh: () -> Unit,
    onLoadRelatedNotes: (UnifiedNoteItem) -> Unit,
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
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            NotesFilterDropdown(
                title = "来源",
                currentLabel = notesSourceFilterLabel(state.sourceFilter),
                options = listOf(
                    NotesFilterOption("全部来源") { onSourceFilterChange("") },
                    NotesFilterOption("B站") { onSourceFilterChange("bilibili") },
                    NotesFilterOption("小红书") { onSourceFilterChange("xiaohongshu") },
                ),
                modifier = Modifier.weight(1f),
            )
            NotesFilterDropdown(
                title = "时间",
                currentLabel = notesDateWindowLabel(state.dateWindowDays),
                options = listOf(
                    NotesFilterOption("全部时间") { onDateWindowChange(0) },
                    NotesFilterOption("近7天") { onDateWindowChange(7) },
                    NotesFilterOption("近30天") { onDateWindowChange(30) },
                ),
                modifier = Modifier.weight(1f),
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            NotesFilterDropdown(
                title = "状态",
                currentLabel = notesMergedFilterLabel(state.mergedFilter),
                options = listOf(
                    NotesFilterOption("全部状态") { onMergedFilterChange("all") },
                    NotesFilterOption("已合并") { onMergedFilterChange("merged") },
                    NotesFilterOption("未合并") { onMergedFilterChange("unmerged") },
                ),
                modifier = Modifier.weight(1f),
            )
            NotesFilterDropdown(
                title = "排序",
                currentLabel = notesSortLabel(state.sortBy, state.sortOrder),
                options = listOf(
                    NotesFilterOption("最新优先") { onSortChange("saved_at", "desc") },
                    NotesFilterOption("标题排序") { onSortChange("title", "asc") },
                ),
                modifier = Modifier.weight(1f),
            )
        }
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

        if (state.unifiedNotes.isNotEmpty()) {
            Text(
                text = "统一视图（${state.unifiedNotes.size}）",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            state.unifiedNotes.take(6).forEach { item ->
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text(
                            text = item.title.ifBlank { item.noteId },
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            text = "${item.source} · ${item.savedAt}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (item.topics.isNotEmpty()) {
                            Text(
                                text = "主题：${item.topics.joinToString(" / ")}",
                                style = MaterialTheme.typography.bodySmall,
                                color = LinkStatusColor,
                            )
                        }
                        Text(
                            text = if (item.isMerged) "状态：已合并" else "状态：普通笔记",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (item.isMerged) WarningStatusColor else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        MidasButton(
                            onClick = { onLoadRelatedNotes(item) },
                            tone = ButtonTone.NEUTRAL,
                        ) {
                            SingleLineActionText(
                                if (state.isRelatedLoading && state.relatedNotesTarget?.noteId == item.noteId) {
                                    "回查中..."
                                } else {
                                    "查看相关笔记"
                                },
                            )
                        }
                    }
                }
            }
        }

        if (state.reviewTopicsWeek.isNotEmpty() || state.reviewTopicsMonth.isNotEmpty()) {
            Text(
                text = "主题回顾",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            val sections = listOf(
                "最近一周" to state.reviewTopicsWeek,
                "最近一月" to state.reviewTopicsMonth,
            )
            sections.forEach { (label, items) ->
                if (items.isEmpty()) return@forEach
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text(label, style = MaterialTheme.typography.titleSmall)
                        items.take(4).forEach { item ->
                            Text(
                                text = "${item.topic} · ${item.total} 条",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }
        }

        if (state.reviewTimeline.isNotEmpty()) {
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text("时间回顾", style = MaterialTheme.typography.titleSmall)
                    state.reviewTimeline.take(6).forEach { item ->
                        Text(
                            text = "${item.label} · 新增 ${item.total} 条",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        }

        if (state.relatedNotesTarget != null && (state.relatedNotes.isNotEmpty() || state.isRelatedLoading)) {
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(
                        text = "相关笔记：${state.relatedNotesTarget.title.ifBlank { state.relatedNotesTarget.noteId }}",
                        style = MaterialTheme.typography.titleSmall,
                    )
                    if (state.isRelatedLoading) {
                        Text("正在回查相关笔记...", style = MaterialTheme.typography.bodySmall)
                    } else if (state.relatedNotes.isEmpty()) {
                        Text("暂无明显相关笔记。", style = MaterialTheme.typography.bodySmall)
                    } else {
                        state.relatedNotes.forEach { item ->
                            Text(
                                text = "${item.title} · ${"%.2f".format(item.score)} · ${item.relationLevel}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }
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
                                "来源：${if (item.source == "bilibili") "B站" else "小红书"}  " +
                                    "相似度：${"%.2f".format(item.score)}  " +
                                    "相关级别：${if (item.relationLevel == "STRONG") "强相关" else "弱相关"}"
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

private data class NotesFilterOption(
    val label: String,
    val onSelect: () -> Unit,
)

@Composable
private fun NotesFilterDropdown(
    title: String,
    currentLabel: String,
    options: List<NotesFilterOption>,
    modifier: Modifier = Modifier,
) {
    var expanded by remember(title, currentLabel) { mutableStateOf(false) }
    Box(modifier = modifier) {
        MidasButton(
            onClick = { expanded = true },
            modifier = Modifier.fillMaxWidth(),
            tone = ButtonTone.NEUTRAL,
        ) {
            SingleLineActionText("$title：$currentLabel")
        }
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(option.label) },
                    onClick = {
                        expanded = false
                        option.onSelect()
                    },
                )
            }
        }
    }
}

private fun notesSourceFilterLabel(value: String): String {
    return when (value) {
        "bilibili" -> "B站"
        "xiaohongshu" -> "小红书"
        else -> "全部来源"
    }
}

private fun notesDateWindowLabel(days: Int): String {
    return when (days) {
        7 -> "近7天"
        30 -> "近30天"
        else -> "全部时间"
    }
}

private fun notesMergedFilterLabel(value: String): String {
    return when (value) {
        "merged" -> "已合并"
        "unmerged" -> "未合并"
        else -> "全部状态"
    }
}

private fun notesSortLabel(sortBy: String, sortOrder: String): String {
    return when {
        sortBy == "title" && sortOrder == "asc" -> "标题排序"
        else -> "最新优先"
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
                        "来源：${if (candidate.source == "bilibili") "B站" else "小红书"}  " +
                            "相似度：${"%.2f".format(candidate.score)}  " +
                            "相关级别：${if (candidate.relationLevel == "STRONG") "强相关" else "弱相关"}"
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
