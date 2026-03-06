from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import app.api.routes as routes_module
from fastapi.testclient import TestClient

from app.api.routes import (
    _get_editable_config_service,
    _get_finance_signals_service,
    _get_note_library_service,
    _get_xiaohongshu_sync_service,
)
from app.core.config import get_settings
from app.main import app
from app.models.schemas import FinanceSignalsData, FinanceWatchlistItem
from app.repositories.note_repo import NoteLibraryRepository

client = TestClient(app)


def _notes_db_path() -> Path:
    return Path(get_settings().xiaohongshu.db_path)


def _notes_backup_dir() -> Path:
    return _notes_db_path().parent / "backups"


def _timestamped_backup_files() -> list[Path]:
    db_path = _notes_db_path()
    files = sorted(_notes_backup_dir().glob(f"{db_path.stem}_*.db"))
    return [path for path in files if not path.name.endswith("_latest.db")]


def _reset_xiaohongshu_state() -> None:
    _get_editable_config_service.cache_clear()
    _get_finance_signals_service.cache_clear()
    _get_note_library_service.cache_clear()
    _get_xiaohongshu_sync_service.cache_clear()
    get_settings.cache_clear()
    db_path = _notes_db_path()
    if db_path.exists():
        db_path.unlink()
    backup_dir = _notes_backup_dir()
    if backup_dir.exists():
        shutil.rmtree(backup_dir)


def test_health_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["code"] == "OK"
    assert body["data"]["status"] == "ok"
    assert body["request_id"]


