from __future__ import annotations

import os
from pathlib import Path

import app.api.routes as routes_module
from fastapi.testclient import TestClient

from app.api.routes import (
    _get_editable_config_service,
    _get_note_library_service,
    _get_xiaohongshu_sync_service,
)
from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def _reset_xiaohongshu_state() -> None:
    _get_editable_config_service.cache_clear()
    _get_note_library_service.cache_clear()
    _get_xiaohongshu_sync_service.cache_clear()
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

    summarize_resp = client.post(
        "/api/xiaohongshu/summarize-url",
        json={"url": "https://www.xiaohongshu.com/explore/mock-note-001"},
    )
    assert summarize_resp.status_code == 200
    summarize_body = summarize_resp.json()
    assert summarize_body["ok"] is True
    first_summary = summarize_body["data"]

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
    service = _get_xiaohongshu_sync_service()
    assert service._repository.is_synced(first_summary["note_id"]) is True


def test_prune_unsaved_xiaohongshu_synced_notes() -> None:
    _reset_xiaohongshu_state()

    first_resp = client.post(
        "/api/xiaohongshu/summarize-url",
        json={"url": "https://www.xiaohongshu.com/explore/mock-note-001"},
    )
    assert first_resp.status_code == 200
    second_resp = client.post(
        "/api/xiaohongshu/summarize-url",
        json={"url": "https://www.xiaohongshu.com/explore/mock-note-002"},
    )
    assert second_resp.status_code == 200
    summaries = [first_resp.json()["data"], second_resp.json()["data"]]

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


def test_xiaohongshu_auth_update_from_client() -> None:
    _reset_xiaohongshu_state()
    previous_cookie = os.environ.get("XHS_HEADER_COOKIE")
    previous_ua = os.environ.get("XHS_HEADER_USER_AGENT")
    previous_origin = os.environ.get("XHS_HEADER_ORIGIN")
    previous_referer = os.environ.get("XHS_HEADER_REFERER")

    try:
        resp = client.post(
            "/api/xiaohongshu/auth/update",
            json={
                "cookie": "a=1; b=2; c=3",
                "user_agent": "Mozilla/5.0 (Linux; Android 14)",
                "origin": "https://www.xiaohongshu.com",
                "referer": "https://www.xiaohongshu.com/",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["cookie_pairs"] == 3
        assert body["data"]["non_empty_keys"] == 4
        assert "XHS_HEADER_COOKIE" in body["data"]["updated_keys"]
        assert os.environ.get("XHS_HEADER_COOKIE") == "a=1; b=2; c=3"
        assert os.environ.get("XHS_HEADER_USER_AGENT") == "Mozilla/5.0 (Linux; Android 14)"
    finally:
        if previous_cookie is None:
            os.environ.pop("XHS_HEADER_COOKIE", None)
        else:
            os.environ["XHS_HEADER_COOKIE"] = previous_cookie
        if previous_ua is None:
            os.environ.pop("XHS_HEADER_USER_AGENT", None)
        else:
            os.environ["XHS_HEADER_USER_AGENT"] = previous_ua
        if previous_origin is None:
            os.environ.pop("XHS_HEADER_ORIGIN", None)
        else:
            os.environ["XHS_HEADER_ORIGIN"] = previous_origin
        if previous_referer is None:
            os.environ.pop("XHS_HEADER_REFERER", None)
        else:
            os.environ["XHS_HEADER_REFERER"] = previous_referer


def test_xiaohongshu_auth_update_rejects_empty_cookie() -> None:
    _reset_xiaohongshu_state()
    resp = client.post(
        "/api/xiaohongshu/auth/update",
        json={"cookie": "  "},
    )
    assert resp.status_code == 422 or resp.status_code == 400
    if resp.status_code == 400:
        body = resp.json()
        assert body["ok"] is False
        assert body["code"] == "INVALID_INPUT"


def test_xiaohongshu_auth_update_rejects_guest_identity(monkeypatch) -> None:
    _reset_xiaohongshu_state()

    async def _fake_probe(**_kwargs):
        return "guest-user-id", True

    monkeypatch.setattr(routes_module, "_probe_xiaohongshu_web_identity", _fake_probe)

    resp = client.post(
        "/api/xiaohongshu/auth/update",
        json={
            "cookie": "a=1; b=2",
            "user_agent": "Mozilla/5.0 (Linux; Android 14)",
            "origin": "https://www.xiaohongshu.com",
            "referer": "https://www.xiaohongshu.com/",
        },
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "AUTH_EXPIRED"
    assert "游客态" in body["message"]


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
