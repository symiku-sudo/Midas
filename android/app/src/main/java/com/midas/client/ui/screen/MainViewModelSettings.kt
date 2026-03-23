package com.midas.client.ui.screen

import androidx.lifecycle.viewModelScope
import com.midas.client.util.AppResult
import com.midas.client.util.EditableConfigFormMapper
import com.midas.client.util.ErrorContext
import com.midas.client.util.ErrorMessageMapper
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

fun MainViewModel.onBaseUrlInputChange(newValue: String) {
    _settingsState.update {
        it.copy(
            baseUrlInput = newValue,
            saveStatus = "",
            testStatus = "",
            configStatus = "",
        )
    }
}

fun MainViewModel.onAccessTokenInputChange(newValue: String) {
    _settingsState.update {
        it.copy(
            accessTokenInput = newValue,
            saveStatus = "",
            testStatus = "",
            configStatus = "",
        )
    }
}

fun MainViewModel.saveBaseUrl() {
    val normalized = settingsRepository.saveServerBaseUrl(_settingsState.value.baseUrlInput)
    val token = settingsRepository.saveServerAccessToken(_settingsState.value.accessTokenInput)
    _settingsState.update {
        it.copy(
            baseUrlInput = normalized,
            accessTokenInput = token,
            saveStatus = if (token.isBlank()) {
                "已保存服务端地址。"
            } else {
                "已保存服务端地址和访问令牌。"
            },
        )
    }
    loadEditableConfig()
    refreshAsyncJobHistories()
    loadFinanceSignals()
    loadAssetCurrent()
    loadAssetSnapshotHistory()
}

fun MainViewModel.testConnection() {
    val baseUrl = normalizeCurrentBaseUrl()
    if (baseUrl.isEmpty()) {
        _settingsState.update { it.copy(testStatus = "请输入服务端地址。") }
        return
    }

    viewModelScope.launch {
        _settingsState.update {
            it.copy(
                isTesting = true,
                testStatus = "正在测试连接...",
            )
        }

        when (val result = apiRepository.testConnection(baseUrl)) {
            is AppResult.Success -> {
                _settingsState.update {
                    it.copy(
                        isTesting = false,
                        testStatus = "连接成功（status=${result.data.status}）",
                    )
                }
            }

            is AppResult.Error -> {
                _settingsState.update {
                    it.copy(
                        isTesting = false,
                        testStatus = "连接失败：${
                            ErrorMessageMapper.format(
                                code = result.code,
                                message = result.message,
                                context = ErrorContext.CONNECTION,
                            )
                        }",
                    )
                }
            }
        }
    }
}

fun MainViewModel.onEditableConfigFieldTextChange(path: String, newValue: String) {
    val updatedFields = EditableConfigFormMapper.updateText(
        fields = _settingsState.value.editableConfigFields,
        path = path,
        text = newValue,
    )
    val error = updatedFields.firstOrNull { it.path == path }
        ?.let { EditableConfigFormMapper.validateField(it) }
    _settingsState.update {
        val nextErrors = it.configFieldErrors.toMutableMap()
        if (error.isNullOrBlank()) {
            nextErrors.remove(path)
        } else {
            nextErrors[path] = error
        }
        it.copy(
            editableConfigFields = updatedFields,
            configFieldErrors = nextErrors,
            configStatus = error ?: "",
        )
    }
    if (error.isNullOrBlank()) {
        scheduleAutoSaveConfig()
    } else {
        autoSaveConfigJob?.cancel()
    }
}

fun MainViewModel.onEditableConfigFieldBooleanChange(path: String, newValue: Boolean) {
    val updatedFields = EditableConfigFormMapper.updateBoolean(
        fields = _settingsState.value.editableConfigFields,
        path = path,
        value = newValue,
    )
    val error = updatedFields.firstOrNull { it.path == path }
        ?.let { EditableConfigFormMapper.validateField(it) }
    _settingsState.update {
        val nextErrors = it.configFieldErrors.toMutableMap()
        if (error.isNullOrBlank()) {
            nextErrors.remove(path)
        } else {
            nextErrors[path] = error
        }
        it.copy(
            editableConfigFields = updatedFields,
            configFieldErrors = nextErrors,
            configStatus = error ?: "",
        )
    }
    if (error.isNullOrBlank()) {
        scheduleAutoSaveConfig()
    } else {
        autoSaveConfigJob?.cancel()
    }
}