def test_finance_signals_ok(monkeypatch) -> None:
    class _FakeFinanceSignalsService:
        def get_dashboard_state(self) -> FinanceSignalsData:
            return FinanceSignalsData(
                update_time="2026-03-05 12:00:00",
                watchlist_preview=[
                    FinanceWatchlistItem(
                        name="布伦特原油",
                        symbol="BZ=F",
                        price=91.23,
                        change_pct="+1.2%",
                        alert_hint=">90",
                    )
                ],
                ai_insight_text="行情警报：布伦特原油（BZ=F）触发阈值。",
            )

    monkeypatch.setattr(
        routes_module,
        "_get_finance_signals_service",
        lambda: _FakeFinanceSignalsService(),
    )

    resp = client.get("/api/finance/signals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["code"] == "OK"
    assert body["data"]["update_time"] == "2026-03-05 12:00:00"
    assert body["data"]["watchlist_preview"][0]["symbol"] == "BZ=F"
    assert body["data"]["watchlist_preview"][0]["price"] == 91.23
    assert body["data"]["watchlist_preview"][0]["alert_hint"] == ">90"
    assert body["data"]["ai_insight_text"]


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
    assert "评论区洞察（含点赞权重）" in body["data"]["summary_markdown"]


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
    backup_files = _timestamped_backup_files()
    assert len(backup_files) == 1
    assert backup_files[0].is_file()
    db_path = _notes_db_path()
    suffix = db_path.suffix or ".db"
    latest_backup = _notes_backup_dir() / f"{db_path.stem}_latest{suffix}"
    assert latest_backup.exists()

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
    backup_files = _timestamped_backup_files()
    assert len(backup_files) == 1
    assert backup_files[0].is_file()

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


def test_notes_merge_lifecycle_commit_rollback_and_finalize() -> None:
    _reset_xiaohongshu_state()

    first_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "summary_markdown": "# AI 总结\n\n这是第一条合并测试内容。",
            "elapsed_ms": 100,
            "transcript_chars": 1000,
            "title": "AI 合并测试",
        },
    )
    assert first_save.status_code == 200
    first_note_id = first_save.json()["data"]["note_id"]

    second_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mE",
            "summary_markdown": "# AI 总结\n\n这是第二条合并测试内容。",
            "elapsed_ms": 200,
            "transcript_chars": 2000,
            "title": "AI 合并测试 进阶",
        },
    )
    assert second_save.status_code == 200
    second_note_id = second_save.json()["data"]["note_id"]

    suggest_resp = client.post(
        "/api/notes/merge/suggest",
        json={"source": "bilibili", "limit": 20, "min_score": 0.1},
    )
    assert suggest_resp.status_code == 200
    suggest_body = suggest_resp.json()
    assert suggest_body["ok"] is True
    assert suggest_body["data"]["total"] >= 1
    candidate = suggest_body["data"]["items"][0]
    assert candidate["source"] == "bilibili"
    candidate_note_ids = set(candidate["note_ids"])
    assert {first_note_id, second_note_id}.issubset(candidate_note_ids)

    preview_resp = client.post(
        "/api/notes/merge/preview",
        json={
            "source": "bilibili",
            "note_ids": [first_note_id, second_note_id],
        },
    )
    assert preview_resp.status_code == 200
    preview_body = preview_resp.json()
    assert preview_body["ok"] is True
    assert preview_body["data"]["source"] == "bilibili"
    assert preview_body["data"]["merged_title"]
    assert preview_body["data"]["merged_summary_markdown"]
    merged_markdown = preview_body["data"]["merged_summary_markdown"]
    assert "## 差异与冲突" in merged_markdown
    last_h2 = ""
    for raw in merged_markdown.strip().splitlines():
        line = raw.strip()
        if line.startswith("## "):
            last_h2 = line
    assert last_h2 == "## 差异与冲突"

    commit_resp = client.post(
        "/api/notes/merge/commit",
        json={
            "source": "bilibili",
            "note_ids": [first_note_id, second_note_id],
        },
    )
    assert commit_resp.status_code == 200
    commit_body = commit_resp.json()
    assert commit_body["ok"] is True
    assert commit_body["data"]["status"] == "MERGED_PENDING_CONFIRM"
    merge_id = commit_body["data"]["merge_id"]

    list_after_commit = client.get("/api/notes/bilibili")
    assert list_after_commit.status_code == 200
    list_after_commit_body = list_after_commit.json()
    assert list_after_commit_body["data"]["total"] == 3
    merged_items = [
        item
        for item in list_after_commit_body["data"]["items"]
        if str(item.get("note_id", "")).startswith("merged_note_")
    ]
    assert len(merged_items) == 1
    merged_summary = str(merged_items[0]["summary_markdown"])
    assert "## 原始笔记来源" in merged_summary
    assert "[AI 合并测试](<https://www.bilibili.com/video/BV1xx411c7mD>)" in merged_summary
    assert "[AI 合并测试 进阶](<https://www.bilibili.com/video/BV1xx411c7mE>)" in merged_summary

    rollback_resp = client.post(
        "/api/notes/merge/rollback",
        json={"merge_id": merge_id},
    )
    assert rollback_resp.status_code == 200
    rollback_body = rollback_resp.json()
    assert rollback_body["ok"] is True
    assert rollback_body["data"]["status"] == "ROLLED_BACK"
    assert rollback_body["data"]["deleted_merged_count"] == 1

    list_after_rollback = client.get("/api/notes/bilibili")
    assert list_after_rollback.status_code == 200
    assert list_after_rollback.json()["data"]["total"] == 2

    second_commit_resp = client.post(
        "/api/notes/merge/commit",
        json={
            "source": "bilibili",
            "note_ids": [first_note_id, second_note_id],
        },
    )
    assert second_commit_resp.status_code == 200
    second_merge_id = second_commit_resp.json()["data"]["merge_id"]

    finalize_resp = client.post(
        "/api/notes/merge/finalize",
        json={"merge_id": second_merge_id, "confirm_destructive": True},
    )
    assert finalize_resp.status_code == 200
    finalize_body = finalize_resp.json()
    assert finalize_body["ok"] is True
    assert finalize_body["data"]["status"] == "FINALIZED_DESTRUCTIVE"
    assert finalize_body["data"]["deleted_source_count"] == 2

    list_after_finalize = client.get("/api/notes/bilibili")
    assert list_after_finalize.status_code == 200
    assert list_after_finalize.json()["data"]["total"] == 1

    rollback_after_finalize = client.post(
        "/api/notes/merge/rollback",
        json={"merge_id": second_merge_id},
    )
    assert rollback_after_finalize.status_code == 409
    rollback_after_finalize_body = rollback_after_finalize.json()
    assert rollback_after_finalize_body["ok"] is False
    assert rollback_after_finalize_body["code"] == "MERGE_NOT_ALLOWED"


