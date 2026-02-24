package com.midas.client.util

object UrlNormalizer {
    fun normalize(input: String): String {
        var url = input.trim()
        if (url.isEmpty()) {
            return ""
        }
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "http://$url"
        }
        if (!url.endsWith("/")) {
            url += "/"
        }
        return url
    }
}
