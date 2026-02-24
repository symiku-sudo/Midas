from __future__ import annotations

import argparse
import time
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
    results: list[CheckResult] = []
    with httpx.Client(
        base_url=base_url.rstrip("/"),
        timeout=timeout_seconds,
        trust_env=False,
    ) as client:
        results.append(check_health(client))
        results.append(check_bilibili_invalid_input(client))

        if profile == "mock":
            results.append(check_xhs_sync_mock(client))
            results.append(check_xhs_job_mock(client, poll_timeout_seconds=poll_timeout_seconds))
        elif profile == "web_guard":
            results.append(check_xhs_confirm_guard(client))
            results.append(
                check_xhs_job_guard(client, poll_timeout_seconds=poll_timeout_seconds)
            )
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


def check_xhs_sync_mock(client: httpx.Client) -> CheckResult:
    try:
        resp = client.post("/api/xiaohongshu/sync", json={"limit": 2})
    except httpx.HTTPError as exc:
        return CheckResult(name="xhs.sync.mock", status="fail", message=str(exc))

    body = _parse_json(resp)
    if body is None:
        return CheckResult(name="xhs.sync.mock", status="fail", message="响应不是 JSON。")

    if resp.status_code == 200 and body.get("ok") is True:
        data = body.get("data") or {}
        fetched = data.get("fetched_count")
        return CheckResult(
            name="xhs.sync.mock",
            status="pass",
            message=f"同步成功，fetched_count={fetched}",
        )

    if (
        resp.status_code == 400
        and body.get("code") == "INVALID_INPUT"
        and "confirm_live" in str(body.get("message", ""))
    ):
        return CheckResult(
            name="xhs.sync.mock",
            status="fail",
            message="当前服务似乎处于 web_readonly 模式，请改用 --profile web_guard。",
        )

    return CheckResult(
        name="xhs.sync.mock",
        status="fail",
        message=f"期望 200 成功，实际 {resp.status_code} / {body.get('code')}",
    )


def check_xhs_confirm_guard(client: httpx.Client) -> CheckResult:
    try:
        resp = client.post("/api/xiaohongshu/sync", json={"limit": 1})
    except httpx.HTTPError as exc:
        return CheckResult(name="xhs.sync.guard", status="fail", message=str(exc))

    body = _parse_json(resp)
    if body is None:
        return CheckResult(name="xhs.sync.guard", status="fail", message="响应不是 JSON。")

    if (
        resp.status_code == 400
        and body.get("code") == "INVALID_INPUT"
        and "confirm_live" in str(body.get("message", ""))
    ):
        return CheckResult(
            name="xhs.sync.guard",
            status="pass",
            message="confirm_live 显式确认保护生效。",
        )

    return CheckResult(
        name="xhs.sync.guard",
        status="fail",
        message=f"未命中 confirm_live 保护，实际 {resp.status_code} / {body.get('code')}",
    )


def check_xhs_job_mock(client: httpx.Client, *, poll_timeout_seconds: int) -> CheckResult:
    try:
        create = client.post("/api/xiaohongshu/sync/jobs", json={"limit": 1})
    except httpx.HTTPError as exc:
        return CheckResult(name="xhs.job.mock", status="fail", message=str(exc))

    create_body = _parse_json(create)
    if create_body is None:
        return CheckResult(name="xhs.job.mock", status="fail", message="create 响应不是 JSON。")
    if create.status_code != 200 or create_body.get("ok") is not True:
        return CheckResult(
            name="xhs.job.mock",
            status="fail",
            message=f"create 失败: {create.status_code} / {create_body.get('code')}",
        )

    job_id = str((create_body.get("data") or {}).get("job_id", "")).strip()
    if not job_id:
        return CheckResult(name="xhs.job.mock", status="fail", message="缺少 job_id。")

    deadline = time.time() + poll_timeout_seconds
    while time.time() < deadline:
        try:
            status_resp = client.get(f"/api/xiaohongshu/sync/jobs/{job_id}")
        except httpx.HTTPError as exc:
            return CheckResult(name="xhs.job.mock", status="fail", message=str(exc))
        status_body = _parse_json(status_resp)
        if status_body is None:
            return CheckResult(name="xhs.job.mock", status="fail", message="status 响应不是 JSON。")

        state = ((status_body.get("data") or {}).get("status") or "").strip()
        if state == "succeeded":
            return CheckResult(name="xhs.job.mock", status="pass", message=f"job={job_id} succeeded")
        if state == "failed":
            error = (status_body.get("data") or {}).get("error") or {}
            return CheckResult(
                name="xhs.job.mock",
                status="fail",
                message=f"job={job_id} failed: {error}",
            )
        time.sleep(0.2)

    return CheckResult(
        name="xhs.job.mock",
        status="fail",
        message=f"轮询超时（{poll_timeout_seconds}s），job={job_id}",
    )


def check_xhs_job_guard(client: httpx.Client, *, poll_timeout_seconds: int) -> CheckResult:
    try:
        create = client.post("/api/xiaohongshu/sync/jobs", json={"limit": 1})
    except httpx.HTTPError as exc:
        return CheckResult(name="xhs.job.guard", status="fail", message=str(exc))

    create_body = _parse_json(create)
    if create_body is None:
        return CheckResult(
            name="xhs.job.guard",
            status="fail",
            message="create 响应不是 JSON。",
        )
    if create.status_code != 200 or create_body.get("ok") is not True:
        return CheckResult(
            name="xhs.job.guard",
            status="fail",
            message=f"create 失败: {create.status_code} / {create_body.get('code')}",
        )

    job_id = str((create_body.get("data") or {}).get("job_id", "")).strip()
    if not job_id:
        return CheckResult(name="xhs.job.guard", status="fail", message="缺少 job_id。")

    deadline = time.time() + poll_timeout_seconds
    while time.time() < deadline:
        try:
            status_resp = client.get(f"/api/xiaohongshu/sync/jobs/{job_id}")
        except httpx.HTTPError as exc:
            return CheckResult(name="xhs.job.guard", status="fail", message=str(exc))
        status_body = _parse_json(status_resp)
        if status_body is None:
            return CheckResult(
                name="xhs.job.guard",
                status="fail",
                message="status 响应不是 JSON。",
            )

        data = status_body.get("data") or {}
        state = (data.get("status") or "").strip()
        if state == "failed":
            error = data.get("error") or {}
            if error.get("code") == "INVALID_INPUT":
                return CheckResult(
                    name="xhs.job.guard",
                    status="pass",
                    message=f"job={job_id} 命中 confirm_live 保护失败（符合预期）",
                )
            return CheckResult(
                name="xhs.job.guard",
                status="fail",
                message=f"job={job_id} failed，但错误码异常: {error}",
            )

        if state == "succeeded":
            return CheckResult(
                name="xhs.job.guard",
                status="fail",
                message=f"job={job_id} succeeded，说明当前不是 web_readonly 保护场景。",
            )
        time.sleep(0.2)

    return CheckResult(
        name="xhs.job.guard",
        status="fail",
        message=f"轮询超时（{poll_timeout_seconds}s），job={job_id}",
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
        help="异步任务轮询超时（秒）",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="mock",
        choices=["mock", "web_guard"],
        help="mock: 期望 xhs mock 同步成功；web_guard: 期望 confirm_live 保护生效",
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