def test_notes_merge_finalize_requires_destructive_confirmation() -> None:
    _reset_xiaohongshu_state()
    save_resp = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "summary_markdown": "# 测试",
            "elapsed_ms": 10,
            "transcript_chars": 20,
            "title": "测试标题",
        },
    )
    assert save_resp.status_code == 200
    first_note_id = save_resp.json()["data"]["note_id"]

    save_resp2 = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mE",
            "summary_markdown": "# 测试",
            "elapsed_ms": 11,
            "transcript_chars": 22,
            "title": "测试标题2",
        },
    )
    assert save_resp2.status_code == 200
    second_note_id = save_resp2.json()["data"]["note_id"]

    commit_resp = client.post(
        "/api/notes/merge/commit",
        json={
            "source": "bilibili",
            "note_ids": [first_note_id, second_note_id],
        },
    )
    assert commit_resp.status_code == 200
    merge_id = commit_resp.json()["data"]["merge_id"]

    finalize_resp = client.post(
        "/api/notes/merge/finalize",
        json={"merge_id": merge_id, "confirm_destructive": False},
    )
    assert finalize_resp.status_code == 400
    body = finalize_resp.json()
    assert body["ok"] is False
    assert body["code"] == "INVALID_INPUT"


def test_existing_merge_note_format_is_refreshed_for_legacy_markdown() -> None:
    _reset_xiaohongshu_state()
    first_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "summary_markdown": "# 测试一",
            "elapsed_ms": 10,
            "transcript_chars": 20,
            "title": "历史标题一",
        },
    )
    assert first_save.status_code == 200
    first_note_id = first_save.json()["data"]["note_id"]

    second_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mE",
            "summary_markdown": "# 测试二",
            "elapsed_ms": 11,
            "transcript_chars": 22,
            "title": "历史标题二",
        },
    )
    assert second_save.status_code == 200
    second_note_id = second_save.json()["data"]["note_id"]

    commit_resp = client.post(
        "/api/notes/merge/commit",
        json={
            "source": "bilibili",
            "note_ids": [first_note_id, second_note_id],
        },
    )
    assert commit_resp.status_code == 200
    merged_note_id = commit_resp.json()["data"]["merged_note_id"]

    legacy_markdown = "# 旧版合并笔记\n\n## 差异与冲突\n\n- 旧格式内容"
    repo = NoteLibraryRepository(get_settings().xiaohongshu.db_path)
    updated_count = repo.update_bilibili_note_summary(
        note_id=merged_note_id,
        summary_markdown=legacy_markdown,
    )
    assert updated_count == 1

    routes_module._get_note_library_service.cache_clear()

    list_resp = client.get("/api/notes/bilibili")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    merged_items = [
        item
        for item in list_body["data"]["items"]
        if item["note_id"] == merged_note_id
    ]
    assert len(merged_items) == 1
    refreshed_summary = merged_items[0]["summary_markdown"]
    assert "## 原始笔记来源" in refreshed_summary
    assert "[历史标题一](<https://www.bilibili.com/video/BV1xx411c7mD>)" in refreshed_summary
    assert "[历史标题二](<https://www.bilibili.com/video/BV1xx411c7mE>)" in refreshed_summary


