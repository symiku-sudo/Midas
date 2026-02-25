from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.config import Settings, clear_settings_cache, get_config_path, get_settings
from app.core.errors import AppError, ErrorCode

_EDITABLE_PATHS = {
    "server.host",
    "server.port",
    "llm.enabled",
    "llm.api_base",
    "llm.model",
    "llm.timeout_seconds",
    "asr.mode",
    "asr.device",
    "asr.model_size",
    "asr.language",
    "bilibili.max_video_minutes",
    "bilibili.yt_dlp_path",
    "bilibili.ffmpeg_path",
    "runtime.temp_dir",
    "runtime.log_level",
    "xiaohongshu.mode",
    "xiaohongshu.collection_id",
    "xiaohongshu.default_limit",
    "xiaohongshu.max_limit",
    "xiaohongshu.random_delay_min_seconds",
    "xiaohongshu.random_delay_max_seconds",
    "xiaohongshu.circuit_breaker_failures",
    "xiaohongshu.min_live_sync_interval_seconds",
    "xiaohongshu.db_path",
    "xiaohongshu.request_timeout_seconds",
    "xiaohongshu.api_base",
    "xiaohongshu.mock_notes_path",
    "xiaohongshu.web_readonly.request_url",
    "xiaohongshu.web_readonly.request_method",
    "xiaohongshu.web_readonly.request_body",
    "xiaohongshu.web_readonly.detail_fetch_mode",
    "xiaohongshu.web_readonly.detail_request_url_template",
    "xiaohongshu.web_readonly.detail_request_method",
    "xiaohongshu.web_readonly.detail_request_body",
    "xiaohongshu.web_readonly.items_path",
    "xiaohongshu.web_readonly.note_id_field",
    "xiaohongshu.web_readonly.title_field",
    "xiaohongshu.web_readonly.content_field_candidates",
    "xiaohongshu.web_readonly.image_field_candidates",
    "xiaohongshu.web_readonly.detail_content_field_candidates",
    "xiaohongshu.web_readonly.detail_image_field_candidates",
    "xiaohongshu.web_readonly.source_url_field",
    "xiaohongshu.web_readonly.max_images_per_note",
    "xiaohongshu.web_readonly.host_allowlist",
}


class EditableConfigService:
    def __init__(
        self,
        config_path: Path | None = None,
        default_path: Path | None = None,
    ) -> None:
        resolved = config_path or get_config_path()
        if resolved.name == "config.example.yaml":
            resolved = resolved.with_name("config.yaml")
        self._config_path = resolved
        self._default_path = default_path or self._config_path.with_name("config.example.yaml")

    def get_editable_settings(self) -> dict[str, Any]:
        current = get_settings().model_dump()
        return self._extract_allowed(current)

    def update_editable_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(patch, dict) or not patch:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="settings 不能为空对象。",
                status_code=400,
            )

        flattened = self._flatten_patch(patch)
        if not flattened:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="settings 中未检测到可更新字段。",
                status_code=400,
            )

        for path in flattened.keys():
            if path not in _EDITABLE_PATHS:
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=f"字段不可修改或不存在：{path}",
                    status_code=400,
                )

        raw = self._load_yaml(self._config_path)
        for path, value in flattened.items():
            self._set_by_path(raw, path, value)

        self._validate(raw)
        self._write_yaml(self._config_path, raw)
        clear_settings_cache()
        return self.get_editable_settings()

    def reset_to_defaults(self) -> dict[str, Any]:
        raw = self._load_yaml(self._config_path)
        default_raw = self._load_defaults()
        for path in _EDITABLE_PATHS:
            self._set_by_path(raw, path, self._get_by_path(default_raw, path))

        self._validate(raw)
        self._write_yaml(self._config_path, raw)
        clear_settings_cache()
        return self.get_editable_settings()

    def _load_defaults(self) -> dict[str, Any]:
        if self._default_path.exists():
            return self._load_yaml(self._default_path)
        return Settings().model_dump()

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as fp:
            loaded = yaml.safe_load(fp) or {}
        if not isinstance(loaded, dict):
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"配置文件不是 YAML 对象：{path}",
                status_code=400,
            )
        return loaded

    def _write_yaml(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            yaml.safe_dump(payload, fp, allow_unicode=True, sort_keys=False)

    def _validate(self, payload: dict[str, Any]) -> None:
        try:
            Settings.model_validate(payload)
        except Exception as exc:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"配置校验失败：{exc}",
                status_code=400,
            ) from exc

    def _flatten_patch(
        self,
        payload: dict[str, Any],
        *,
        prefix: str = "",
    ) -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not key.strip():
                continue
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                nested = self._flatten_patch(value, prefix=full_key)
                flattened.update(nested)
            else:
                flattened[full_key] = value
        return flattened

    def _set_by_path(self, payload: dict[str, Any], path: str, value: Any) -> None:
        parts = path.split(".")
        current = payload
        for part in parts[:-1]:
            node = current.get(part)
            if not isinstance(node, dict):
                node = {}
                current[part] = node
            current = node
        current[parts[-1]] = value

    def _get_by_path(self, payload: dict[str, Any], path: str) -> Any:
        parts = path.split(".")
        current: Any = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _extract_allowed(self, payload: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for path in sorted(_EDITABLE_PATHS):
            self._set_by_path(result, path, self._get_by_path(payload, path))
        return result