fun MainViewModel.loadEditableConfig() {
    val baseUrl = requireBaseUrl {
        _settingsState.update {
            it.copy(
                isConfigLoading = false,
                configStatus = "请先填写服务端地址。",
            )
        }
    } ?: return
    viewModelScope.launch {
        _settingsState.update {
            it.copy(
                isConfigLoading = true,
                configStatus = "正在拉取可编辑配置...",
            )
        }

        when (val result = apiRepository.getEditableConfig(baseUrl)) {
            is AppResult.Success -> {
                _settingsState.update {
                    it.copy(
                        isConfigLoading = false,
                        editableConfigFields = EditableConfigFormMapper.flatten(result.data.settings),
                        configFieldErrors = emptyMap(),
                        configStatus = "已拉取可编辑配置。",
                    )
                }
            }

            is AppResult.Error -> {
                _settingsState.update {
                    it.copy(
                        isConfigLoading = false,
                        configFieldErrors = emptyMap(),
                        configStatus = ErrorMessageMapper.format(
                            code = result.code,
                            message = result.message,
                            context = ErrorContext.CONFIG,
                        ),
                    )
                }
            }
        }
    }
}

fun MainViewModel.resetEditableConfig() {
    val baseUrl = requireBaseUrl {
        _settingsState.update {
            it.copy(
                isConfigResetting = false,
                configStatus = "请先填写服务端地址。",
            )
        }
    } ?: return
    autoSaveConfigJob?.cancel()
    viewModelScope.launch {
        _settingsState.update {
            it.copy(
                isConfigResetting = true,
                configStatus = "正在恢复默认配置...",
            )
        }

        when (val result = apiRepository.resetEditableConfig(baseUrl)) {
            is AppResult.Success -> {
                _settingsState.update {
                    it.copy(
                        isConfigResetting = false,
                        editableConfigFields = EditableConfigFormMapper.flatten(result.data.settings),
                        configFieldErrors = emptyMap(),
                        configStatus = "已恢复默认配置。",
                    )
                }
            }

            is AppResult.Error -> {
                _settingsState.update {
                    it.copy(
                        isConfigResetting = false,
                        configStatus = ErrorMessageMapper.format(
                            code = result.code,
                            message = result.message,
                            context = ErrorContext.CONFIG,
                        ),
                    )
                }
            }
        }
    }
}

internal fun MainViewModel.scheduleAutoSaveConfig() {
    autoSaveConfigJob?.cancel()
    autoSaveConfigJob = viewModelScope.launch {
        delay(600)
        val baseUrl = requireBaseUrl {
            _settingsState.update {
                it.copy(
                    isConfigSaving = false,
                    configStatus = "请先填写服务端地址。",
                )
            }
        } ?: return@launch
        val snapshot = _settingsState.value
        if (snapshot.editableConfigFields.isEmpty()) {
            return@launch
        }
        if (snapshot.configFieldErrors.isNotEmpty()) {
            _settingsState.update {
                it.copy(configStatus = "请先修正红色配置项。")
            }
            return@launch
        }

        val parsed = runCatching {
            EditableConfigFormMapper.buildPayload(snapshot.editableConfigFields)
        }.getOrElse { throwable ->
            _settingsState.update {
                it.copy(configStatus = throwable.message ?: "配置格式错误。")
            }
            return@launch
        }

        _settingsState.update {
            it.copy(
                isConfigSaving = true,
                configStatus = "正在自动保存配置...",
            )
        }

        when (val result = apiRepository.updateEditableConfig(baseUrl, parsed)) {
            is AppResult.Success -> {
                _settingsState.update {
                    it.copy(
                        isConfigSaving = false,
                        editableConfigFields = EditableConfigFormMapper.flatten(result.data.settings),
                        configFieldErrors = emptyMap(),
                        configStatus = "配置已自动保存。",
                    )
                }
            }

            is AppResult.Error -> {
                _settingsState.update {
                    it.copy(
                        isConfigSaving = false,
                        configStatus = ErrorMessageMapper.format(
                            code = result.code,
                            message = result.message,
                            context = ErrorContext.CONFIG,
                        ),
                    )
                }
            }
        }
    }
}
