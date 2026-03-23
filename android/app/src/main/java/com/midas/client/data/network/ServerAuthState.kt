package com.midas.client.data.network

object ServerAuthState {
    @Volatile
    private var accessToken: String = ""

    fun updateAccessToken(token: String) {
        accessToken = token.trim()
    }

    fun currentAccessToken(): String = accessToken
}
