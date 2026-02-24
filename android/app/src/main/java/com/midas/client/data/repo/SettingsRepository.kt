package com.midas.client.data.repo

import android.content.Context
import androidx.core.content.edit
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

    companion object {
        private const val PREFS_NAME = "midas_client_prefs"
        private const val KEY_SERVER_BASE_URL = "server_base_url"
        private const val DEFAULT_SERVER_BASE_URL = "http://10.0.2.2:8000/"
    }
}
