from __future__ import annotations

import logging
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


class BilibiliSummarizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fetcher = AudioFetcher(settings)
        self._asr = ASRService(settings)
        self._llm = LLMService(settings)

    async def summarize(self, video_url: str) -> BilibiliSummaryData:
        self._validate_url(video_url)

        start = time.perf_counter()
        base_temp = Path(self._settings.runtime.temp_dir)
        job_dir = base_temp / f"bili-{uuid.uuid4().hex}"
        job_dir.mkdir(parents=True, exist_ok=True)

        try:
            audio_path = self._fetcher.fetch_audio(video_url=video_url, output_dir=job_dir)
            transcript = self._asr.transcribe(audio_path)
            summary_md = await self._llm.summarize(transcript=transcript, video_url=video_url)
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("Bilibili summarize done, elapsed_ms=%d", elapsed_ms)
        return BilibiliSummaryData(
            video_url=video_url,
            summary_markdown=summary_md,
            elapsed_ms=elapsed_ms,
            transcript_chars=len(transcript),
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
