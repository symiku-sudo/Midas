package com.midas.client.util

sealed class AppResult<out T> {
    data class Success<T>(val data: T) : AppResult<T>()
    data class Error(val code: String, val message: String) : AppResult<Nothing>()
}
