package com.midas.client

import com.midas.client.util.ConfigFieldType
import com.midas.client.util.EditableConfigField
import com.midas.client.util.EditableConfigFormMapper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class EditableConfigFormMapperTest {
    @Test
    fun flattenAndBuildPayload_shouldKeepTypesAndNestedPaths() {
        val settings = linkedMapOf<String, Any?>(
            "llm" to linkedMapOf(
                "enabled" to true,
                "timeout_seconds" to 120,
                "api_base" to "https://example.com",
            ),
            "xiaohongshu" to linkedMapOf(
                "default_limit" to 20,
                "content_field_candidates" to listOf("desc", "content"),
            ),
        )

        val flattened = EditableConfigFormMapper.flatten(settings)
        val enabled = flattened.first { it.path == "llm.enabled" }
        val timeout = flattened.first { it.path == "llm.timeout_seconds" }
        val candidates = flattened.first { it.path == "xiaohongshu.content_field_candidates" }

        assertEquals(ConfigFieldType.BOOLEAN, enabled.type)
        assertTrue(enabled.boolValue)
        assertEquals(ConfigFieldType.INTEGER, timeout.type)
        assertEquals("120", timeout.textValue)
        assertEquals(ConfigFieldType.LIST_JSON, candidates.type)

        val updated = EditableConfigFormMapper.updateBoolean(flattened, "llm.enabled", false)
            .let { EditableConfigFormMapper.updateText(it, "llm.timeout_seconds", "90") }
            .let {
                EditableConfigFormMapper.updateText(
                    it,
                    "xiaohongshu.content_field_candidates",
                    "[\"title\",\"note_content\"]",
                )
            }

        val payload = EditableConfigFormMapper.buildPayload(updated)
        val llm = payload["llm"] as Map<*, *>
        val xhs = payload["xiaohongshu"] as Map<*, *>

        assertFalse(llm["enabled"] as Boolean)
        assertEquals(90L, llm["timeout_seconds"])
        assertEquals(listOf("title", "note_content"), xhs["content_field_candidates"])
    }

    @Test
    fun buildPayload_shouldRejectInvalidInteger() {
        val fields = listOf(
            EditableConfigField(
                path = "xiaohongshu.default_limit",
                type = ConfigFieldType.INTEGER,
                textValue = "abc",
            )
        )

        val exception = runCatching { EditableConfigFormMapper.buildPayload(fields) }.exceptionOrNull()
        assertTrue(exception is IllegalArgumentException)
        assertTrue(exception?.message?.contains("xiaohongshu.default_limit") == true)
    }

    @Test
    fun buildPayload_shouldRejectInvalidListJson() {
        val fields = listOf(
            EditableConfigField(
                path = "xiaohongshu.content_field_candidates",
                type = ConfigFieldType.LIST_JSON,
                textValue = "desc,content",
            )
        )

        val exception = runCatching { EditableConfigFormMapper.buildPayload(fields) }.exceptionOrNull()
        assertTrue(exception is IllegalArgumentException)
        assertTrue(exception?.message?.contains("JSON 数组") == true)
    }

    @Test
    fun validateField_shouldReturnErrorMessageForInvalidNumber() {
        val field = EditableConfigField(
            path = "xiaohongshu.default_limit",
            type = ConfigFieldType.INTEGER,
            textValue = "12a",
        )

        val error = EditableConfigFormMapper.validateField(field)
        assertTrue(error?.contains("xiaohongshu.default_limit") == true)
    }

    @Test
    fun validateField_shouldReturnNullForValidValue() {
        val field = EditableConfigField(
            path = "xiaohongshu.default_limit",
            type = ConfigFieldType.INTEGER,
            textValue = "12",
        )

        val error = EditableConfigFormMapper.validateField(field)
        assertNull(error)
    }
}
