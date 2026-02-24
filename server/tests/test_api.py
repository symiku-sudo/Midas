from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes import (
    _get_xiaohongshu_sync_job_manager,
    _get_xiaohongshu_sync_service,
)
from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def _reset_xiaohongshu_state() -> None:
    _get_xiaohongshu_sync_service.cache_clear()
    _get_xiaohongshu_sync_job_manager.cache_clear()
    get_settings.cache_clear()
    db_path = Path(get_settings().xiaohongshu.db_path)
    if db_path.exists():
        db_path.unlink()


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


def test_xiaohongshu_sync_and_dedupe() -> None:
    _reset_xiaohongshu_state()

    first = client.post("/api/xiaohongshu/sync", json={"limit": 3})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["ok"] is True
    assert first_body["data"]["fetched_count"] == 3
    assert first_body["data"]["new_count"] == 3
    assert first_body["data"]["skipped_count"] == 0
    assert first_body["data"]["failed_count"] == 0
    assert first_body["data"]["circuit_opened"] is False
    assert len(first_body["data"]["summaries"]) == 3

    second = client.post("/api/xiaohongshu/sync", json={"limit": 3})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["ok"] is True
    assert second_body["data"]["fetched_count"] == 3
    assert second_body["data"]["new_count"] == 0
    assert second_body["data"]["skipped_count"] == 3
    assert second_body["data"]["failed_count"] == 0


def test_xiaohongshu_sync_limit_exceeded() -> None:
    _reset_xiaohongshu_state()

    resp = client.post("/api/xiaohongshu/sync", json={"limit": 99})
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "INVALID_INPUT"


def test_xiaohongshu_sync_job_progress_and_result() -> None:
    _reset_xiaohongshu_state()

    create_resp = client.post("/api/xiaohongshu/sync/jobs", json={"limit": 2})
    assert create_resp.status_code == 200
    create_body = create_resp.json()
    assert create_body["ok"] is True
    job_id = create_body["data"]["job_id"]
    assert job_id

    final_body: dict | None = None
    for _ in range(30):
        status_resp = client.get(f"/api/xiaohongshu/sync/jobs/{job_id}")
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["ok"] is True
        assert body["data"]["job_id"] == job_id
        assert body["data"]["status"] in {"pending", "running", "succeeded", "failed"}

        if body["data"]["status"] in {"succeeded", "failed"}:
            final_body = body
            break
        time.sleep(0.05)

    assert final_body is not None
    assert final_body["data"]["status"] == "succeeded"
    assert final_body["data"]["result"]["new_count"] == 2
    assert final_body["data"]["result"]["fetched_count"] == 2


def test_xiaohongshu_sync_job_not_found() -> None:
    _reset_xiaohongshu_state()

    resp = client.get("/api/xiaohongshu/sync/jobs/not-exists")
    assert resp.status_code == 404
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "INVALID_INPUT"
