from __future__ import annotations

from pathlib import Path

import yaml

from app.core.config import Settings, XiaohongshuConfig, XiaohongshuWebReadonlyConfig
from tools.selfcheck import (
    CheckResult,
    check_bilibili,
    check_config_key_schema,
    check_llm,
    check_xiaohongshu,
    summarize_results,
)


def test_check_llm_enabled_without_key_fails() -> None:
    settings = Settings.model_validate(
        {
            "llm": {
                "enabled": True,
                "api_base": "https://api.openai.com/v1",
                "api_key": "",
            }
        }
    )

    results = check_llm(settings)
    status_by_name = {item.name: item.status for item in results}
    assert status_by_name["llm.api_key"] == "fail"
    assert status_by_name["llm.api_base"] == "pass"


def test_check_xiaohongshu_web_readonly_missing_url_fails() -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            web_readonly=XiaohongshuWebReadonlyConfig(request_url=""),
        )
    )

    results = check_xiaohongshu(settings)
    status_by_name = {item.name: item.status for item in results}
    assert status_by_name["xiaohongshu.web_readonly.request_url"] == "fail"


def test_check_xiaohongshu_web_readonly_valid_config_passes() -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            min_live_sync_interval_seconds=1800,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v1/collect/list",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                host_allowlist=["edith.xiaohongshu.com"],
            ),
        )
    )

    results = check_xiaohongshu(settings)
    status_by_name = {item.name: item.status for item in results}
    assert status_by_name["xiaohongshu.web_readonly.request_url"] == "pass"
    assert status_by_name["xiaohongshu.web_readonly.host_allowlist"] == "pass"
    assert status_by_name["xiaohongshu.cookie"] == "pass"


def test_check_xiaohongshu_playwright_driver_missing_dependency_warns_in_auto(
    monkeypatch,
) -> None:
    monkeypatch.setattr("tools.selfcheck.importlib.util.find_spec", lambda _name: None)
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            min_live_sync_interval_seconds=1800,
            web_readonly=XiaohongshuWebReadonlyConfig(
                page_fetch_driver="auto",
                request_url="https://edith.xiaohongshu.com/api/sns/web/v1/collect/list",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                host_allowlist=["edith.xiaohongshu.com"],
            ),
        )
    )

    results = check_xiaohongshu(settings)
    status_by_name = {item.name: item.status for item in results}
    assert status_by_name["xiaohongshu.web_readonly.page_fetch_driver"] == "pass"
    assert status_by_name["xiaohongshu.web_readonly.playwright"] == "warn"


def test_check_xiaohongshu_playwright_driver_missing_dependency_fails_when_forced(
    monkeypatch,
) -> None:
    monkeypatch.setattr("tools.selfcheck.importlib.util.find_spec", lambda _name: None)
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            min_live_sync_interval_seconds=1800,
            web_readonly=XiaohongshuWebReadonlyConfig(
                page_fetch_driver="playwright",
                request_url="https://edith.xiaohongshu.com/api/sns/web/v1/collect/list",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                host_allowlist=["edith.xiaohongshu.com"],
            ),
        )
    )

    results = check_xiaohongshu(settings)
    status_by_name = {item.name: item.status for item in results}
    assert status_by_name["xiaohongshu.web_readonly.page_fetch_driver"] == "pass"
    assert status_by_name["xiaohongshu.web_readonly.playwright"] == "fail"


def test_check_bilibili_binary_uses_which(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "bilibili": {"yt_dlp_path": "yt-dlp", "ffmpeg_path": "ffmpeg"},
        }
    )

    def _fake_which(cmd: str):
        return f"/usr/bin/{cmd}" if cmd == "yt-dlp" else None

    monkeypatch.setattr("tools.selfcheck.shutil.which", _fake_which)

    results = check_bilibili(settings)
    status_by_name = {item.name: item.status for item in results}
    assert status_by_name["bilibili.yt_dlp_path"] == "pass"
    assert status_by_name["bilibili.ffmpeg_path"] == "fail"


def test_summarize_results_counts() -> None:
    pass_count, warn_count, fail_count = summarize_results(
        [
            CheckResult(name="a", status="pass", message=""),
            CheckResult(name="b", status="warn", message=""),
            CheckResult(name="c", status="fail", message=""),
        ]
    )
    assert pass_count == 1
    assert warn_count == 1
    assert fail_count == 1


def test_check_config_key_schema_warns_when_missing_config(
    monkeypatch, tmp_path: Path
) -> None:
    example = {
        "llm": {"enabled": True},
    }
    (tmp_path / "config.example.yaml").write_text(
        yaml.safe_dump(example, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    monkeypatch.setattr("tools.selfcheck.SERVER_ROOT", tmp_path)

    results = check_config_key_schema()
    assert len(results) == 1
    assert results[0].name == "config.key_schema"
    assert results[0].status == "warn"


def test_check_config_key_schema_fails_on_shape_diff(
    monkeypatch, tmp_path: Path
) -> None:
    example = {
        "llm": {"enabled": True, "timeout_seconds": 120},
    }
    config = {
        "llm": {"enabled": True},
    }

    (tmp_path / "config.example.yaml").write_text(
        yaml.safe_dump(example, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    monkeypatch.setattr("tools.selfcheck.SERVER_ROOT", tmp_path)

    results = check_config_key_schema()
    assert len(results) == 1
    assert results[0].status == "fail"
    assert "llm.timeout_seconds" in results[0].message
