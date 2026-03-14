package com.midas.client.data.repo

import android.content.Context
import androidx.core.content.edit
import com.midas.client.data.network.ServerAuthState
import com.midas.client.util.UrlNormalizer
import org.json.JSONArray
import org.json.JSONObject

class SettingsRepository(context: Context) {
    data class AssetSnapshotRecord(
        val id: String,
        val savedAt: String,
        val totalAmountWan: Double,
        val amounts: Map<String, Double>,
    )

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

    fun getAssetSnapshotHistory(): List<AssetSnapshotRecord> {
        val raw = prefs.getString(KEY_ASSET_SNAPSHOT_HISTORY, "") ?: ""
        if (raw.isBlank()) {
            return emptyList()
        }
        return runCatching {
            val result = mutableListOf<AssetSnapshotRecord>()
            val historyArray = JSONArray(raw)
            for (index in 0 until historyArray.length()) {
                val item = historyArray.optJSONObject(index) ?: continue
                val id = item.optString("id", "").trim()
                val savedAt = item.optString("saved_at", "").trim()
                if (id.isBlank() || savedAt.isBlank()) {
                    continue
                }
                val amountsJson = item.optJSONObject("amounts") ?: JSONObject()
                val amounts = parseAmountMap(amountsJson)
                val totalRaw = item.optDouble("total_amount_wan", Double.NaN)
                val total = if (!totalRaw.isNaN() && totalRaw.isFinite() && totalRaw >= 0.0) {
                    totalRaw
                } else {
                    amounts.values.sum()
                }
                result += AssetSnapshotRecord(
                    id = id,
                    savedAt = savedAt,
                    totalAmountWan = total,
                    amounts = amounts,
                )
            }
            result.toList()
        }.getOrDefault(emptyList())
    }

    fun saveAssetSnapshotHistory(records: List<AssetSnapshotRecord>) {
        val array = JSONArray()
        records.forEach { record ->
            if (record.id.isBlank() || record.savedAt.isBlank()) {
                return@forEach
            }
            val amountsJson = JSONObject()
            record.amounts.forEach { (key, amount) ->
                if (amount.isFinite() && amount >= 0.0) {
                    amountsJson.put(key, amount)
                }
            }
            val item = JSONObject()
            item.put("id", record.id)
            item.put("saved_at", record.savedAt)
            item.put("total_amount_wan", record.totalAmountWan)
            item.put("amounts", amountsJson)
            array.put(item)
        }
        prefs.edit {
            putString(KEY_ASSET_SNAPSHOT_HISTORY, array.toString())
        }
    }

    private fun parseAmountMap(json: JSONObject): Map<String, Double> {
        val result = linkedMapOf<String, Double>()
        val keys = json.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            val amount = json.optDouble(key, Double.NaN)
            if (!amount.isNaN() && amount.isFinite() && amount >= 0.0) {
                result[key] = amount
            }
        }
        return result.toMap()
    }

    companion object {
        private const val PREFS_NAME = "midas_client_prefs"
        private const val KEY_SERVER_BASE_URL = "server_base_url"
        private const val KEY_SERVER_ACCESS_TOKEN = "server_access_token"
        private const val KEY_ASSET_CATEGORY_AMOUNTS = "asset_category_amounts"
        private const val KEY_ASSET_SNAPSHOT_HISTORY = "asset_snapshot_history"
        private const val DEFAULT_SERVER_BASE_URL = "http://100.98.44.5:8000/"
    }
}
