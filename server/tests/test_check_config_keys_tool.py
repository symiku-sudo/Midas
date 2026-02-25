from __future__ import annotations

from pathlib import Path

import yaml

from tools.check_config_keys import validate_config_key_schema


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_validate_config_key_schema_passes_when_keys_match(tmp_path: Path) -> None:
    example = {
        "llm": {"enabled": True, "timeout_seconds": 120},
        "runtime": {"log_level": "INFO"},
    }
    config = {
        "llm": {"enabled": False, "timeout_seconds": 300},
        "runtime": {"log_level": "DEBUG"},
    }

    example_path = tmp_path / "config.example.yaml"
    config_path = tmp_path / "config.yaml"
    _write_yaml(example_path, example)
    _write_yaml(config_path, config)

    issues = validate_config_key_schema(example_path, config_path)
    assert issues == []


def test_validate_config_key_schema_reports_missing_and_extra_keys(tmp_path: Path) -> None:
    example = {
        "llm": {"enabled": True, "timeout_seconds": 120},
    }
    config = {
        "llm": {"enabled": True},
        "runtime": {"log_level": "INFO"},
    }

    example_path = tmp_path / "config.example.yaml"
    config_path = tmp_path / "config.yaml"
    _write_yaml(example_path, example)
    _write_yaml(config_path, config)

    issues = validate_config_key_schema(example_path, config_path)
    paths = {item.path for item in issues}
    assert "llm.timeout_seconds" in paths
    assert "runtime" in paths


def test_validate_config_key_schema_reports_type_mismatch(tmp_path: Path) -> None:
    example = {
        "xiaohongshu": {
            "web_readonly": {
                "host_allowlist": ["www.xiaohongshu.com"],
            }
        }
    }
    config = {
        "xiaohongshu": {
            "web_readonly": {
                "host_allowlist": {"a": 1},
            }
        }
    }

    example_path = tmp_path / "config.example.yaml"
    config_path = tmp_path / "config.yaml"
    _write_yaml(example_path, example)
    _write_yaml(config_path, config)

    issues = validate_config_key_schema(example_path, config_path)
    assert len(issues) == 1
    assert issues[0].path == "xiaohongshu.web_readonly.host_allowlist"
    assert "期望 list" in issues[0].message
