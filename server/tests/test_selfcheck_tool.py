from __future__ import annotations

from app.core.config import Settings, XiaohongshuConfig, XiaohongshuWebReadonlyConfig
from tools.selfcheck import (
    CheckResult,
    check_bilibili,
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
