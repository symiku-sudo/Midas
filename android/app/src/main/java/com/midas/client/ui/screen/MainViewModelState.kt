package com.midas.client.ui.screen

import com.midas.client.data.model.AsyncJobListItemData
import com.midas.client.data.model.BilibiliSavedNote
import com.midas.client.data.model.BilibiliSummaryData
import com.midas.client.data.model.FinanceFocusCard
import com.midas.client.data.model.FinanceFocusCardHistoryItem
import com.midas.client.data.model.FinanceNewsItem
import com.midas.client.data.model.FinanceWatchlistItem
import com.midas.client.data.model.NotesMergeCandidateItem
import com.midas.client.data.model.NotesMergeCommitData
import com.midas.client.data.model.NotesMergePreviewData
import com.midas.client.data.model.NotesReviewTopicItem
import com.midas.client.data.model.NotesTimelineReviewItem
import com.midas.client.data.model.RelatedNoteItem
import com.midas.client.data.model.UnifiedNoteItem
import com.midas.client.data.model.XiaohongshuSavedNote
import com.midas.client.data.model.XiaohongshuSummaryItem
import com.midas.client.util.EditableConfigField

data class SettingsUiState(
    val baseUrlInput: String = "",
    val accessTokenInput: String = "",
    val isTesting: Boolean = false,
    val testStatus: String = "",
    val saveStatus: String = "",
    val editableConfigFields: List<EditableConfigField> = emptyList(),
    val configFieldErrors: Map<String, String> = emptyMap(),
    val isConfigLoading: Boolean = false,
    val isConfigSaving: Boolean = false,
    val isConfigResetting: Boolean = false,
    val configStatus: String = "",
)

data class BilibiliUiState(
    val videoUrlInput: String = "",
    val isLoading: Boolean = false,
    val isSavingNote: Boolean = false,
    val isRecentJobsLoading: Boolean = false,
    val errorMessage: String = "",
    val submitStatus: String = "",
    val currentJobId: String = "",
    val recentJobsStatus: String = "",
    val saveStatus: String = "",
    val recentJobs: List<AsyncJobListItemData> = emptyList(),
    val result: BilibiliSummaryData? = null,
)

data class XiaohongshuUiState(
    val urlInput: String = "",
    val isSummarizingUrl: Boolean = false,
    val isRefreshingCaptureConfig: Boolean = false,
    val isRecentJobsLoading: Boolean = false,
    val savingSingleNoteIds: Set<String> = emptySet(),
    val savedNoteIds: Set<String> = emptySet(),
    val errorMessage: String = "",
    val saveStatus: String = "",
    val captureRefreshStatus: String = "",
    val summarizeUrlStatus: String = "",
    val currentJobId: String = "",
    val currentJobType: String = "",
    val recentJobsStatus: String = "",
    val recentJobs: List<AsyncJobListItemData> = emptyList(),
    val summaries: List<XiaohongshuSummaryItem> = emptyList(),
)

data class NotesUiState(
    val keywordInput: String = "",
    val sourceFilter: String = "",
    val dateWindowDays: Int = 0,
    val mergedFilter: String = "all",
    val sortBy: String = "saved_at",
    val sortOrder: String = "desc",
    val isLoading: Boolean = false,
    val isReviewLoading: Boolean = false,
    val isRelatedLoading: Boolean = false,
    val errorMessage: String = "",
    val actionStatus: String = "",
    val mergeStatus: String = "",
    val isMergeSuggesting: Boolean = false,
    val mergeCandidates: List<NotesMergeCandidateItem> = emptyList(),
    val isMergePreviewLoading: Boolean = false,
    val mergePreview: NotesMergePreviewData? = null,
    val mergePreviewKey: String = "",
    val mergePreviewCache: Map<String, NotesMergePreviewData> = emptyMap(),
    val isMergeCommitting: Boolean = false,
    val isMergeRollingBack: Boolean = false,
    val isMergeFinalizing: Boolean = false,
    val lastMergeCommit: NotesMergeCommitData? = null,
    val unifiedNotes: List<UnifiedNoteItem> = emptyList(),
    val reviewTopicsWeek: List<NotesReviewTopicItem> = emptyList(),
    val reviewTopicsMonth: List<NotesReviewTopicItem> = emptyList(),
    val reviewTimeline: List<NotesTimelineReviewItem> = emptyList(),
    val relatedNotesTarget: UnifiedNoteItem? = null,
    val relatedNotes: List<RelatedNoteItem> = emptyList(),
    val bilibiliNotes: List<BilibiliSavedNote> = emptyList(),
    val xiaohongshuNotes: List<XiaohongshuSavedNote> = emptyList(),
)

internal const val ASYNC_JOB_POLL_INTERVAL_MS = 1500L
internal const val ASYNC_JOB_POLL_MAX_ATTEMPTS = 800
internal const val XIAOHONGSHU_CAPTURE_JOB_TYPE = "xiaohongshu_summarize_url"

data class FinanceSignalsUiState(
    val isLoading: Boolean = false,
    val updateTime: String = "",
    val newsLastFetchTime: String = "",
    val newsIsStale: Boolean = false,
    val allFocusCards: List<FinanceFocusCard> = emptyList(),
    val focusCards: List<FinanceFocusCard> = emptyList(),
    val dismissedFocusCardCount: Int = 0,
    val historyCount: Int = 0,
    val isUpdatingFocusCardStatus: Boolean = false,
    val focusCardHistory: List<FinanceFocusCardHistoryItem> = emptyList(),
    val watchlistPreview: List<FinanceWatchlistItem> = emptyList(),
    val topNews: List<FinanceNewsItem> = emptyList(),
    val watchlistNtfyEnabled: Boolean = false,
    val isUpdatingWatchlistNtfy: Boolean = false,
    val isGeneratingNewsDigest: Boolean = false,
    val digestLastGeneratedAt: String = "",
    val aiInsightText: String = "",
    val errorMessage: String = "",
    val statusMessage: String = "",
)
