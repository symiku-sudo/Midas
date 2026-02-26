from __future__ import annotations

import os
import time
from pathlib import Path

import app.api.routes as routes_module
from fastapi.testclient import TestClient

from app.api.routes import (
    _get_editable_config_service,
    _get_note_library_service,
    _get_xiaohongshu_sync_job_manager,
    _get_xiaohongshu_sync_service,
)
from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def _reset_xiaohongshu_state() -> None:
    _get_editable_config_service.cache_clear()
    _get_note_library_service.cache_clear()
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
    assert second_body["data"]["fetched_count"] == 5
    assert second_body["data"]["new_count"] == 2
    assert second_body["data"]["skipped_count"] == 3
    assert second_body["data"]["failed_count"] == 0
    assert len(second_body["data"]["summaries"]) == 2


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


def test_xiaohongshu_sync_cooldown_status() -> None:
    _reset_xiaohongshu_state()
    service = _get_xiaohongshu_sync_service()
    now = int(time.time())
    service._repository.set_state("last_live_sync_ts", str(now - 11))

    resp = client.get("/api/xiaohongshu/sync/cooldown")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["mode"] in {"mock", "web_readonly"}
    assert data["min_interval_seconds"] >= 0
    if data["mode"] == "web_readonly":
        assert data["last_sync_at_epoch"] == now - 11
        assert data["allowed"] is False
        assert data["remaining_seconds"] > 0
    else:
        assert data["last_sync_at_epoch"] == 0
        assert data["allowed"] is True
        assert data["remaining_seconds"] == 0


def test_xiaohongshu_summarize_single_url() -> None:
    _reset_xiaohongshu_state()

    resp = client.post(
        "/api/xiaohongshu/summarize-url",
        json={"url": "https://www.xiaohongshu.com/explore/mock-note-001"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["note_id"] == "mock-note-001"
    assert body["data"]["source_url"] == "https://www.xiaohongshu.com/explore/mock-note-001"
    assert body["data"]["summary_markdown"]


def test_xiaohongshu_pending_count() -> None:
    _reset_xiaohongshu_state()

    sync_resp = client.post("/api/xiaohongshu/sync", json={"limit": 1})
    assert sync_resp.status_code == 200
    assert sync_resp.json()["data"]["new_count"] == 1

    count_resp = client.get("/api/xiaohongshu/sync/pending-count")
    assert count_resp.status_code == 200
    body = count_resp.json()
    assert body["ok"] is True
    assert body["data"]["mode"] == "mock"
    assert body["data"]["scanned_count"] == 5
    assert body["data"]["pending_count"] == 4


def test_bilibili_saved_notes_crud() -> None:
    _reset_xiaohongshu_state()

    save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "summary_markdown": "# 总结\n\n测试内容",
            "elapsed_ms": 123,
            "transcript_chars": 456,
            "title": "测试B站笔记",
        },
    )
    assert save.status_code == 200
    save_body = save.json()
    assert save_body["ok"] is True
    note_id = save_body["data"]["note_id"]
    assert note_id

    listed = client.get("/api/notes/bilibili")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["ok"] is True
    assert listed_body["data"]["total"] == 1
    assert listed_body["data"]["items"][0]["note_id"] == note_id

    deleted = client.delete(f"/api/notes/bilibili/{note_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_count"] == 1

    listed_after = client.get("/api/notes/bilibili")
    assert listed_after.status_code == 200
    assert listed_after.json()["data"]["total"] == 0


