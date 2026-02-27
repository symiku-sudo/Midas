from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一个中文知识整理助手。"
    "请把输入转写整理成结构化 Markdown。"
    "首行必须是一级标题（# 标题），标题要简短具体，建议不超过18个字。"
    "标题禁止使用“这是一份关于……的知识整理”这类模板句。"
    "如需使用该句式，只能放在摘要首句。"
    "正文输出包含：一段摘要、要点列表、可执行建议。"
)

_XHS_PROMPT = (
    "你是一个中文信息提炼助手。"
    "请把输入的小红书笔记整理成 Markdown，输出包含：摘要、关键要点、可执行建议。"
    "严格基于提供的正文，不得根据标题臆测。"
    "若提供了配图，请结合图文共同总结，不可忽略图片信息。"
    "如果信息不足，请明确写出“信息不足”，不要编造细节。"
)

_XHS_VIDEO_PROMPT = (
    "你是一个中文信息提炼助手。"
    "请把输入的小红书视频笔记整理成 Markdown，输出包含：摘要、关键要点、可执行建议。"
    "必须结合视频转写文本与笔记正文（若有），不能遗漏任一来源。"
    "如果视频转写与正文信息冲突，请明确标注冲突点。"
    "如果信息不足，请明确写出“信息不足”，不要编造细节。"
)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _normalize_image_urls(self, image_urls: list[str] | None) -> list[str]:
        return [
            item.strip()
            for item in (image_urls or [])
            if isinstance(item, str) and item.strip().startswith(("http://", "https://"))
        ]

    def _build_multimodal_user_content(
        self,
        user_text: str,
        image_urls: list[str],
    ) -> list[dict[str, Any]]:
        user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for image_url in image_urls:
            user_content.append(
                {"type": "image_url", "image_url": {"url": image_url}}
            )
        return user_content

    def _chat_completions_url(self) -> str:
        return f"{self._settings.llm.api_base.rstrip('/')}/chat/completions"

    def _require_api_key(self) -> str:
        api_key = self._settings.llm.api_key
        if api_key:
            return api_key
        raise AppError(
            code=ErrorCode.INVALID_INPUT,
            message="LLM 已启用但缺少 api_key 配置。",
            status_code=400,
        )

    def _build_auth_headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _request_chat_completion(
        self,
        payload: dict[str, Any],
        *,
        api_key: str,
        server_error_message: str | None = None,
    ) -> str:
        url = self._chat_completions_url()
        headers = self._build_auth_headers(api_key)
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
        if server_error_message and resp.status_code >= 500:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=server_error_message,
                status_code=502,
            )
        if resp.status_code >= 400:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=f"LLM 请求失败（HTTP {resp.status_code}）。",
                status_code=502,
            )

        raw = resp.json()
        result = self._extract_response_text(raw)
        if not result:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 未返回有效内容。",
                status_code=502,
            )
        return result

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

        api_key = self._require_api_key()
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
        logger.info("Request LLM summarize, model=%s", self._settings.llm.model)
        return await self._request_chat_completion(
            payload,
            api_key=api_key,
            server_error_message="LLM 上游服务异常。",
        )

    async def summarize_xiaohongshu_note(
        self,
        *,
        note_id: str,
        title: str,
        content: str,
        source_url: str,
        image_urls: list[str] | None = None,
    ) -> str:
        normalized_image_urls = self._normalize_image_urls(image_urls)
        if not self._settings.llm.enabled:
            preview = content[:300].strip()
            image_section = ""
            if normalized_image_urls:
                image_lines = "\n".join(
                    f"- [配图{i + 1}]({url})"
                    for i, url in enumerate(normalized_image_urls[:6])
                )
                image_section = f"\n## 配图链接\n\n{image_lines}\n"
            return (
                f"# 小红书笔记总结：{title}\n\n"
                f"- 笔记ID：{note_id}\n"
                f"- 来源：{source_url}\n\n"
                "## 摘要\n\n"
                "当前为本地降级输出（未启用 LLM）。\n\n"
                "## 内容片段\n\n"
                f"> {preview}\n"
                f"{image_section}"
            )

        api_key = self._require_api_key()
        user_text = (
            f"笔记ID: {note_id}\n"
            f"标题: {title}\n"
            f"来源: {source_url}\n\n"
            f"正文:\n{content}\n\n"
            f"配图数量: {len(normalized_image_urls)}"
        )
        user_content = self._build_multimodal_user_content(
            user_text=user_text,
            image_urls=normalized_image_urls,
        )

        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _XHS_PROMPT},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        }
        return await self._request_chat_completion(payload, api_key=api_key)

    async def summarize_xiaohongshu_video_note(
        self,
        *,
        note_id: str,
        title: str,
        content: str,
        transcript: str,
        source_url: str,
        image_urls: list[str] | None = None,
    ) -> str:
        normalized_image_urls = self._normalize_image_urls(image_urls)
        content_text = content.strip() or "（无正文）"
        transcript_text = transcript.strip()
        if not transcript_text:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="视频转写为空，无法生成视频笔记总结。",
                status_code=502,
            )

        if not self._settings.llm.enabled:
            preview = transcript_text[:400]
            return (
                f"# 小红书视频笔记总结：{title}\n\n"
                f"- 笔记ID：{note_id}\n"
                f"- 来源：{source_url}\n\n"
                "## 正文补充\n\n"
                f"{content_text}\n\n"
                "## 视频转写片段\n\n"
                f"> {preview}\n"
            )

        api_key = self._require_api_key()
        user_text = (
            f"笔记ID: {note_id}\n"
            f"标题: {title}\n"
            f"来源: {source_url}\n\n"
            f"正文:\n{content_text}\n\n"
            f"视频转写:\n{transcript_text}\n\n"
            f"配图数量: {len(normalized_image_urls)}"
        )
        user_content = self._build_multimodal_user_content(
            user_text=user_text,
            image_urls=normalized_image_urls,
        )

        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _XHS_VIDEO_PROMPT},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        }
        return await self._request_chat_completion(payload, api_key=api_key)

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 响应结构异常。",
                status_code=502,
            ) from exc

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text = item["text"].strip()
                    if text:
                        chunks.append(text)
            return "\n".join(chunks).strip()

        return ""
