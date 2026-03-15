package com.midas.client.ui.screen

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import com.midas.client.data.network.ServerAuthState
import com.midas.client.data.repo.MidasRepository
import com.midas.client.data.repo.SettingsRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class MainViewModel(application: Application) : AndroidViewModel(application) {
    internal val settingsRepository = SettingsRepository(application)
    internal val apiRepository = MidasRepository()

    internal val _settingsState = MutableStateFlow(
        SettingsUiState(
            baseUrlInput = settingsRepository.getServerBaseUrl(),
            accessTokenInput = settingsRepository.getServerAccessToken(),
        )
    )
    val settingsState: StateFlow<SettingsUiState> = _settingsState.asStateFlow()

    internal val _homeState = MutableStateFlow(HomeUiState())
    val homeState: StateFlow<HomeUiState> = _homeState.asStateFlow()

    internal val _bilibiliState = MutableStateFlow(BilibiliUiState())
    val bilibiliState: StateFlow<BilibiliUiState> = _bilibiliState.asStateFlow()

    internal val _xiaohongshuState = MutableStateFlow(XiaohongshuUiState())
    val xiaohongshuState: StateFlow<XiaohongshuUiState> = _xiaohongshuState.asStateFlow()

    internal val _notesState = MutableStateFlow(NotesUiState())
    val notesState: StateFlow<NotesUiState> = _notesState.asStateFlow()

    internal val _financeState = MutableStateFlow(FinanceSignalsUiState())
    val financeState: StateFlow<FinanceSignalsUiState> = _financeState.asStateFlow()

    internal var autoSaveConfigJob: Job? = null
    internal var financeSignalsJob: Job? = null
    internal var assetCurrentJob: Job? = null
    internal var assetHistoryJob: Job? = null
    internal var notesSearchJob: Job? = null
    internal var bilibiliSummaryJob: Job? = null
    internal var xiaohongshuSummaryJob: Job? = null

    init {
        ServerAuthState.updateAccessToken(settingsRepository.getServerAccessToken())
        loadLocalAssetStats()
        loadEditableConfig()
        loadSavedNotes()
        refreshAsyncJobHistories()
        loadFinanceSignals()
        loadHomeOverview()
        loadAssetCurrent()
        loadAssetSnapshotHistory()
    }

    override fun onCleared() {
        autoSaveConfigJob?.cancel()
        financeSignalsJob?.cancel()
        assetCurrentJob?.cancel()
        assetHistoryJob?.cancel()
        notesSearchJob?.cancel()
        bilibiliSummaryJob?.cancel()
        xiaohongshuSummaryJob?.cancel()
        super.onCleared()
    }
}