def test_xiaohongshu_saved_notes_crud_and_dedupe_independent() -> None:
    _reset_xiaohongshu_state()

    sync_resp = client.post("/api/xiaohongshu/sync", json={"limit": 1})
    assert sync_resp.status_code == 200
    sync_body = sync_resp.json()
    assert sync_body["ok"] is True
    assert sync_body["data"]["new_count"] == 1
    first_summary = sync_body["data"]["summaries"][0]

    save_resp = client.post(
        "/api/notes/xiaohongshu/save-batch",
        json={"notes": [first_summary]},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["data"]["saved_count"] == 1

    listed = client.get("/api/notes/xiaohongshu")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["data"]["total"] == 1
    note_id = listed_body["data"]["items"][0]["note_id"]

    deleted = client.delete(f"/api/notes/xiaohongshu/{note_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_count"] == 1

    listed_after = client.get("/api/notes/xiaohongshu")
    assert listed_after.status_code == 200
    assert listed_after.json()["data"]["total"] == 0

    # Saved note deletion should not affect xiaohongshu dedupe table.
    sync_again = client.post("/api/xiaohongshu/sync", json={"limit": 1})
    assert sync_again.status_code == 200
    sync_again_body = sync_again.json()
    assert sync_again_body["data"]["new_count"] == 1
    assert sync_again_body["data"]["skipped_count"] == 1
    assert sync_again_body["data"]["summaries"][0]["note_id"] != first_summary["note_id"]


def test_prune_unsaved_xiaohongshu_synced_notes() -> None:
    _reset_xiaohongshu_state()

    sync_resp = client.post("/api/xiaohongshu/sync", json={"limit": 2})
    assert sync_resp.status_code == 200
    sync_body = sync_resp.json()
    assert sync_body["ok"] is True
    summaries = sync_body["data"]["summaries"]
    assert len(summaries) == 2

    save_resp = client.post(
        "/api/notes/xiaohongshu/save-batch",
        json={"notes": [summaries[0]]},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["data"]["saved_count"] == 1

    prune_resp = client.post("/api/notes/xiaohongshu/synced/prune")
    assert prune_resp.status_code == 200
    prune_body = prune_resp.json()
    assert prune_body["ok"] is True
    assert prune_body["data"]["candidate_count"] == 1
    assert prune_body["data"]["deleted_count"] == 1

    prune_again_resp = client.post("/api/notes/xiaohongshu/synced/prune")
    assert prune_again_resp.status_code == 200
    prune_again_body = prune_again_resp.json()
    assert prune_again_body["ok"] is True
    assert prune_again_body["data"]["candidate_count"] == 0
    assert prune_again_body["data"]["deleted_count"] == 0


def test_xiaohongshu_capture_refresh_from_default_har(monkeypatch) -> None:
    _reset_xiaohongshu_state()

    old_cookie = os.environ.get("XHS_HEADER_COOKIE", "")

    def _fake_apply(*, require_cookie: bool = False):
        assert require_cookie is True
        capture = routes_module.xhs_capture_tool.RequestCapture(
            request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page?num=30",
            request_method="GET",
            request_headers={
                "Accept": "application/json",
                "Cookie": "new_cookie=1",
                "User-Agent": "ua-test",
            },
            request_body="",
            inference=None,
        )
        updates = {
            "XHS_REQUEST_URL": capture.request_url,
            "XHS_HEADER_ACCEPT": "application/json",
            "XHS_HEADER_COOKIE": "new_cookie=1",
            "XHS_HEADER_ORIGIN": "",
            "XHS_HEADER_REFERER": "",
            "XHS_HEADER_USER_AGENT": "ua-test",
            "XHS_HEADER_X_S": "",
            "XHS_HEADER_X_S_COMMON": "",
            "XHS_HEADER_X_T": "",
        }
        return "har", Path("/tmp/xhs_detail.har"), capture, updates

    monkeypatch.setattr(
        routes_module.xhs_capture_tool,
        "apply_capture_from_default_auth_source_to_env",
        _fake_apply,
    )

    try:
        resp = client.post("/api/xiaohongshu/capture/refresh")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["request_url_host"] == "edith.xiaohongshu.com"
        assert body["data"]["request_method"] == "GET"
        assert body["data"]["headers_count"] == 3
        assert body["data"]["non_empty_keys"] == 4
        assert "XHS_HEADER_X_T" in body["data"]["empty_keys"]
        assert os.environ.get("XHS_HEADER_COOKIE") == "new_cookie=1"
    finally:
        if old_cookie:
            os.environ["XHS_HEADER_COOKIE"] = old_cookie
        elif "XHS_HEADER_COOKIE" in os.environ:
            os.environ.pop("XHS_HEADER_COOKIE", None)


def test_xiaohongshu_capture_refresh_requires_cookie(monkeypatch) -> None:
    _reset_xiaohongshu_state()

    def _fake_apply(*, require_cookie: bool = False):
        assert require_cookie is True
        raise ValueError("HAR/cURL 未包含 Cookie，请使用包含敏感数据的抓包导出。")

    monkeypatch.setattr(
        routes_module.xhs_capture_tool,
        "apply_capture_from_default_auth_source_to_env",
        _fake_apply,
    )

    resp = client.post("/api/xiaohongshu/capture/refresh")
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "INVALID_INPUT"
    assert "未包含 Cookie" in body["message"]


def test_editable_config_update_and_reset(tmp_path) -> None:
    original_config_path = os.environ.get("MIDAS_CONFIG_PATH", "")
    source_config = Path(original_config_path)
    temp_config = tmp_path / "config.runtime.yaml"
    temp_config.write_text(source_config.read_text(encoding="utf-8"), encoding="utf-8")

    try:
        os.environ["MIDAS_CONFIG_PATH"] = str(temp_config)
        _reset_xiaohongshu_state()

        get_resp = client.get("/api/config/editable")
        assert get_resp.status_code == 200
        get_body = get_resp.json()
        assert get_body["ok"] is True
        assert "api_key" not in get_body["data"]["settings"].get("llm", {})
        assert "cookie" not in get_body["data"]["settings"].get("xiaohongshu", {})

        update_resp = client.put(
            "/api/config/editable",
            json={
                "settings": {
                    "xiaohongshu": {"default_limit": 7},
                    "runtime": {"log_level": "DEBUG"},
                }
            },
        )
        assert update_resp.status_code == 200
        update_body = update_resp.json()
        assert update_body["ok"] is True
        assert update_body["data"]["settings"]["xiaohongshu"]["default_limit"] == 7
        assert update_body["data"]["settings"]["runtime"]["log_level"] == "DEBUG"

        # Verify new default_limit is effective in runtime behavior.
        sync_resp = client.post("/api/xiaohongshu/sync", json={})
        assert sync_resp.status_code == 200
        assert sync_resp.json()["data"]["requested_limit"] == 7

        reset_resp = client.post("/api/config/editable/reset")
        assert reset_resp.status_code == 200
        reset_body = reset_resp.json()
        assert reset_body["ok"] is True
        assert reset_body["data"]["settings"]["xiaohongshu"]["default_limit"] == 20
        assert reset_body["data"]["settings"]["runtime"]["log_level"] == "INFO"
    finally:
        if original_config_path:
            os.environ["MIDAS_CONFIG_PATH"] = original_config_path
        _reset_xiaohongshu_state()


def test_editable_config_rejects_sensitive_keys(tmp_path) -> None:
    original_config_path = os.environ.get("MIDAS_CONFIG_PATH", "")
    source_config = Path(original_config_path)
    temp_config = tmp_path / "config.runtime.yaml"
    temp_config.write_text(source_config.read_text(encoding="utf-8"), encoding="utf-8")

    try:
        os.environ["MIDAS_CONFIG_PATH"] = str(temp_config)
        _reset_xiaohongshu_state()
        resp = client.put(
            "/api/config/editable",
            json={"settings": {"llm": {"api_key": "SHOULD_NOT_PASS"}}},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["ok"] is False
        assert body["code"] == "INVALID_INPUT"
    finally:
        if original_config_path:
            os.environ["MIDAS_CONFIG_PATH"] = original_config_path
        _reset_xiaohongshu_state()
