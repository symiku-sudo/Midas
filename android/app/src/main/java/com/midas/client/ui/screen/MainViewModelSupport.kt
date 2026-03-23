package com.midas.client.ui.screen

import com.midas.client.data.model.NotesMergeCandidateItem
import com.midas.client.util.UrlNormalizer
import kotlinx.coroutines.flow.update

internal fun MainViewModel.requireBaseUrl(onMissing: () -> Unit): String? {
    val baseUrl = normalizeCurrentBaseUrl()
    if (baseUrl.isNotEmpty()) {
        return baseUrl
    }
    onMissing()
    return null
}

internal fun MainViewModel.normalizeCurrentBaseUrl(): String {
    val normalized = UrlNormalizer.normalize(_settingsState.value.baseUrlInput)
    _settingsState.update { it.copy(baseUrlInput = normalized) }
    return normalized
}

internal fun buildMergeCandidateKey(source: String, noteIds: List<String>): String {
    val normalizedIds = noteIds
        .map { it.trim() }
        .filter { it.isNotEmpty() }
        .sorted()
    return "${source.trim().lowercase()}::${normalizedIds.joinToString("|")}"
}

internal fun filterStrongMergeCandidates(
    candidates: List<NotesMergeCandidateItem>,
): List<NotesMergeCandidateItem> {
    return candidates.filter { it.relationLevel == "STRONG" }
}
