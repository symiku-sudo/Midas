package com.midas.client

import com.midas.client.util.UrlNormalizer
import org.junit.Assert.assertEquals
import org.junit.Test

class UrlNormalizerTest {
    @Test
    fun normalize_shouldAddSchemeAndSlash() {
        assertEquals("http://192.168.1.10:8000/", UrlNormalizer.normalize("192.168.1.10:8000"))
    }

    @Test
    fun normalize_shouldKeepHttps() {
        assertEquals("https://example.com/", UrlNormalizer.normalize("https://example.com"))
    }
}
