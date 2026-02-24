from __future__ import annotations

import logging

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一个中文知识整理助手。"
    "请把输入转写整理成结构化 Markdown，输出包含：一段摘要、要点列表、可执行建议。"
)

_XHS_PROMPT = (
    "你是一个中文信息提炼助手。"
    "请把输入的小红书笔记整理成 Markdown，输出包含：摘要、关键要点、可执行建议。"
)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def summarize(self, transcript: str, video_url: str) -> str:
        if not self._settings.llm.enabled:
            logger.info("LLM disabled, return deterministic local summary")
            preview = transcript[:400].strip()
            return (
                "# B站视频总结（本地降级）\n\n"
                f"- 视频链接：{video_url}\n"
                f"- 转写字数：{len(transcript)}\n\n"
                "## 摘要\n\n"
                "当前为本地降级输出（未启用 LLM）。\n\n"
                "## 转写片段\n\n"
                f"> {preview}\n"
            )

        if not self._settings.llm.api_key:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="LLM 已启用但缺少 api_key 配置。",
                status_code=400,
            )

        url = f"{self._settings.llm.api_base.rstrip('/')}/chat/completions"
        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"视频链接: {video_url}\n\n转写文本:\n{transcript}",
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._settings.llm.api_key}",
            "Content-Type": "application/json",
        }

        logger.info("Request LLM summarize, model=%s", self._settings.llm.model)
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.llm.timeout_seconds
            ) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 服务连接失败。",
                status_code=502,
            ) from exc

        if resp.status_code in {401, 403}:
            raise AppError(
                code=ErrorCode.AUTH_EXPIRED,
                message="LLM 鉴权失败，请检查 API Key。",
                status_code=401,
            )
        if resp.status_code == 429:
            raise AppError(
                code=ErrorCode.RATE_LIMITED,
                message="LLM 请求触发限流，请稍后重试。",
                status_code=429,
            )
        if resp.status_code >= 500:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 上游服务异常。",
                status_code=502,
            )
        if resp.status_code >= 400:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=f"LLM 请求失败（HTTP {resp.status_code}）。",
                status_code=502,
            )

        raw = resp.json()
        try:
            content = raw["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 响应结构异常。",
                status_code=502,
            ) from exc

        if not content:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 未返回有效内容。",
                status_code=502,
            )

        return content

    async def summarize_xiaohongshu_note(
        self,
        *,
        note_id: str,
        title: str,
        content: str,
        source_url: str,
    ) -> str:
        if not self._settings.llm.enabled:
            preview = content[:300].strip()
            return (
                f"# 小红书笔记总结：{title}\n\n"
                f"- 笔记ID：{note_id}\n"
                f"- 来源：{source_url}\n\n"
                "## 摘要\n\n"
                "当前为本地降级输出（未启用 LLM）。\n\n"
                "## 内容片段\n\n"
                f"> {preview}\n"
            )

        if not self._settings.llm.api_key:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="LLM 已启用但缺少 api_key 配置。",
                status_code=400,
            )

        url = f"{self._settings.llm.api_base.rstrip('/')}/chat/completions"
        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _XHS_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"笔记ID: {note_id}\n"
                        f"标题: {title}\n"
                        f"来源: {source_url}\n\n"
                        f"正文:\n{content}"
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._settings.llm.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.llm.timeout_seconds
            ) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 服务连接失败。",
                status_code=502,
            ) from exc

        if resp.status_code in {401, 403}:
            raise AppError(
                code=ErrorCode.AUTH_EXPIRED,
                message="LLM 鉴权失败，请检查 API Key。",
                status_code=401,
            )
        if resp.status_code == 429:
            raise AppError(
                code=ErrorCode.RATE_LIMITED,
                message="LLM 请求触发限流，请稍后重试。",
                status_code=429,
            )
        if resp.status_code >= 400:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=f"LLM 请求失败（HTTP {resp.status_code}）。",
                status_code=502,
            )

        raw = resp.json()
        try:
            result = raw["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 响应结构异常。",
                status_code=502,
            ) from exc

        if not result:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 未返回有效内容。",
                status_code=502,
            )

        return result
