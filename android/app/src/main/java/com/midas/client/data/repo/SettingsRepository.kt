package com.midas.client.data.repo

import android.content.Context
import androidx.core.content.edit
import com.midas.client.data.network.ServerAuthState
import com.midas.client.util.UrlNormalizer

class SettingsRepository(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getServerBaseUrl(): String {
        val saved = prefs.getString(KEY_SERVER_BASE_URL, DEFAULT_SERVER_BASE_URL) ?: DEFAULT_SERVER_BASE_URL
        return UrlNormalizer.normalize(saved)
    }

    fun saveServerBaseUrl(url: String): String {
        val normalized = UrlNormalizer.normalize(url)
        prefs.edit {
            putString(KEY_SERVER_BASE_URL, normalized)
        }
        return normalized
    }

    fun getServerAccessToken(): String {
        return prefs.getString(KEY_SERVER_ACCESS_TOKEN, "")?.trim().orEmpty()
    }

    fun saveServerAccessToken(token: String): String {
        val normalized = token.trim()
        prefs.edit {
            putString(KEY_SERVER_ACCESS_TOKEN, normalized)
        }
        ServerAuthState.updateAccessToken(normalized)
        return normalized
    }

    fun getDismissedFinanceFocusCardKeys(): Set<String> {
        return prefs.getStringSet(KEY_DISMISSED_FINANCE_FOCUS_CARDS, emptySet())
            ?.map { it.trim() }
            ?.filter { it.isNotEmpty() }
            ?.toSet()
            .orEmpty()
    }

    fun saveDismissedFinanceFocusCardKeys(keys: Set<String>) {
        prefs.edit {
            putStringSet(
                KEY_DISMISSED_FINANCE_FOCUS_CARDS,
                keys.map { it.trim() }.filter { it.isNotEmpty() }.toSet(),
            )
        }
    }

    companion object {
        private const val PREFS_NAME = "midas_client_prefs"
        private const val KEY_SERVER_BASE_URL = "server_base_url"
        private const val KEY_SERVER_ACCESS_TOKEN = "server_access_token"
        private const val KEY_DISMISSED_FINANCE_FOCUS_CARDS = "dismissed_finance_focus_cards"
        private const val DEFAULT_SERVER_BASE_URL = "http://100.98.44.5:8000/"
    }
}
