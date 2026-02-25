from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.schemas import BilibiliSummaryData
from app.services.asr import ASRService
from app.services.audio_fetcher import AudioFetcher
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

_VALID_HOSTS = {"www.bilibili.com", "bilibili.com", "b23.tv", "www.b23.tv"}
_BVID_PATTERN = re.compile(r"(?i)^bv[0-9a-z]{10}$")


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
