from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class LLMConfig(BaseModel):
    enabled: bool = True
    api_base: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    api_key: str = ""
    model: str = "gemini-3-flash-preview"
    timeout_seconds: int = 120


class ASRConfig(BaseModel):
    mode: str = "faster_whisper"
    device: str = "cpu"
    model_size: str = "base"
    language: str = "zh"


class BilibiliConfig(BaseModel):
    max_video_minutes: int = 240
    yt_dlp_path: str = "yt-dlp"
    ffmpeg_path: str = "ffmpeg"


class XiaohongshuWebReadonlyConfig(BaseModel):
    page_fetch_driver: str = "auto"  # auto / http / playwright
    request_url: str = ""
    request_method: str = "GET"
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: str = ""
    har_capture_path: str = ".tmp/xhs_detail.har"
    curl_capture_path: str = ".tmp/xhs.curl"
    playwright_user_data_dir: str = ""
    playwright_channel: str = ""
    playwright_headless: bool = True
    playwright_collect_page_url_template: str = (
        "https://www.xiaohongshu.com/user/profile/{user_id}?tab=collect"
    )
    playwright_navigation_timeout_seconds: int = 30
    playwright_response_timeout_seconds: int = 12
    playwright_scroll_wait_seconds: float = 1.0
    playwright_max_idle_rounds: int = 6
    detail_fetch_mode: str = "auto"  # auto / always / never
    detail_request_url_template: str = ""
    detail_request_method: str = "GET"
    detail_request_headers: dict[str, str] = Field(default_factory=dict)
    detail_request_body: str = ""
    items_path: str = "data.notes"
    note_id_field: str = "note_id"
    title_field: str = "title"
    content_field_candidates: list[str] = Field(
        default_factory=lambda: ["desc", "content", "note_text"]
    )
    image_field_candidates: list[str] = Field(
        default_factory=lambda: [
            "cover.url_pre",
            "cover.url_default",
            "cover.info_list",
            "image_list",
            "images",
        ]
    )
    detail_content_field_candidates: list[str] = Field(
        default_factory=lambda: [
            "data.items.0.note_card.desc",
            "data.items.0.note_card.note_display_title",
            "data.note.desc",
            "data.note.note_desc",
        ]
    )
    detail_image_field_candidates: list[str] = Field(
        default_factory=lambda: [
            "data.items.0.note_card.image_list",
            "data.items.0.note_card.images_list",
            "data.note.image_list",
            "data.note.images",
        ]
    )
    source_url_field: str = "url"
    max_images_per_note: int = 32
    host_allowlist: list[str] = Field(
        default_factory=lambda: ["www.xiaohongshu.com", "edith.xiaohongshu.com"]
    )


class XiaohongshuConfig(BaseModel):
    mode: str = "web_readonly"
    cookie: str = ""
    collection_id: str = ""
    default_limit: int = 20
    max_limit: int = 30
    random_delay_min_seconds: float = 3.0
    random_delay_max_seconds: float = 10.0
    circuit_breaker_failures: int = 3
    min_live_sync_interval_seconds: int = 120
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


class NotesMergeConfig(BaseModel):
    semantic_similarity_enabled: bool = True
    semantic_model_name: str = "BAAI/bge-small-zh-v1.5"
    semantic_device: str = "cpu"
    semantic_max_chars: int = 2000
    semantic_cache_size: int = 512


class Settings(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    asr: ASRConfig = Field(default_factory=ASRConfig)
    bilibili: BilibiliConfig = Field(default_factory=BilibiliConfig)
    xiaohongshu: XiaohongshuConfig = Field(default_factory=XiaohongshuConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    notes_merge: NotesMergeConfig = Field(default_factory=NotesMergeConfig)


_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_dotenv(project_root: Path) -> None:
    dotenv_path = project_root / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _expand_env_vars(payload: object) -> object:
    if isinstance(payload, dict):
        return {key: _expand_env_vars(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_expand_env_vars(item) for item in payload]
    if isinstance(payload, str):
        return _ENV_VAR_PATTERN.sub(
            lambda match: os.getenv(match.group(1), ""),
            payload,
        )
    return payload


def _resolve_config_path() -> Path:
    project_root = _project_root()
    _load_dotenv(project_root)

    env_path = os.getenv("MIDAS_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

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
    expanded = _expand_env_vars(raw)
    return Settings.model_validate(expanded)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_config_path() -> Path:
    return _resolve_config_path()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
