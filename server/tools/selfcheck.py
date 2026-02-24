from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.config import Settings, load_settings


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # pass | warn | fail
    message: str


def run_selfcheck(settings: Settings) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(check_runtime(settings))
    results.extend(check_llm(settings))
    results.extend(check_asr(settings))
    results.extend(check_bilibili(settings))
    results.extend(check_xiaohongshu(settings))
    return results


def check_runtime(settings: Settings) -> list[CheckResult]:
    temp_dir = Path(settings.runtime.temp_dir).expanduser()
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [
            CheckResult(
                name="runtime.temp_dir",
                status="fail",
                message=f"无法创建临时目录: {temp_dir} ({exc})",
            )
        ]

    return [
        CheckResult(
            name="runtime.temp_dir",
            status="pass",
            message=f"临时目录可用: {temp_dir}",
        )
    ]


def check_llm(settings: Settings) -> list[CheckResult]:
    cfg = settings.llm
    if not cfg.enabled:
        return [
            CheckResult(
                name="llm.enabled",
                status="warn",
                message="LLM 未启用，当前将返回本地降级总结。",
            )
        ]

    results: list[CheckResult] = [
        CheckResult(name="llm.enabled", status="pass", message="LLM 已启用。")
    ]
    if not cfg.api_key.strip():
        results.append(
            CheckResult(
                name="llm.api_key",
                status="fail",
                message="LLM 已启用但 api_key 为空。",
            )
        )
    else:
        results.append(
            CheckResult(name="llm.api_key", status="pass", message="LLM API Key 已配置。")
        )

    parsed = urlparse(cfg.api_base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        results.append(
            CheckResult(
                name="llm.api_base",
                status="fail",
                message=f"LLM api_base 非法: {cfg.api_base}",
            )
        )
    else:
        results.append(
            CheckResult(
                name="llm.api_base",
                status="pass",
                message=f"LLM API 地址格式正常: {cfg.api_base}",
            )
        )
    return results


def check_asr(settings: Settings) -> list[CheckResult]:
    mode = settings.asr.mode.strip().lower()
    if mode == "mock":
        return [
            CheckResult(
                name="asr.mode",
                status="warn",
                message="ASR 为 mock 模式，不进行真实语音转写。",
            )
        ]

    if mode != "faster_whisper":
        return [
            CheckResult(
                name="asr.mode",
                status="fail",
                message=f"不支持的 ASR 模式: {settings.asr.mode}",
            )
        ]

    has_module = importlib.util.find_spec("faster_whisper") is not None
    if not has_module:
        return [
            CheckResult(
                name="asr.faster_whisper",
                status="fail",
                message="缺少 faster_whisper 依赖。",
            )
        ]
    return [
        CheckResult(
            name="asr.faster_whisper",
            status="pass",
            message=f"faster_whisper 可用，device={settings.asr.device}",
        )
    ]


def check_bilibili(settings: Settings) -> list[CheckResult]:
    results: list[CheckResult] = []
    yt_path = settings.bilibili.yt_dlp_path
    ffmpeg_path = settings.bilibili.ffmpeg_path

    results.append(_check_command("bilibili.yt_dlp_path", yt_path))
    results.append(_check_command("bilibili.ffmpeg_path", ffmpeg_path))
    return results


def check_xiaohongshu(settings: Settings) -> list[CheckResult]:
    cfg = settings.xiaohongshu
    mode = cfg.mode.strip().lower()
    if mode == "mock":
        return [
            CheckResult(
                name="xiaohongshu.mode",
                status="warn",
                message="小红书为 mock 模式，不会请求真实网页接口。",
            )
        ]

    if mode != "web_readonly":
        return [
            CheckResult(
                name="xiaohongshu.mode",
                status="fail",
                message=f"不支持的小红书模式: {cfg.mode}",
            )
        ]

    results: list[CheckResult] = [
        CheckResult(
            name="xiaohongshu.mode",
            status="pass",
            message="小红书 web_readonly 模式已开启。",
        )
    ]

    request_url = cfg.web_readonly.request_url.strip()
    if not request_url:
        results.append(
            CheckResult(
                name="xiaohongshu.web_readonly.request_url",
                status="fail",
                message="request_url 为空。",
            )
        )
        return results

    parsed = urlparse(request_url)
    if parsed.scheme != "https" or not parsed.netloc:
        results.append(
            CheckResult(
                name="xiaohongshu.web_readonly.request_url",
                status="fail",
                message="request_url 必须是 HTTPS 且包含域名。",
            )
        )
    else:
        results.append(
            CheckResult(
                name="xiaohongshu.web_readonly.request_url",
                status="pass",
                message=f"request_url 已配置: {request_url}",
            )
        )

    allowlist = {item.strip() for item in cfg.web_readonly.host_allowlist if item.strip()}
    if parsed.netloc and parsed.netloc not in allowlist:
        results.append(
            CheckResult(
                name="xiaohongshu.web_readonly.host_allowlist",
                status="fail",
                message=f"请求域名不在白名单: {parsed.netloc}",
            )
        )
    else:
        results.append(
            CheckResult(
                name="xiaohongshu.web_readonly.host_allowlist",
                status="pass",
                message="请求域名命中白名单。",
            )
        )

    method = cfg.web_readonly.request_method.strip().upper()
    if method not in {"GET", "POST"}:
        results.append(
            CheckResult(
                name="xiaohongshu.web_readonly.request_method",
                status="fail",
                message=f"request_method 仅支持 GET/POST，当前为 {method}",
            )
        )
    else:
        results.append(
            CheckResult(
                name="xiaohongshu.web_readonly.request_method",
                status="pass",
                message=f"request_method={method}",
            )
        )

    if "Cookie" not in cfg.web_readonly.request_headers and not cfg.cookie.strip():
        results.append(
            CheckResult(
                name="xiaohongshu.cookie",
                status="warn",
                message="未发现 Cookie，真实请求大概率鉴权失败。",
            )
        )
    else:
        results.append(
            CheckResult(
                name="xiaohongshu.cookie",
                status="pass",
                message="Cookie 已提供（header 或配置字段）。",
            )
        )

    if cfg.min_live_sync_interval_seconds < 300:
        results.append(
            CheckResult(
                name="xiaohongshu.min_live_sync_interval_seconds",
                status="warn",
                message=(
                    "真实同步最小间隔偏小，建议至少 1800 秒以降低风控风险。"
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="xiaohongshu.min_live_sync_interval_seconds",
                status="pass",
                message=f"最小同步间隔: {cfg.min_live_sync_interval_seconds} 秒。",
            )
        )

    return results


def _check_command(name: str, command: str) -> CheckResult:
    if shutil.which(command):
        return CheckResult(name=name, status="pass", message=f"命令可用: {command}")
    return CheckResult(name=name, status="fail", message=f"命令不可用: {command}")


def summarize_results(results: Iterable[CheckResult]) -> tuple[int, int, int]:
    pass_count = sum(1 for item in results if item.status == "pass")
    warn_count = sum(1 for item in results if item.status == "warn")
    fail_count = sum(1 for item in results if item.status == "fail")
    return pass_count, warn_count, fail_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Midas 服务端环境与配置自检")
    parser.parse_args()

    settings = load_settings()
    results = run_selfcheck(settings)

    for item in results:
        print(f"[{item.status.upper()}] {item.name}: {item.message}")

    pass_count, warn_count, fail_count = summarize_results(results)
    print(
        f"\n自检结果: pass={pass_count}, warn={warn_count}, fail={fail_count}"
    )
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