def test_legacy_merge_history_without_titles_is_rehydrated_from_markdown_links() -> None:
    _reset_xiaohongshu_state()
    first_url = "https://www.bilibili.com/video/BV1xx411c7mD"
    second_url = "https://www.bilibili.com/video/BV1xx411c7mE"

    first_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": first_url,
            "summary_markdown": "# 测试一",
            "elapsed_ms": 10,
            "transcript_chars": 20,
            "title": "历史标题一",
        },
    )
    assert first_save.status_code == 200
    first_note_id = first_save.json()["data"]["note_id"]

    second_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": second_url,
            "summary_markdown": "# 测试二",
            "elapsed_ms": 11,
            "transcript_chars": 22,
            "title": "历史标题二",
        },
    )
    assert second_save.status_code == 200
    second_note_id = second_save.json()["data"]["note_id"]

    commit_resp = client.post(
        "/api/notes/merge/commit",
        json={
            "source": "bilibili",
            "note_ids": [first_note_id, second_note_id],
        },
    )
    assert commit_resp.status_code == 200
    merge_data = commit_resp.json()["data"]
    merge_id = merge_data["merge_id"]
    merged_note_id = merge_data["merged_note_id"]

    finalize_resp = client.post(
        "/api/notes/merge/finalize",
        json={"merge_id": merge_id, "confirm_destructive": True},
    )
    assert finalize_resp.status_code == 200

    legacy_markdown = (
        "# 旧版合并笔记\n\n"
        "## 来源\n\n"
        f"- [历史标题一](<{first_url}>)\n"
        f"- [历史标题二](<{second_url}>)"
    )
    repo = NoteLibraryRepository(get_settings().xiaohongshu.db_path)
    assert (
        repo.update_bilibili_note_summary(
            note_id=merged_note_id,
            summary_markdown=legacy_markdown,
        )
        == 1
    )
    assert (
        repo.update_merge_history_field_decisions(
            merge_id=merge_id,
            field_decisions={
                "merged_title": "旧版合并笔记",
                "merged_summary_markdown": legacy_markdown,
                "source_refs": [first_url, second_url],
                "lineage_source_ids": [first_note_id, second_note_id],
                "source_link_snapshot": {
                    first_note_id: first_note_id,
                    second_note_id: second_note_id,
                },
                "conflict_markers": [],
            },
        )
        == 1
    )

    routes_module._get_note_library_service.cache_clear()

    list_resp = client.get("/api/notes/bilibili")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    merged_items = [
        item
        for item in list_body["data"]["items"]
        if item["note_id"] == merged_note_id
    ]
    assert len(merged_items) == 1
    refreshed_summary = merged_items[0]["summary_markdown"]
    assert "## 原始笔记来源" in refreshed_summary
    assert f"[历史标题一](<{first_url}>)" in refreshed_summary
    assert f"[历史标题二](<{second_url}>)" in refreshed_summary
    assert f"- [{first_note_id}](<{first_url}>)" not in refreshed_summary
    assert f"- [{second_note_id}](<{second_url}>)" not in refreshed_summary

    refreshed_history = repo.get_merge_history(merge_id)
    assert refreshed_history is not None
    field_decisions = json.loads(str(refreshed_history["field_decisions"]))
    assert field_decisions["lineage_sources"] == [
        {
            "note_id": first_note_id,
            "title": "历史标题一",
            "source_ref": first_url,
        },
        {
            "note_id": second_note_id,
            "title": "历史标题二",
            "source_ref": second_url,
        },
    ]
    assert field_decisions["source_ref_by_note_id"] == {
        first_note_id: first_url,
        second_note_id: second_url,
    }


