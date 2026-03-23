package com.midas.client.ui.screen

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import com.midas.client.data.model.AsyncJobListItemData
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.FinanceFocusCard
import com.midas.client.data.model.FinanceNewsItem
import com.midas.client.data.model.FinanceWatchlistItem
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.data.model.XiaohongshuSummaryItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class MainScreenContentRobolectricSmokeTest {
    @get:Rule
    val composeRule = createComposeRule()

    private fun clickTopSection(title: String) {
        composeRule.onNodeWithTag("glass_tab_bar_scroll", useUnmergedTree = true)
            .performScrollToNode(hasText(title))
        composeRule.onNodeWithText(title, useUnmergedTree = true).performClick()
        composeRule.waitForIdle()
    }

    @Test
    fun glassTabBar_shouldKeepAllSectionsReachable_onCompactWidth() {
        composeRule.setContent {
            MaterialTheme {
                Box(modifier = Modifier.width(240.dp)) {
                    GlassTabBar(
                        selectedTabIndex = TopSection.FINANCE.ordinal,
                        labels = TopSection.entries.map { it.title },
                        onSelect = {},
                    )
                }
            }
        }

        TopSection.entries.forEach { section ->
            composeRule.onNodeWithTag("glass_tab_bar_scroll", useUnmergedTree = true)
                .performScrollToNode(hasText(section.title))
            val node = composeRule.onNodeWithText(section.title, useUnmergedTree = true)
            node.assertIsDisplayed()
            node.performClick()
        }
    }

    @Test
    fun smoke_clickMainButtons_withoutDevice_usesOnlyInjectedCallbacks() {
        var saveBaseUrlClicks = 0
        var testConnectionClicks = 0
        var resetConfigClicks = 0
        var bilibiliSubmitClicks = 0
        var bilibiliSaveClicks = 0
        var xhsSummarizeUrlClicks = 0
        var xhsSaveSingleClicks = 0
        var notesRefreshClicks = 0

        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(
                        baseUrlInput = "http://127.0.0.1:8000/",
                    ),
                    bilibili = BilibiliUiState(
                        videoUrlInput = "BV1xx411c7mD",
                        result = BilibiliSummaryData(
                            videoUrl = "https://www.bilibili.com/video/BV1xx411c7mD",
                            summaryMarkdown = "# 总结",
                            elapsedMs = 1200,
                            transcriptChars = 88,
                        ),
                    ),
                    xiaohongshu = XiaohongshuUiState(
                        urlInput = "https://www.xiaohongshu.com/explore/test-note-id",
                        summaries = listOf(
                            XiaohongshuSummaryItem(
                                noteId = "test-note-id",
                                title = "测试笔记",
                                sourceUrl = "https://www.xiaohongshu.com/explore/test-note-id",
                                summaryMarkdown = "# 测试总结",
                            ),
                        ),
                    ),
                    notes = NotesUiState(
                        bilibiliNotes = listOf(
                            BilibiliSavedNote(
                                noteId = "b1",
                                title = "B站笔记",
                                videoUrl = "https://www.bilibili.com/video/BV1xx411c7mD",
                                summaryMarkdown = "# B",
                                elapsedMs = 1000,
                                transcriptChars = 66,
                                savedAt = "2026-02-27 00:00:00",
                            ),
                        ),
                        xiaohongshuNotes = listOf(
                            XiaohongshuSavedNote(
                                noteId = "x1",
                                title = "小红书笔记",
                                sourceUrl = "https://www.xiaohongshu.com/explore/x1",
                                summaryMarkdown = "# X",
                                savedAt = "2026-02-27 00:00:00",
                            ),
                        ),
                    ),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = { saveBaseUrlClicks += 1 },
                    onTestConnection = { testConnectionClicks += 1 },
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = { resetConfigClicks += 1 },
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = { bilibiliSubmitClicks += 1 },
                    onSaveBilibiliNote = { bilibiliSaveClicks += 1 },
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = { xhsSummarizeUrlClicks += 1 },
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = { _ -> xhsSaveSingleClicks += 1 },
                    onNotesKeywordChange = {},
                    onRefreshNotes = { notesRefreshClicks += 1 },
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.BILIBILI,
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("开始总结").performClick()
        composeRule.onNodeWithText("保存总结").performClick()

        clickTopSection("笔记")
        composeRule.onNodeWithText("刷新笔记库").performScrollTo().performClick()

        clickTopSection("设置")
        composeRule.onNodeWithText("保存").performClick()
        composeRule.onNodeWithText("连接测试").performClick()
        composeRule.onNodeWithText("恢复默认").performScrollTo().performClick()
        composeRule.waitForIdle()

        assertEquals(1, bilibiliSubmitClicks)
        assertEquals(1, bilibiliSaveClicks)
        assertEquals(0, xhsSummarizeUrlClicks)
        assertEquals(0, xhsSaveSingleClicks)
        assertEquals(1, notesRefreshClicks)
        assertEquals(1, saveBaseUrlClicks)
        assertEquals(1, testConnectionClicks)
        assertEquals(1, resetConfigClicks)
    }

    @Test
    fun bilibiliRecentJobsCard_shouldSupportRefreshOpenAndRetry() {
        var refreshClicks = 0
        var openedJobId = ""
        var retriedJobId = ""

        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(
                        baseUrlInput = "http://127.0.0.1:8000/",
                    ),
                    bilibili = BilibiliUiState(
                        recentJobs = listOf(
                            AsyncJobListItemData(
                                jobId = "job-bili-ok",
                                jobType = "bilibili_summarize",
                                status = "SUCCEEDED",
                                message = "任务执行完成。",
                                submittedAt = "2026-03-12 12:30:00",
                                finishedAt = "2026-03-12 12:31:00",
                            ),
                            AsyncJobListItemData(
                                jobId = "job-bili-failed",
                                jobType = "bilibili_summarize",
                                status = "FAILED",
                                message = "上游暂时不可用。",
                                submittedAt = "2026-03-12 12:32:00",
                                finishedAt = "2026-03-12 12:33:00",
                            ),
                        ),
                    ),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onRefreshBilibiliJobs = { refreshClicks += 1 },
                    onOpenBilibiliJob = { openedJobId = it },
                    onRetryBilibiliJob = { retriedJobId = it },
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.BILIBILI,
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("刷新任务").performScrollTo().performClick()
        composeRule.onNodeWithTag("job_open_job-bili-ok", useUnmergedTree = true)
            .performScrollTo()
            .performClick()
        composeRule.onNodeWithTag("job_retry_job-bili-failed", useUnmergedTree = true)
            .performScrollTo()
            .performClick()

        assertEquals(1, refreshClicks)
        assertEquals("job-bili-ok", openedJobId)
        assertEquals("job-bili-failed", retriedJobId)
    }

    @Test
    fun workspaceDropdown_switchToFinance_shouldShowSignalPanelAndTriggerRefresh() {
        var financeRefreshClicks = 0

        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    onRefreshFinanceSignals = { financeRefreshClicks += 1 },
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        clickTopSection("财经")

        composeRule.onAllNodesWithText("财经信号").assertCountEquals(1)
        composeRule.onAllNodesWithText("Watchlist").assertCountEquals(1)
        composeRule.onAllNodesWithText("24小时新闻摘要").assertCountEquals(1)
        composeRule.onAllNodesWithText("今日金融与时政新闻 Top5").assertCountEquals(1)

        assertEquals(1, financeRefreshClicks)
    }

    @Test
    fun bilibiliInput_clearButton_shouldTriggerEmptyCallback() {
        var latestVideoInput = "BV1xx411c7mD"

        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(videoUrlInput = latestVideoInput),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = { latestVideoInput = it },
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.BILIBILI,
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithTag("bilibili_url_clear_button", useUnmergedTree = true).performClick()
        composeRule.waitForIdle()

        assertEquals("", latestVideoInput)
    }

    @Test
    fun xhsInput_shouldTriggerEmptyCallback() {
        var latestUrlInput = "https://www.xiaohongshu.com/explore/test-note-id"

        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(urlInput = latestUrlInput),
                    notes = NotesUiState(),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = { latestUrlInput = it },
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.XHS,
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithTag("xhs_url_input", useUnmergedTree = true).performTextClearance()
        composeRule.waitForIdle()

        assertEquals("", latestUrlInput)
    }

    @Test
    fun xhsPanel_singleLinkActions_shouldTriggerCallbacks() {
        var summarizeClicks = 0

        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(
                        urlInput = "https://www.xiaohongshu.com/explore/test-note-id",
                        summaries = listOf(
                            XiaohongshuSummaryItem(
                                noteId = "test-note-id",
                                title = "测试笔记",
                                sourceUrl = "https://www.xiaohongshu.com/explore/test-note-id",
                                summaryMarkdown = "# 测试总结",
                            ),
                        ),
                    ),
                    notes = NotesUiState(),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = { summarizeClicks += 1 },
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.XHS,
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("总结单篇").performScrollTo().performClick()
        composeRule.waitForIdle()

        assertEquals(1, summarizeClicks)
    }

    @Test
    fun notesKeyword_shouldMatchSummaryContent() {
        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(
                        keywordInput = "命中词",
                        bilibiliNotes = listOf(
                            BilibiliSavedNote(
                                noteId = "b1",
                                title = "标题未命中",
                                videoUrl = "https://www.bilibili.com/video/BV1xx411c7mD",
                                summaryMarkdown = "这里有命中词",
                                elapsedMs = 1000,
                                transcriptChars = 66,
                                savedAt = "2026-02-27 00:00:00",
                            ),
                        ),
                    ),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        clickTopSection("笔记")
        composeRule.onNodeWithText("B站笔记（1/1）").performScrollTo().assertIsDisplayed()
    }

    @Test
    fun mergeNoteDetail_shouldShowMergeMarkerInsteadOfSourceUrl() {
        val mergedUrl = "https://www.bilibili.com/video/BV1xx411c7mD"
        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(
                        bilibiliNotes = listOf(
                            BilibiliSavedNote(
                                noteId = "merged_note_abc123",
                                title = "合并笔记",
                                videoUrl = mergedUrl,
                                summaryMarkdown = "# 合并内容",
                                elapsedMs = 1000,
                                transcriptChars = 66,
                                savedAt = "2026-02-27 00:00:00",
                            ),
                        ),
                    ),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        clickTopSection("笔记")
        composeRule.onNodeWithTag("saved_note_open_merged_note_abc123", useUnmergedTree = true)
            .performScrollTo()
            .performClick()
        composeRule.waitForIdle()

        composeRule.onAllNodesWithText("Merge Note · 来源请见正文末尾链接").assertCountEquals(1)
        composeRule.onAllNodesWithText(mergedUrl).assertCountEquals(0)
    }

    @Test
    fun nonMergeNoteDetail_sourceUrl_shouldBeSingleLineAndKeepClickAction() {
        val longUrl = buildString {
            append("https://www.bilibili.com/video/BV1xx411c7mD?")
            repeat(120) { index ->
                append("spm_id_from=$index&")
            }
        }
        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(
                        bilibiliNotes = listOf(
                            BilibiliSavedNote(
                                noteId = "b-normal-1",
                                title = "普通笔记",
                                videoUrl = longUrl,
                                summaryMarkdown = "# 正文",
                                elapsedMs = 1000,
                                transcriptChars = 66,
                                savedAt = "2026-02-27 00:00:00",
                            ),
                        ),
                    ),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        clickTopSection("笔记")
        composeRule.onNodeWithTag("saved_note_open_b-normal-1", useUnmergedTree = true)
            .performScrollTo()
            .performClick()
        composeRule.waitForIdle()

        composeRule.onAllNodesWithTag("bili_source_url_detail", useUnmergedTree = true)
            .assertCountEquals(1)
        val linkNode = composeRule.onNodeWithTag("bili_source_url_detail", useUnmergedTree = true)
        linkNode.assertHasClickAction()

        val layoutResults = mutableListOf<TextLayoutResult>()
        linkNode.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { fetch ->
            assertTrue(fetch(layoutResults))
        }
        assertTrue(layoutResults.isNotEmpty())
        assertTrue(layoutResults.first().lineCount == 1)
    }

    @Test
    fun financePanel_shouldShowStaleRssHint() {
        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(),
                    finance = FinanceSignalsUiState(
                        updateTime = "2026-03-08 12:00:00",
                        newsLastFetchTime = "2026-03-08 11:40:00",
                        newsIsStale = true,
                    ),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.FINANCE,
                    enableLifecycleAutoRefresh = false,
                    enableFinanceAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("新闻拉取：2026-03-08 11:40:00（数据可能陈旧）").assertIsDisplayed()
    }

    @Test
    fun financePanel_shouldRenderThresholdBadge() {
        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(),
                    finance = FinanceSignalsUiState(
                        watchlistPreview = listOf(
                            FinanceWatchlistItem(
                                name = "布伦特原油",
                                symbol = "BZ=F",
                                price = 92.69,
                                changePct = "+8.52%",
                                alertHint = ">90",
                                alertActive = true,
                            ),
                        ),
                    ),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.FINANCE,
                    enableLifecycleAutoRefresh = false,
                    enableFinanceAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("阈值 >90").performScrollTo().assertIsDisplayed()
        composeRule.onNodeWithText("ntfy 已关闭").assertIsDisplayed()
    }

    @Test
    fun financePanel_shouldRenderWatchlistNewsLinks() {
        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(),
                    finance = FinanceSignalsUiState(
                        focusCards = listOf(
                            FinanceFocusCard(
                                title = "布伦特原油 已触发监控阈值",
                                summary = "阈值条件：>90；最近关联新闻 2 条",
                                priority = "HIGH",
                                kind = "ALERT",
                                actionType = "REVIEW_NOW",
                                actionLabel = "立即复核",
                                actionHint = "先看价格异动和关联新闻，再决定是否提升观察频率。",
                                reasons = listOf("threshold_triggered", "related_news_present"),
                                relatedWatchlistNames = listOf("布伦特原油"),
                            ),
                        ),
                        watchlistPreview = listOf(
                            FinanceWatchlistItem(
                                name = "布伦特原油",
                                symbol = "BZ=F",
                                price = 92.69,
                                changePct = "+8.52%",
                                relatedNewsCount = 2,
                                relatedKeywords = listOf("原油", "油价"),
                            ),
                        ),
                        topNews = listOf(
                            FinanceNewsItem(
                                title = "原油与黄金同步走高",
                                publisher = "Reuters",
                                published = "2026-03-12 11:30:00",
                                category = "finance",
                                matchedKeywords = listOf("原油", "黄金"),
                                relatedSymbols = listOf("BZ=F"),
                                relatedWatchlistNames = listOf("布伦特原油"),
                            ),
                        ),
                    ),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.FINANCE,
                    enableLifecycleAutoRefresh = false,
                    enableFinanceAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("今日关注建议").assertIsDisplayed()
        composeRule.onNodeWithText("阈值提醒").performScrollTo().assertIsDisplayed()
        composeRule.onNodeWithText("立即复核 · 立即处理").performScrollTo().assertIsDisplayed()
        composeRule.onNodeWithText("布伦特原油 已触发监控阈值").performScrollTo().assertIsDisplayed()
        composeRule.onNodeWithText("建议动作：先看价格异动和关联新闻，再决定是否提升观察频率。").performScrollTo()
            .assertIsDisplayed()
        composeRule.onNodeWithText("触发原因：阈值触发 / 已有关联新闻").performScrollTo()
            .assertIsDisplayed()
        composeRule.onNodeWithText("关联新闻 2").performScrollTo().assertIsDisplayed()
        composeRule.onNodeWithText("原油 / 油价").performScrollTo().assertIsDisplayed()
        composeRule.onNodeWithText("影响 布伦特原油").performScrollTo().assertIsDisplayed()
    }

    @Test
    fun financePanel_shouldRenderDailyDigestCard() {
        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(),
                    finance = FinanceSignalsUiState(
                        aiInsightText = "## 24小时摘要\n\n- 原油与黄金波动加剧。",
                        digestLastGeneratedAt = "2026-03-11 09:46:31",
                    ),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    initialSection = TopSection.FINANCE,
                    enableLifecycleAutoRefresh = false,
                    enableFinanceAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("24小时新闻摘要").performScrollTo().assertIsDisplayed()
        composeRule.onNodeWithTag("finance_digest_last_generated_at", useUnmergedTree = true)
            .performScrollTo()
            .assertIsDisplayed()
        composeRule.onNodeWithTag("finance_digest_button", useUnmergedTree = true)
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    fun financePanel_generateDigestButton_shouldTriggerCallback() {
        var triggerCount = 0

        composeRule.setContent {
            MaterialTheme {
                MainScreenContent(
                    settings = SettingsUiState(baseUrlInput = "http://127.0.0.1:8000/"),
                    bilibili = BilibiliUiState(),
                    xiaohongshu = XiaohongshuUiState(),
                    notes = NotesUiState(),
                    finance = FinanceSignalsUiState(),
                    onAppForeground = {},
                    onBaseUrlChange = {},
                    onSaveBaseUrl = {},
                    onTestConnection = {},
                    onConfigTextChange = { _, _ -> },
                    onConfigBooleanChange = { _, _ -> },
                    onResetConfig = {},
                    onBilibiliVideoUrlChange = {},
                    onSubmitBilibiliSummary = {},
                    onSaveBilibiliNote = {},
                    onXiaohongshuUrlChange = {},
                    onSummarizeXiaohongshuUrl = {},
                    onRefreshXiaohongshuAuthConfig = {},
                    onSaveSingleXiaohongshuNote = {},
                    onNotesKeywordChange = {},
                    onRefreshNotes = {},
                    onDeleteBilibiliNote = {},
                    onDeleteXiaohongshuNote = {},
                    onSuggestMergeCandidates = {},
                    onPreviewMergeCandidate = { _ -> },
                    onCommitCurrentMerge = {},
                    onRollbackLastMerge = {},
                    onFinalizeLastMerge = {},
                    onGenerateFinanceNewsDigest = { triggerCount += 1 },
                    initialSection = TopSection.FINANCE,
                    enableLifecycleAutoRefresh = false,
                    enableFinanceAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithTag("finance_digest_button", useUnmergedTree = true)
            .performScrollTo()
            .performClick()
        composeRule.waitForIdle()

        assertEquals(1, triggerCount)
    }
}
