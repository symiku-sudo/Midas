from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.schemas import BilibiliSummaryData
from app.services.asr import ASRService
from app.services.audio_fetcher import AudioFetcher
from app.services.comment_insights import CommentInsightService, CommentSnippet
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

_VALID_HOSTS = {"www.bilibili.com", "bilibili.com", "b23.tv", "www.b23.tv"}
_BVID_PATTERN = re.compile(r"(?i)^bv[0-9a-z]{10}$")
_BVID_IN_TEXT_PATTERN = re.compile(r"(?i)(bv[0-9a-z]{10})")
_BILIBILI_VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
_BILIBILI_REPLY_URL = "https://api.bilibili.com/x/v2/reply/main"


def _normalize_bilibili_video_url(video_url: str) -> str:
    candidate = video_url.strip()
    if _BVID_PATTERN.fullmatch(candidate):
        return f"https://www.bilibili.com/video/BV{candidate[2:]}"
    return candidate


class BilibiliSummarizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fetcher = AudioFetcher(settings)
        self._asr = ASRService(settings)
        self._llm = LLMService(settings)
        self._comment_insights = CommentInsightService(settings, llm_service=self._llm)

    async def summarize(self, video_url: str) -> BilibiliSummaryData:
        normalized_video_url = _normalize_bilibili_video_url(video_url)
        self._validate_url(normalized_video_url)

        start = time.perf_counter()
        base_temp = Path(self._settings.runtime.temp_dir)
        job_dir = base_temp / f"bili-{uuid.uuid4().hex}"
        job_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Offload blocking download/ASR work to a worker thread, so /health
            # and other requests remain responsive during long Bilibili jobs.
            audio_path = await asyncio.to_thread(
                self._fetcher.fetch_audio, normalized_video_url, job_dir
            )
            transcript = await asyncio.to_thread(self._asr.transcribe, audio_path)
            try:
                summary_md = await self._llm.summarize(
                    transcript=transcript, video_url=normalized_video_url
                )
            except AppError as exc:
                if exc.code not in {ErrorCode.UPSTREAM_ERROR, ErrorCode.RATE_LIMITED}:
                    raise
                logger.warning(
                    "LLM summarize failed, fallback to local summary: code=%s message=%s",
                    exc.code.value,
                    exc.message,
                )
                summary_md = self._build_local_fallback_summary(
                    video_url=normalized_video_url,
                    transcript=transcript,
                    reason=exc.message,
                )
            summary_md = await self._append_comment_insights(
                summary_markdown=summary_md,
                video_url=normalized_video_url,
            )
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("Bilibili summarize done, elapsed_ms=%d", elapsed_ms)
        return BilibiliSummaryData(
            video_url=normalized_video_url,
            summary_markdown=summary_md,
            elapsed_ms=elapsed_ms,
            transcript_chars=len(transcript),
        )

    def _build_local_fallback_summary(
        self, *, video_url: str, transcript: str, reason: str
    ) -> str:
        preview = transcript[:600].strip()
        return (
            "# B站视频总结（本地降级）\n\n"
            f"- 视频链接：{video_url}\n"
            f"- 转写字数：{len(transcript)}\n"
            f"- 降级原因：{reason}\n\n"
            "## 摘要\n\n"
            "LLM 上游调用失败，当前返回基于转写文本的本地降级结果。\n\n"
            "## 转写片段\n\n"
            f"> {preview}\n"
        )

    def _validate_url(self, video_url: str) -> None:
        parsed = urlparse(video_url)
        if parsed.scheme not in {"http", "https"}:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="视频链接必须以 http:// 或 https:// 开头。",
                status_code=400,
            )
        if parsed.netloc not in _VALID_HOSTS:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="当前仅支持 bilibili.com 或 b23.tv 链接。",
                status_code=400,
            )

    async def _append_comment_insights(
        self,
        *,
        summary_markdown: str,
        video_url: str,
    ) -> str:
        if not self._settings.comment_insights.enabled:
            return summary_markdown

        comments = await self._fetch_comment_snippets(video_url)
        section = await self._comment_insights.build_insight_section(
            platform="bilibili",
            source_title="",
            source_url=video_url,
            comments=comments,
        )
        return self._comment_insights.append_section(
            summary_markdown=summary_markdown,
            section_markdown=section,
        )

    async def _fetch_comment_snippets(self, video_url: str) -> list[CommentSnippet]:
        bvid = self._extract_bvid(video_url)
        if not bvid:
            return []

        timeout = max(int(self._settings.comment_insights.request_timeout_seconds), 1)
        max_fetch = max(int(self._settings.comment_insights.max_comments_fetch), 1)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                aid = await self._fetch_video_aid(client=client, bvid=bvid)
                if aid <= 0:
                    return []
                response = await client.get(
                    _BILIBILI_REPLY_URL,
                    params={
                        "mode": 3,
                        "next": 0,
                        "type": 1,
                        "oid": aid,
                        "ps": max_fetch,
                    },
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError:
            logger.warning("Fetch bilibili comments failed: network error")
            return []

        if response.status_code >= 400:
            logger.warning(
                "Fetch bilibili comments failed: status=%s",
                response.status_code,
            )
            return []
        try:
            payload = response.json()
        except ValueError:
            return []

        if not isinstance(payload, dict):
            return []
        if int(payload.get("code", 0) or 0) != 0:
            return []

        data = payload.get("data")
        if not isinstance(data, dict):
            return []
        raw_replies = data.get("replies")
        if not isinstance(raw_replies, list):
            return []

        output: list[CommentSnippet] = []
        seen_text: set[str] = set()
        for raw in raw_replies:
            if not isinstance(raw, dict):
                continue
            content = raw.get("content")
            if not isinstance(content, dict):
                continue
            text = str(content.get("message", "")).strip()
            if not text:
                continue
            normalized_key = re.sub(r"\s+", " ", text).strip().lower()
            if not normalized_key or normalized_key in seen_text:
                continue
            seen_text.add(normalized_key)
            like_count = raw.get("like", 0)
            if isinstance(like_count, bool):
                like_count = int(like_count)
            elif isinstance(like_count, (int, float)):
                like_count = int(like_count)
            elif isinstance(like_count, str) and like_count.strip().isdigit():
                like_count = int(like_count.strip())
            else:
                like_count = 0
            output.append(
                CommentSnippet(
                    text=text,
                    like_count=max(int(like_count), 0),
                )
            )
            if len(output) >= max_fetch:
                break
        output.sort(key=lambda item: item.like_count, reverse=True)
        return output

    async def _fetch_video_aid(self, *, client: httpx.AsyncClient, bvid: str) -> int:
        try:
            response = await client.get(
                _BILIBILI_VIEW_URL,
                params={"bvid": bvid},
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError:
            return 0
        if response.status_code >= 400:
            return 0
        try:
            payload = response.json()
        except ValueError:
            return 0
        if not isinstance(payload, dict):
            return 0
        if int(payload.get("code", 0) or 0) != 0:
            return 0
        data = payload.get("data")
        if not isinstance(data, dict):
            return 0
        aid = data.get("aid", 0)
        if isinstance(aid, bool):
            return 0
        if isinstance(aid, (int, float)):
            return max(int(aid), 0)
        if isinstance(aid, str) and aid.strip().isdigit():
            return max(int(aid.strip()), 0)
        return 0

    def _extract_bvid(self, video_url: str) -> str:
        matched = _BVID_IN_TEXT_PATTERN.search(video_url.strip())
        if matched is None:
            return ""
        raw = matched.group(1)
        return f"BV{raw[2:]}"
