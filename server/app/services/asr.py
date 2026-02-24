from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)


class ASRService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def transcribe(self, audio_path: Path) -> str:
        mode = self._settings.asr.mode.lower().strip()

        if mode == "mock":
            logger.info("ASR mode=mock, return generated transcript")
            return (
                "这是 mock 模式生成的转写文本。"
                "如需真实转写，请在 config.yaml 里将 asr.mode 设置为 faster_whisper。"
            )

        if mode != "faster_whisper":
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"不支持的 ASR 模式: {mode}",
                status_code=400,
            )

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AppError(
                code=ErrorCode.DEPENDENCY_MISSING,
                message="缺少 faster-whisper 依赖，请先安装后重试。",
                status_code=500,
            ) from exc

        logger.info("Start ASR transcription: %s", audio_path)
        compute_type = "int8" if self._settings.asr.device == "cpu" else "float16"
        model = WhisperModel(
            self._settings.asr.model_size,
            device=self._settings.asr.device,
            compute_type=compute_type,
        )
        segments, _ = model.transcribe(
            str(audio_path), language=self._settings.asr.language
        )
        text = "".join(seg.text for seg in segments).strip()
        if not text:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="ASR 未产出可用文本。",
                status_code=502,
            )

        logger.info("ASR transcription done, chars=%d", len(text))
        return text
