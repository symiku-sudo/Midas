package com.midas.client.ui.screen

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.data.model.XiaohongshuSummaryItem
import org.junit.Assert.assertEquals
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
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("开始总结").performClick()
        composeRule.onNodeWithText("保存总结").performClick()

        composeRule.onNodeWithText("小红书").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText("总结单篇").performClick()
        composeRule.onNodeWithTag("xhs_save_single_test-note-id", useUnmergedTree = true).performScrollTo().performClick()

        composeRule.onNodeWithText("笔记库").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText("刷新笔记库").performClick()

        composeRule.onNodeWithText("设置").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText("保存").performClick()
        composeRule.onNodeWithText("连接测试").performClick()
        composeRule.onNodeWithText("恢复默认").performClick()
        composeRule.waitForIdle()

        assertEquals(1, bilibiliSubmitClicks)
        assertEquals(1, bilibiliSaveClicks)
        assertEquals(1, xhsSummarizeUrlClicks)
        assertEquals(1, xhsSaveSingleClicks)
        assertEquals(1, notesRefreshClicks)
        assertEquals(1, saveBaseUrlClicks)
        assertEquals(1, testConnectionClicks)
        assertEquals(1, resetConfigClicks)
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
    fun xhsInput_clearButton_shouldTriggerEmptyCallback() {
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
                    enableLifecycleAutoRefresh = false,
                    enableCyclicTabs = false,
                    animateTabSwitch = false,
                )
            }
        }

        composeRule.onNodeWithText("小红书").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("xhs_url_clear_button", useUnmergedTree = true).performClick()
        composeRule.waitForIdle()

        assertEquals("", latestUrlInput)
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

        composeRule.onNodeWithText("笔记库").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText("B站笔记（1/1）").assertIsDisplayed()
    }
}
