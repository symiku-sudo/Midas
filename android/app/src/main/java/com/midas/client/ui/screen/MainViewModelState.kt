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

data class HomeUiState(
    val isLoading: Boolean = false,
    val generatedAt: String = "",
    val recentTasks: List<AsyncJobListItemData> = emptyList(),
    val recentNotes: List<UnifiedNoteItem> = emptyList(),
    val financeFocusCards: List<FinanceFocusCard> = emptyList(),
    val quickLinks: List<HomeQuickLinkItemUi> = emptyList(),
    val assetTotalAmountWan: Double = 0.0,
    val errorMessage: String = "",
)

data class HomeQuickLinkItemUi(
    val target: String,
    val title: String,
    val subtitle: String = "",
)

data class AssetCategoryDraft(
    val key: String,
    val label: String,
    val amountInput: String = "",
)

data class AssetHistoryRecord(
    val id: String,
    val savedAt: String,
    val totalAmountWan: Double,
    val amounts: Map<String, Double>,
)

internal data class AssetCategorySpec(
    val key: String,
    val label: String,
)

internal val assetCategorySpecs = listOf(
    AssetCategorySpec(key = "stock", label = "股票"),
    AssetCategorySpec(key = "equity_fund", label = "股票基金"),
    AssetCategorySpec(key = "gold", label = "黄金"),
    AssetCategorySpec(key = "bond_and_bond_fund", label = "债券/债券基金"),
    AssetCategorySpec(key = "money_market_fund", label = "货币基金"),
    AssetCategorySpec(key = "bank_fixed_deposit", label = "银行定期存款"),
    AssetCategorySpec(key = "bank_current_deposit", label = "银行活期存款"),
    AssetCategorySpec(key = "housing_fund", label = "公积金"),
)

internal const val MAX_ASSET_IMAGE_UPLOAD = 5
internal const val ASYNC_JOB_POLL_INTERVAL_MS = 1500L
internal const val ASYNC_JOB_POLL_MAX_ATTEMPTS = 800
internal const val XIAOHONGSHU_CAPTURE_JOB_TYPE = "xiaohongshu_summarize_url"

internal fun defaultAssetDrafts(): List<AssetCategoryDraft> {
    return assetCategorySpecs.map { spec ->
        AssetCategoryDraft(
            key = spec.key,
            label = spec.label,
            amountInput = "",
        )
    }
}

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
    val assetDrafts: List<AssetCategoryDraft> = defaultAssetDrafts(),
    val assetTotalAmount: Double = 0.0,
    val isSavingAssetStats: Boolean = false,
    val isFillingAssetFromImages: Boolean = false,
    val assetErrorMessage: String = "",
    val assetStatusMessage: String = "",
    val assetHistory: List<AssetHistoryRecord> = emptyList(),
    val errorMessage: String = "",
    val statusMessage: String = "",
)
