package com.midas.client.data.repo

import android.content.Context
import androidx.core.content.edit
import com.midas.client.util.UrlNormalizer
import org.json.JSONObject

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

    fun getAssetCategoryAmounts(): Map<String, Double> {
        val raw = prefs.getString(KEY_ASSET_CATEGORY_AMOUNTS, "") ?: ""
        if (raw.isBlank()) {
            return emptyMap()
        }
        return runCatching {
            val json = JSONObject(raw)
            val result = linkedMapOf<String, Double>()
            val keys = json.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val amount = json.optDouble(key, Double.NaN)
                if (!amount.isNaN() && amount.isFinite() && amount >= 0.0) {
                    result[key] = amount
                }
            }
            result.toMap()
        }.getOrDefault(emptyMap())
    }

    fun saveAssetCategoryAmounts(amounts: Map<String, Double>) {
        val json = JSONObject()
        amounts.forEach { (key, amount) ->
            if (amount.isFinite() && amount >= 0.0) {
                json.put(key, amount)
            }
        }
        prefs.edit {
            putString(KEY_ASSET_CATEGORY_AMOUNTS, json.toString())
        }
    }

    companion object {
        private const val PREFS_NAME = "midas_client_prefs"
        private const val KEY_SERVER_BASE_URL = "server_base_url"
        private const val KEY_ASSET_CATEGORY_AMOUNTS = "asset_category_amounts"
        private const val DEFAULT_SERVER_BASE_URL = "http://100.98.44.5:8000/"
    }
}
