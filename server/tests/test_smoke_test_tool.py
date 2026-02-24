from __future__ import annotations

from collections.abc import Callable

import httpx

from tools.smoke_test import (
    check_bilibili_invalid_input,
    check_health,
    check_xhs_confirm_guard,
    check_xhs_job_guard,
    check_xhs_job_mock,
    check_xhs_sync_mock,
)


def _client_with_handler(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url="http://test")


def test_check_health_pass() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/health":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "code": "OK",
                    "message": "",
                    "data": {"status": "ok"},
                    "request_id": "r1",
                },
            )
        return httpx.Response(404, json={})

    with _client_with_handler(handler) as client:
        result = check_health(client)
    assert result.status == "pass"


def test_check_bilibili_invalid_input_pass() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/bilibili/summarize":
            return httpx.Response(
                400,
                json={
                    "ok": False,
                    "code": "INVALID_INPUT",
                    "message": "bad input",
                    "data": None,
                    "request_id": "r2",
                },
            )
        return httpx.Response(404, json={})

    with _client_with_handler(handler) as client:
        result = check_bilibili_invalid_input(client)
    assert result.status == "pass"


def test_check_xhs_sync_mock_reports_wrong_mode() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/xiaohongshu/sync":
            return httpx.Response(
                400,
                json={
                    "ok": False,
                    "code": "INVALID_INPUT",
                    "message": "web_readonly 模式需要显式确认。请在请求体中传 confirm_live=true。",
                },
            )
        return httpx.Response(404, json={})

    with _client_with_handler(handler) as client:
        result = check_xhs_sync_mock(client)
    assert result.status == "fail"
    assert "web_readonly" in result.message


def test_check_xhs_confirm_guard_pass() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/xiaohongshu/sync":
            return httpx.Response(
                400,
                json={
                    "ok": False,
                    "code": "INVALID_INPUT",
                    "message": "web_readonly 模式需要显式确认。请在请求体中传 confirm_live=true。",
                },
            )
        return httpx.Response(404, json={})

    with _client_with_handler(handler) as client:
        result = check_xhs_confirm_guard(client)
    assert result.status == "pass"


def test_check_xhs_job_mock_pass() -> None:
    calls = {"status": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/xiaohongshu/sync/jobs":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "code": "OK",
                    "data": {"job_id": "job-1", "status": "pending", "requested_limit": 1},
                    "request_id": "r3",
                },
            )

        if request.method == "GET" and request.url.path == "/api/xiaohongshu/sync/jobs/job-1":
            calls["status"] += 1
            state = "running" if calls["status"] == 1 else "succeeded"
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "code": "OK",
                    "data": {"job_id": "job-1", "status": state},
                    "request_id": "r4",
                },
            )

        return httpx.Response(404, json={})

    with _client_with_handler(handler) as client:
        result = check_xhs_job_mock(client, poll_timeout_seconds=2)
    assert result.status == "pass"


def test_check_xhs_job_guard_pass() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/xiaohongshu/sync/jobs":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "code": "OK",
                    "data": {"job_id": "job-2", "status": "pending", "requested_limit": 1},
                    "request_id": "r5",
                },
            )

        if request.method == "GET" and request.url.path == "/api/xiaohongshu/sync/jobs/job-2":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "code": "OK",
                    "data": {
                        "job_id": "job-2",
                        "status": "failed",
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": "需要 confirm_live",
                            "details": None,
                        },
                    },
                    "request_id": "r6",
                },
            )

        return httpx.Response(404, json={})

    with _client_with_handler(handler) as client:
        result = check_xhs_job_guard(client, poll_timeout_seconds=2)
    assert result.status == "pass"