def test_existing_merge_history_with_duplicate_source_refs_is_collapsed_on_refresh() -> None:
    _reset_xiaohongshu_state()
    first_url = "https://www.bilibili.com/video/BV1xx411c7mD"
    second_url = "https://www.bilibili.com/video/BV1xx411c7mE"

    first_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": first_url,
            "summary_markdown": "# 测试一",
            "elapsed_ms": 10,
            "transcript_chars": 20,
            "title": "历史标题一",
        },
    )
    assert first_save.status_code == 200
    first_note_id = first_save.json()["data"]["note_id"]

    second_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": second_url,
            "summary_markdown": "# 测试二",
            "elapsed_ms": 11,
            "transcript_chars": 22,
            "title": "历史标题二",
        },
    )
    assert second_save.status_code == 200
    second_note_id = second_save.json()["data"]["note_id"]

    commit_resp = client.post(
        "/api/notes/merge/commit",
        json={
            "source": "bilibili",
            "note_ids": [first_note_id, second_note_id],
        },
    )
    assert commit_resp.status_code == 200
    merge_data = commit_resp.json()["data"]
    merge_id = merge_data["merge_id"]
    merged_note_id = merge_data["merged_note_id"]

    repo = NoteLibraryRepository(get_settings().xiaohongshu.db_path)
    legacy_markdown = "# 旧版合并笔记\n\n- 占位内容"
    assert (
        repo.update_bilibili_note_summary(
            note_id=merged_note_id,
            summary_markdown=legacy_markdown,
        )
        == 1
    )
    assert (
        repo.update_merge_history_field_decisions(
            merge_id=merge_id,
            field_decisions={
                "merged_title": "旧版合并笔记",
                "merged_summary_markdown": legacy_markdown,
                "source_refs": [first_url, second_url],
                "source_ref_by_note_id": {
                    first_note_id: first_url,
                    "alias_note_a": first_url,
                    second_note_id: second_url,
                    "alias_note_b": second_url,
                },
                "lineage_source_ids": [first_note_id, second_note_id],
                "lineage_sources": [
                    {
                        "note_id": first_note_id,
                        "title": "历史标题一",
                        "source_ref": first_url,
                    },
                    {
                        "note_id": "alias_note_a",
                        "title": "历史标题一（重复）",
                        "source_ref": first_url,
                    },
                    {
                        "note_id": second_note_id,
                        "title": "历史标题二",
                        "source_ref": second_url,
                    },
                    {
                        "note_id": "alias_note_b",
                        "title": "历史标题二（重复）",
                        "source_ref": second_url,
                    },
                ],
                "source_link_snapshot": {
                    first_note_id: first_note_id,
                    second_note_id: second_note_id,
                },
                "conflict_markers": [],
            },
        )
        == 1
    )

    routes_module._get_note_library_service.cache_clear()

    list_resp = client.get("/api/notes/bilibili")
    assert list_resp.status_code == 200
    merged_items = [
        item
        for item in list_resp.json()["data"]["items"]
        if item["note_id"] == merged_note_id
    ]
    assert len(merged_items) == 1
    refreshed_summary = merged_items[0]["summary_markdown"]
    assert refreshed_summary.count(f"(<{first_url}>)") == 1
    assert refreshed_summary.count(f"(<{second_url}>)") == 1

    refreshed_history = repo.get_merge_history(merge_id)
    assert refreshed_history is not None
    field_decisions = json.loads(str(refreshed_history["field_decisions"]))
    lineage_sources = field_decisions["lineage_sources"]
    assert len(lineage_sources) == 2
    assert {item["source_ref"] for item in lineage_sources} == {first_url, second_url}


def test_notes_merge_suggest_default_threshold_hits_summary_and_keyword_similarity() -> None:
    _reset_xiaohongshu_state()
    first_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "summary_markdown": "# Claude Code\n\nHook 使用与自动化实践。",
            "elapsed_ms": 10,
            "transcript_chars": 20,
            "title": "Claude Code 实战一",
        },
    )
    assert first_save.status_code == 200
    first_note_id = first_save.json()["data"]["note_id"]

    second_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mE",
            "summary_markdown": "# Claude Code\n\n团队工作流与 Hook 设计。",
            "elapsed_ms": 11,
            "transcript_chars": 22,
            "title": "Claude Code 实战二",
        },
    )
    assert second_save.status_code == 200
    second_note_id = second_save.json()["data"]["note_id"]

    suggest_resp = client.post(
        "/api/notes/merge/suggest",
        json={"source": "bilibili", "limit": 20},
    )
    assert suggest_resp.status_code == 200
    body = suggest_resp.json()
    assert body["ok"] is True
    assert body["data"]["total"] >= 1
    pair_found = False
    for item in body["data"]["items"]:
        note_ids = set(item["note_ids"])
        if {first_note_id, second_note_id} == note_ids:
            pair_found = True
            assert item["relation_level"] == "STRONG"
            assert "KEYWORD_OVERLAP" in item["reason_codes"]
            assert "SUMMARY_SIMILAR" in item["reason_codes"]
            assert "TITLE_SIMILAR" not in item["reason_codes"]
            break
    assert pair_found is True


