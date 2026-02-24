from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class LLMConfig(BaseModel):
    enabled: bool = False
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout_seconds: int = 120


class ASRConfig(BaseModel):
    mode: str = "mock"
    device: str = "cpu"
    model_size: str = "base"
    language: str = "zh"


class BilibiliConfig(BaseModel):
    max_video_minutes: int = 240
    yt_dlp_path: str = "yt-dlp"
    ffmpeg_path: str = "ffmpeg"


class XiaohongshuWebReadonlyConfig(BaseModel):
    request_url: str = ""
    request_method: str = "GET"
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: str = ""
    items_path: str = "data.notes"
    note_id_field: str = "note_id"
    title_field: str = "title"
    content_field_candidates: list[str] = Field(
        default_factory=lambda: ["desc", "content", "note_text"]
    )
    source_url_field: str = "url"
    host_allowlist: list[str] = Field(
        default_factory=lambda: ["www.xiaohongshu.com", "edith.xiaohongshu.com"]
    )


class XiaohongshuConfig(BaseModel):
    mode: str = "mock"
    cookie: str = ""
    collection_id: str = ""
    default_limit: int = 20
    max_limit: int = 30
    random_delay_min_seconds: float = 3.0
    random_delay_max_seconds: float = 10.0
    circuit_breaker_failures: int = 3
    min_live_sync_interval_seconds: int = 1800
    db_path: str = ".tmp/midas.db"
    request_timeout_seconds: int = 30
    api_base: str = ""
    mock_notes_path: str = ""
    web_readonly: XiaohongshuWebReadonlyConfig = Field(
        default_factory=XiaohongshuWebReadonlyConfig
    )


class RuntimeConfig(BaseModel):
    temp_dir: str = ".tmp"
    log_level: str = "INFO"


class Settings(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    asr: ASRConfig = Field(default_factory=ASRConfig)
    bilibili: BilibiliConfig = Field(default_factory=BilibiliConfig)
    xiaohongshu: XiaohongshuConfig = Field(default_factory=XiaohongshuConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)


def _resolve_config_path() -> Path:
    env_path = os.getenv("MIDAS_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    project_root = Path(__file__).resolve().parents[2]
    default_path = project_root / "config.yaml"
    if default_path.exists():
        return default_path

    fallback = project_root / "config.example.yaml"
    return fallback


def load_settings() -> Settings:
    config_path = _resolve_config_path()
    if not config_path.exists():
        return Settings()

    with config_path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    return Settings.model_validate(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
