from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from shutil import which

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
        yt_dlp_cmd = self._resolve_yt_dlp_command()
        ffmpeg_location = self._resolve_ffmpeg_location()

        cmd = [
            *yt_dlp_cmd,
            "--no-playlist",
            "-x",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "--ffmpeg-location",
            ffmpeg_location,
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

    def _resolve_yt_dlp_command(self) -> list[str]:
        configured = self._settings.bilibili.yt_dlp_path.strip()
        if self._is_executable_available(configured):
            return [configured]

        try:
            import yt_dlp  # noqa: F401
        except ImportError as exc:
            raise AppError(
                code=ErrorCode.DEPENDENCY_MISSING,
                message="yt-dlp 不可用，请安装后重试。",
                status_code=500,
                details={"configured_path": configured or "yt-dlp"},
            ) from exc

        logger.info(
            "yt-dlp command not found in PATH, fallback to Python module execution"
        )
        return [sys.executable, "-m", "yt_dlp"]

    def _resolve_ffmpeg_location(self) -> str:
        configured = self._settings.bilibili.ffmpeg_path.strip()
        resolved = self._resolve_executable_path(configured)
        if resolved:
            return resolved

        try:
            from imageio_ffmpeg import get_ffmpeg_exe
        except ImportError as exc:
            raise AppError(
                code=ErrorCode.DEPENDENCY_MISSING,
                message="ffmpeg 不可用，请安装 ffmpeg 或 imageio-ffmpeg。",
                status_code=500,
                details={"configured_path": configured or "ffmpeg"},
            ) from exc

        ffmpeg_path = get_ffmpeg_exe()
        if not ffmpeg_path:
            raise AppError(
                code=ErrorCode.DEPENDENCY_MISSING,
                message="ffmpeg 不可用，请安装 ffmpeg 或 imageio-ffmpeg。",
                status_code=500,
                details={"configured_path": configured or "ffmpeg"},
            )
        logger.info("ffmpeg command not found in PATH, fallback to imageio-ffmpeg binary")
        return ffmpeg_path

    def _is_executable_available(self, token: str) -> bool:
        return bool(self._resolve_executable_path(token))

    def _resolve_executable_path(self, token: str) -> str:
        if not token:
            return ""
        path = Path(token).expanduser()
        if path.is_absolute() or "/" in token or "\\" in token:
            return str(path) if path.exists() else ""
        resolved = which(token)
        return resolved or ""
