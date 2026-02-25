package com.midas.client.util

import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import kotlin.math.floor

enum class ConfigFieldType {
    BOOLEAN,
    STRING,
    INTEGER,
    DECIMAL,
    LIST_JSON,
    NULL,
}

data class EditableConfigField(
    val path: String,
    val type: ConfigFieldType,
    val textValue: String = "",
    val boolValue: Boolean = false,
)

object EditableConfigFormMapper {
    private val listAnyType = Types.newParameterizedType(List::class.java, Any::class.java)
    private val listAdapter = Moshi.Builder().build().adapter<List<Any?>>(listAnyType)

    fun flatten(settings: Map<String, Any?>): List<EditableConfigField> {
        val fields = mutableListOf<EditableConfigField>()
        collectFields(prefix = "", value = settings, output = fields)
        return fields
    }

    fun updateText(
        fields: List<EditableConfigField>,
        path: String,
        text: String,
    ): List<EditableConfigField> {
        return fields.map { field ->
            if (field.path == path) {
                field.copy(textValue = text)
            } else {
                field
            }
        }
    }

    fun updateBoolean(
        fields: List<EditableConfigField>,
        path: String,
        value: Boolean,
    ): List<EditableConfigField> {
        return fields.map { field ->
            if (field.path == path) {
                field.copy(boolValue = value)
            } else {
                field
            }
        }
    }

    fun buildPayload(fields: List<EditableConfigField>): Map<String, Any?> {
        val payload = linkedMapOf<String, Any?>()
        for (field in fields) {
            setByPath(payload, field.path, parseFieldValue(field))
        }
        return payload
    }

    fun validateField(field: EditableConfigField): String? {
        return runCatching {
            parseFieldValue(field)
            null
        }.getOrElse { throwable ->
            throwable.message ?: "字段 ${field.path} 配置格式错误。"
        }
    }

    private fun collectFields(
        prefix: String,
        value: Any?,
        output: MutableList<EditableConfigField>,
    ) {
        when (value) {
            is Map<*, *> -> {
                val keys = value.keys
                    .filterIsInstance<String>()
                    .sorted()
                for (key in keys) {
                    val nestedPath = if (prefix.isBlank()) key else "$prefix.$key"
                    collectFields(prefix = nestedPath, value = value[key], output = output)
                }
            }

            is Boolean -> {
                output.add(
                    EditableConfigField(
                        path = prefix,
                        type = ConfigFieldType.BOOLEAN,
                        boolValue = value,
                    )
                )
            }

            is Number -> {
                if (isIntegralNumber(value)) {
                    output.add(
                        EditableConfigField(
                            path = prefix,
                            type = ConfigFieldType.INTEGER,
                            textValue = toIntegralString(value),
                        )
                    )
                } else {
                    output.add(
                        EditableConfigField(
                            path = prefix,
                            type = ConfigFieldType.DECIMAL,
                            textValue = value.toString(),
                        )
                    )
                }
            }

            is List<*> -> {
                @Suppress("UNCHECKED_CAST")
                val listValue = value as List<Any?>
                output.add(
                    EditableConfigField(
                        path = prefix,
                        type = ConfigFieldType.LIST_JSON,
                        textValue = listAdapter.toJson(listValue),
                    )
                )
            }

            null -> {
                output.add(
                    EditableConfigField(
                        path = prefix,
                        type = ConfigFieldType.NULL,
                        textValue = "",
                    )
                )
            }

            else -> {
                output.add(
                    EditableConfigField(
                        path = prefix,
                        type = ConfigFieldType.STRING,
                        textValue = value.toString(),
                    )
                )
            }
        }
    }

    private fun parseFieldValue(field: EditableConfigField): Any? {
        val trimmed = field.textValue.trim()
        return when (field.type) {
            ConfigFieldType.BOOLEAN -> field.boolValue
            ConfigFieldType.STRING -> field.textValue
            ConfigFieldType.INTEGER -> {
                if (trimmed.isEmpty()) {
                    throw IllegalArgumentException("字段 ${field.path} 不能为空。")
                }
                trimmed.toLongOrNull()
                    ?: throw IllegalArgumentException("字段 ${field.path} 必须是整数。")
            }

            ConfigFieldType.DECIMAL -> {
                if (trimmed.isEmpty()) {
                    throw IllegalArgumentException("字段 ${field.path} 不能为空。")
                }
                trimmed.toDoubleOrNull()
                    ?: throw IllegalArgumentException("字段 ${field.path} 必须是数字。")
            }

            ConfigFieldType.LIST_JSON -> {
                if (trimmed.isEmpty()) {
                    emptyList<Any?>()
                } else {
                    val parsed = try {
                        listAdapter.fromJson(trimmed)
                    } catch (exc: Exception) {
                        throw IllegalArgumentException(
                            "字段 ${field.path} 必须是 JSON 数组，例如 [\"a\",\"b\"]。",
                            exc,
                        )
                    }
                    parsed ?: throw IllegalArgumentException(
                        "字段 ${field.path} 必须是 JSON 数组，例如 [\"a\",\"b\"]。",
                    )
                }
            }

            ConfigFieldType.NULL -> {
                if (trimmed.isEmpty()) null else field.textValue
            }
        }
    }

    private fun isIntegralNumber(value: Number): Boolean {
        return when (value) {
            is Byte, is Short, is Int, is Long -> true
            is Float -> value.isFinite() && floor(value.toDouble()) == value.toDouble()
            is Double -> value.isFinite() && floor(value) == value
            else -> false
        }
    }

    private fun toIntegralString(value: Number): String {
        return when (value) {
            is Byte, is Short, is Int, is Long -> value.toLong().toString()
            is Float -> value.toLong().toString()
            is Double -> value.toLong().toString()
            else -> value.toLong().toString()
        }
    }

    private fun setByPath(
        payload: MutableMap<String, Any?>,
        path: String,
        value: Any?,
    ) {
        val parts = path.split(".")
        var current: MutableMap<String, Any?> = payload
        for (part in parts.dropLast(1)) {
            val child = current[part]
            if (child is MutableMap<*, *>) {
                @Suppress("UNCHECKED_CAST")
                current = child as MutableMap<String, Any?>
            } else {
                val next = linkedMapOf<String, Any?>()
                current[part] = next
                current = next
            }
        }
        current[parts.last()] = value
    }
}
