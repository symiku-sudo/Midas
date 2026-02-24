from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["code"] == "OK"
    assert body["data"]["status"] == "ok"
    assert body["request_id"]


def test_bilibili_invalid_url() -> None:
    resp = client.post(
        "/api/bilibili/summarize",
        json={"video_url": "https://example.com/video/123"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "INVALID_INPUT"
