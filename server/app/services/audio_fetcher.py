from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".opus", ".webm"}


class AudioFetcher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_audio(self, video_url: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = output_dir / "source.%(ext)s"

        cmd = [
            self._settings.bilibili.yt_dlp_path,
            "--no-playlist",
            "-x",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "--ffmpeg-location",
            self._settings.bilibili.ffmpeg_path,
            "-o",
            str(output_template),
            video_url,
        ]

        logger.info("Start downloading audio for URL: %s", video_url)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            raise AppError(
                code=ErrorCode.DEPENDENCY_MISSING,
                message="yt-dlp 或 ffmpeg 不可用，请先安装依赖。",
                status_code=500,
                details={"dependency": str(exc)},
            ) from exc

        if proc.returncode != 0:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="视频音频下载失败，请确认链接可访问。",
                status_code=502,
                details={"stderr": proc.stderr[-500:]},
            )

        files = [p for p in output_dir.iterdir() if p.suffix.lower() in _AUDIO_SUFFIXES]
        if not files:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="音频下载完成但未找到音频文件。",
                status_code=502,
            )

        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        logger.info("Downloaded audio file: %s", files[0])
        return files[0]
