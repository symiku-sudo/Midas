from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # pass | fail
    message: str


def run_smoke(
    *,
    base_url: str,
    timeout_seconds: int,
    profile: str,
    poll_timeout_seconds: int,
) -> list[CheckResult]:
    _ = poll_timeout_seconds  # backward-compatible arg; not used.

    results: list[CheckResult] = []
    with httpx.Client(
        base_url=base_url.rstrip("/"),
        timeout=timeout_seconds,
        trust_env=False,
    ) as client:
        results.append(check_health(client))
        results.append(check_bilibili_invalid_input(client))

        if profile == "mock":
            results.append(check_xhs_summarize_url_mock(client))
        elif profile == "web_guard":
            results.append(check_xhs_summarize_url_guard(client))
        else:
            results.append(
                CheckResult(
                    name="profile",
                    status="fail",
                    message=f"未知 profile: {profile}",
                )
            )
    return results


def check_health(client: httpx.Client) -> CheckResult:
    try:
        resp = client.get("/health")
    except httpx.HTTPError as exc:
        return CheckResult(name="health", status="fail", message=f"请求失败: {exc}")

    if resp.status_code != 200:
        return CheckResult(
            name="health",
            status="fail",
            message=f"状态码异常: {resp.status_code}",
        )
    body = _parse_json(resp)
    if body is None:
        return CheckResult(name="health", status="fail", message="响应不是 JSON。")
    if body.get("ok") is True and body.get("code") == "OK":
        return CheckResult(name="health", status="pass", message="服务健康接口正常。")
    return CheckResult(name="health", status="fail", message=f"响应结构异常: {body}")


def check_bilibili_invalid_input(client: httpx.Client) -> CheckResult:
    payload = {"video_url": "https://example.com/video/123"}
    try:
        resp = client.post("/api/bilibili/summarize", json=payload)
    except httpx.HTTPError as exc:
        return CheckResult(name="bilibili.invalid_input", status="fail", message=str(exc))

    body = _parse_json(resp)
    if body is None:
        return CheckResult(
            name="bilibili.invalid_input",
            status="fail",
            message="响应不是 JSON。",
        )
    if resp.status_code == 400 and body.get("code") == "INVALID_INPUT":
        return CheckResult(
            name="bilibili.invalid_input",
            status="pass",
            message="无效 URL 校验正常。",
        )
    return CheckResult(
        name="bilibili.invalid_input",
        status="fail",
        message=f"期望 INVALID_INPUT，实际 {resp.status_code} / {body.get('code')}",
    )


def check_xhs_summarize_url_mock(client: httpx.Client) -> CheckResult:
    mock_url = "https://www.xiaohongshu.com/explore/mock-note-001"
    try:
        resp = client.post("/api/xiaohongshu/summarize-url", json={"url": mock_url})
    except httpx.HTTPError as exc:
        return CheckResult(name="xhs.summarize_url.mock", status="fail", message=str(exc))

    body = _parse_json(resp)
    if body is None:
        return CheckResult(
            name="xhs.summarize_url.mock",
            status="fail",
            message="响应不是 JSON。",
        )

    if resp.status_code == 200 and body.get("ok") is True:
        data = body.get("data") or {}
        if (
            data.get("note_id") == "mock-note-001"
            and data.get("source_url") == mock_url
            and data.get("summary_markdown")
        ):
            return CheckResult(
                name="xhs.summarize_url.mock",
                status="pass",
                message="单篇 URL 总结成功。",
            )
        return CheckResult(
            name="xhs.summarize_url.mock",
            status="fail",
            message=f"响应结构异常: {data}",
        )

    return CheckResult(
        name="xhs.summarize_url.mock",
        status="fail",
        message=f"期望 200 成功，实际 {resp.status_code} / {body.get('code')}",
    )


def check_xhs_summarize_url_guard(client: httpx.Client) -> CheckResult:
    # In web_guard mode we avoid live upstream dependency by asserting
    # endpoint-level INVALID_INPUT guard on a non-xiaohongshu URL.
    invalid_url = "https://example.com/not-xhs-note"
    try:
        resp = client.post("/api/xiaohongshu/summarize-url", json={"url": invalid_url})
    except httpx.HTTPError as exc:
        return CheckResult(name="xhs.summarize_url.guard", status="fail", message=str(exc))

    body = _parse_json(resp)
    if body is None:
        return CheckResult(
            name="xhs.summarize_url.guard",
            status="fail",
            message="响应不是 JSON。",
        )

    if resp.status_code == 400 and body.get("code") == "INVALID_INPUT":
        return CheckResult(
            name="xhs.summarize_url.guard",
            status="pass",
            message="web_guard 模式下 URL 输入校验正常。",
        )

    return CheckResult(
        name="xhs.summarize_url.guard",
        status="fail",
        message=f"期望 INVALID_INPUT，实际 {resp.status_code} / {body.get('code')}",
    )


def summarize_results(results: list[CheckResult]) -> tuple[int, int]:
    pass_count = sum(1 for item in results if item.status == "pass")
    fail_count = sum(1 for item in results if item.status == "fail")
    return pass_count, fail_count


def _parse_json(resp: httpx.Response) -> dict[str, Any] | None:
    try:
        payload = resp.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Midas API 快速冒烟测试")
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="服务端地址，默认 http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=15,
        help="单请求超时时间（秒）",
    )
    parser.add_argument(
        "--poll-timeout-seconds",
        type=int,
        default=15,
        help="兼容参数（已不使用）",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="mock",
        choices=["mock", "web_guard"],
        help="mock: 验证 mock URL 可总结；web_guard: 验证 URL 输入保护。",
    )
    args = parser.parse_args()

    results = run_smoke(
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
        profile=args.profile,
        poll_timeout_seconds=args.poll_timeout_seconds,
    )

    for item in results:
        print(f"[{item.status.upper()}] {item.name}: {item.message}")

    pass_count, fail_count = summarize_results(results)
    print(f"\n冒烟结果: pass={pass_count}, fail={fail_count}")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
