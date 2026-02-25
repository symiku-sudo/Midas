package com.midas.client.util

enum class ErrorContext {
    CONNECTION,
    CONFIG,
    BILIBILI,
    XIAOHONGSHU_SYNC,
    XIAOHONGSHU_JOB,
}

object ErrorMessageMapper {
    fun format(code: String, message: String, context: ErrorContext): String {
        val normalizedCode = code.trim().uppercase()
        val normalizedMessage = message.trim()

        val hint = when (normalizedCode) {
            "NETWORK_ERROR" -> "无法连接服务端，请检查地址、端口与局域网连通性。"
            "AUTH_EXPIRED" -> "鉴权已过期，请重新登录并更新 Cookie 或抓包配置。"
            "RATE_LIMITED" -> "请求过于频繁，请等待后重试，避免连续刷新。"
            "CIRCUIT_OPEN" -> "连续失败触发熔断，本次任务已停止，请先排查配置。"
            "DEPENDENCY_MISSING" -> "服务端依赖缺失，请检查 yt-dlp、ffmpeg、ASR 环境。"
            "UPSTREAM_ERROR" -> when (context) {
                ErrorContext.BILIBILI -> "上游处理失败，请检查视频可访问性与服务端日志。"
                ErrorContext.XIAOHONGSHU_SYNC, ErrorContext.XIAOHONGSHU_JOB -> "小红书上游响应异常，请检查抓包字段映射。"
                ErrorContext.CONFIG -> "配置服务响应异常，请稍后重试。"
                ErrorContext.CONNECTION -> "服务端响应异常，请稍后重试。"
            }

            "INTERNAL_ERROR" -> "服务端发生未预期错误，请查看服务端日志。"
            "INVALID_INPUT" -> invalidInputHint(normalizedMessage, context)
            else -> "请求失败，请稍后重试。"
        }

        val detail = if (normalizedMessage.isNotBlank()) normalizedMessage else "无详细错误信息"
        return "$hint\n[$normalizedCode] $detail"
    }

    private fun invalidInputHint(message: String, context: ErrorContext): String {
        if (
            (context == ErrorContext.XIAOHONGSHU_SYNC || context == ErrorContext.XIAOHONGSHU_JOB) &&
            message.contains("confirm_live", ignoreCase = true)
        ) {
            return "当前真实同步受保护，请先打开“确认真实同步请求”开关。"
        }

        return when (context) {
            ErrorContext.CONNECTION -> "服务端地址或请求参数不合法。"
            ErrorContext.CONFIG -> "配置内容不合法，请检查字段值。"
            ErrorContext.BILIBILI -> "输入链接无效，请使用 bilibili.com 或 b23.tv 链接。"
            ErrorContext.XIAOHONGSHU_SYNC, ErrorContext.XIAOHONGSHU_JOB -> "同步参数不合法，请检查同步数量和配置。"
        }
    }
}