def test_notes_merge_suggest_default_threshold_allows_pair_without_title_similarity() -> None:
    _reset_xiaohongshu_state()
    first_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mF",
            "summary_markdown": (
                "# Agent 时代\n\n"
                "Skills 已经爆火，但企业落地仍受合规、审计与成本控制约束。"
            ),
            "elapsed_ms": 10,
            "transcript_chars": 20,
            "title": "再次感叹：请不要再做 App、网站、小程序了",
        },
    )
    assert first_save.status_code == 200

    second_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mG",
            "summary_markdown": (
                "# 企业为何不用 Skills\n\n"
                "Skills 已经爆火，但企业落地仍受合规、审计与成本控制约束。"
            ),
            "elapsed_ms": 11,
            "transcript_chars": 22,
            "title": "Skills爆火，但企业为什么不敢用？",
        },
    )
    assert second_save.status_code == 200

    suggest_resp = client.post(
        "/api/notes/merge/suggest",
        json={"source": "bilibili", "limit": 20},
    )
    assert suggest_resp.status_code == 200
    body = suggest_resp.json()
    assert body["ok"] is True

    pair_found = False
    for item in body["data"]["items"]:
        note_ids = set(item["note_ids"])
        if {first_save.json()["data"]["note_id"], second_save.json()["data"]["note_id"]} == note_ids:
            pair_found = True
            assert item["relation_level"] == "STRONG"
            assert "SUMMARY_SIMILAR" in item["reason_codes"]
            assert "TITLE_SIMILAR" not in item["reason_codes"]
            break
    assert pair_found is True


def test_notes_merge_suggest_marks_medium_related_pair_as_weak() -> None:
    _reset_xiaohongshu_state()
    first_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mK",
            "summary_markdown": (
                "# Agent 治理\n\n"
                "企业落地 Agent 要先做权限边界、审计日志和成本看板。"
            ),
            "elapsed_ms": 10,
            "transcript_chars": 20,
            "title": "AI工程师必看：企业级Skill到底怎么设计",
        },
    )
    assert first_save.status_code == 200
    first_note_id = first_save.json()["data"]["note_id"]

    second_save = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mL",
            "summary_markdown": (
                "# Agent 实施\n\n"
                "企业部署智能体之前，应先完成权限设计、审计闭环，并追踪投入产出。"
            ),
            "elapsed_ms": 11,
            "transcript_chars": 22,
            "title": "Skills爆火，但企业为什么不敢用？",
        },
    )
    assert second_save.status_code == 200
    second_note_id = second_save.json()["data"]["note_id"]

    default_suggest_resp = client.post(
        "/api/notes/merge/suggest",
        json={"source": "bilibili", "limit": 20},
    )
    assert default_suggest_resp.status_code == 200
    default_items = default_suggest_resp.json()["data"]["items"]
    assert all(item["relation_level"] == "STRONG" for item in default_items)
    assert all(
        set(item["note_ids"]) != {first_note_id, second_note_id}
        for item in default_items
    )

    suggest_resp = client.post(
        "/api/notes/merge/suggest",
        json={"source": "bilibili", "limit": 20, "include_weak": True},
    )
    assert suggest_resp.status_code == 200
    body = suggest_resp.json()
    assert body["ok"] is True

    pair_found = False
    for item in body["data"]["items"]:
        note_ids = set(item["note_ids"])
        if {first_note_id, second_note_id} == note_ids:
            pair_found = True
            assert item["score"] >= 0.35
            assert item["relation_level"] == "WEAK"
            assert "RELATION_WEAK" in item["reason_codes"]
            assert "SUMMARY_SIMILAR" in item["reason_codes"]
            assert "TITLE_SIMILAR" not in item["reason_codes"]
            break
    assert pair_found is True


