from __future__ import annotations

from collections.abc import Callable

import httpx

from tools.smoke_test import (
    check_bilibili_invalid_input,
    check_health,
    check_xhs_summarize_url_mock,
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


def test_check_xhs_summarize_url_mock_pass() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/xiaohongshu/summarize-url":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "code": "OK",
                    "message": "",
                    "data": {
                        "note_id": "mock-note-001",
                        "title": "示例",
                        "source_url": "https://www.xiaohongshu.com/explore/mock-note-001",
                        "summary_markdown": "# 总结",
                    },
                    "request_id": "r3",
                },
            )
        return httpx.Response(404, json={})

    with _client_with_handler(handler) as client:
        result = check_xhs_summarize_url_mock(client)
    assert result.status == "pass"


def test_check_xhs_summarize_url_mock_fail_on_unexpected_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/xiaohongshu/summarize-url":
            return httpx.Response(
                400,
                json={
                    "ok": False,
                    "code": "INVALID_INPUT",
                    "message": "url invalid",
                    "data": None,
                    "request_id": "r4",
                },
            )
        return httpx.Response(404, json={})

    with _client_with_handler(handler) as client:
        result = check_xhs_summarize_url_mock(client)
    assert result.status == "fail"
    assert "期望 200" in result.message