def test_notes_merge_suggest_hides_stale_pairs_after_commit_until_refresh() -> None:
    _reset_xiaohongshu_state()

    save_a = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mH",
            "summary_markdown": "# Claude Code\n\nHook 流程与团队协作实践。",
            "elapsed_ms": 10,
            "transcript_chars": 20,
            "title": "Claude Code 实战一",
        },
    )
    assert save_a.status_code == 200
    note_a = save_a.json()["data"]["note_id"]

    save_b = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mI",
            "summary_markdown": "# Claude Code\n\nHook 流程与团队协作实践（二）。",
            "elapsed_ms": 11,
            "transcript_chars": 22,
            "title": "Claude Code 实战二",
        },
    )
    assert save_b.status_code == 200
    note_b = save_b.json()["data"]["note_id"]

    save_c = client.post(
        "/api/notes/bilibili/save",
        json={
            "video_url": "https://www.bilibili.com/video/BV1xx411c7mJ",
            "summary_markdown": "# Claude Code\n\nHook 流程与团队协作实践（三）。",
            "elapsed_ms": 12,
            "transcript_chars": 24,
            "title": "Claude Code 实战三",
        },
    )
    assert save_c.status_code == 200
    note_c = save_c.json()["data"]["note_id"]

    before_suggest = client.post(
        "/api/notes/merge/suggest",
        json={"source": "bilibili", "limit": 20, "min_score": 0.1},
    )
    assert before_suggest.status_code == 200
    before_items = before_suggest.json()["data"]["items"]
    before_pairs = {frozenset(item["note_ids"]) for item in before_items}
    assert frozenset([note_a, note_b]) in before_pairs
    assert frozenset([note_b, note_c]) in before_pairs

    commit_resp = client.post(
        "/api/notes/merge/commit",
        json={"source": "bilibili", "note_ids": [note_a, note_b]},
    )
    assert commit_resp.status_code == 200

    after_suggest = client.post(
        "/api/notes/merge/suggest",
        json={"source": "bilibili", "limit": 20, "min_score": 0.1},
    )
    assert after_suggest.status_code == 200
    after_items = after_suggest.json()["data"]["items"]
    assert after_items == []
    for item in after_items:
        assert note_a not in item["note_ids"]
        assert note_b not in item["note_ids"]


def test_xiaohongshu_summarize_url_dedup_uses_merge_canonical_after_finalize() -> None:
    _reset_xiaohongshu_state()

    first_url = "https://www.xiaohongshu.com/explore/mock-note-001"
    second_url = "https://www.xiaohongshu.com/explore/mock-note-002"

    first_summary_resp = client.post(
        "/api/xiaohongshu/summarize-url",
        json={"url": first_url},
    )
    assert first_summary_resp.status_code == 200
    first_summary = first_summary_resp.json()["data"]

    second_summary_resp = client.post(
        "/api/xiaohongshu/summarize-url",
        json={"url": second_url},
    )
    assert second_summary_resp.status_code == 200
    second_summary = second_summary_resp.json()["data"]

    save_batch_resp = client.post(
        "/api/notes/xiaohongshu/save-batch",
        json={"notes": [first_summary, second_summary]},
    )
    assert save_batch_resp.status_code == 200
    assert save_batch_resp.json()["data"]["saved_count"] == 2

    commit_resp = client.post(
        "/api/notes/merge/commit",
        json={
            "source": "xiaohongshu",
            "note_ids": [first_summary["note_id"], second_summary["note_id"]],
        },
    )
    assert commit_resp.status_code == 200
    merge_id = commit_resp.json()["data"]["merge_id"]

    finalize_resp = client.post(
        "/api/notes/merge/finalize",
        json={"merge_id": merge_id, "confirm_destructive": True},
    )
    assert finalize_resp.status_code == 200
    merged_note_id = finalize_resp.json()["data"]["kept_merged_note_id"]

    list_resp = client.get("/api/notes/xiaohongshu")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["data"]["total"] == 1
    assert list_body["data"]["items"][0]["note_id"] == merged_note_id

    dedup_resp = client.post(
        "/api/xiaohongshu/summarize-url",
        json={"url": first_url},
    )
    assert dedup_resp.status_code == 200
    dedup_body = dedup_resp.json()
    assert dedup_body["ok"] is True
    assert dedup_body["data"]["note_id"] == first_summary["note_id"]
    assert "## 差异与冲突" in dedup_body["data"]["summary_markdown"]

    list_again_resp = client.get("/api/notes/xiaohongshu")
    assert list_again_resp.status_code == 200
    assert list_again_resp.json()["data"]["total"] == 1


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
