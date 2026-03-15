from __future__ import annotations

import sqlite3
from pathlib import Path

from app.repositories.note_repo import NoteLibraryRepository


def _update_saved_at(
    *,
    db_path: Path,
    table: str,
    note_id: str,
    saved_at: str,
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            f"UPDATE {table} SET saved_at = ? WHERE note_id = ?",
            (saved_at, note_id),
        )
        conn.commit()


def test_bilibili_saved_at_is_returned_in_utc8(tmp_path: Path) -> None:
    db_path = tmp_path / "notes.db"
    repo = NoteLibraryRepository(str(db_path))
    repo.save_bilibili_note(
        note_id="b1",
        title="测试",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        summary_markdown="# 测试",
        elapsed_ms=1,
        transcript_chars=2,
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_bilibili_notes",
        note_id="b1",
        saved_at="2026-03-01 00:00:00",
    )

    listed = repo.list_bilibili_notes()
    assert listed[0]["saved_at"] == "2026-03-01 08:00:00"

    fetched = repo.get_bilibili_notes_by_ids(["b1"])
    assert fetched[0]["saved_at"] == "2026-03-01 08:00:00"


def test_xiaohongshu_saved_at_is_returned_in_utc8(tmp_path: Path) -> None:
    db_path = tmp_path / "notes.db"
    repo = NoteLibraryRepository(str(db_path))
    repo.save_xiaohongshu_notes(
        [
            {
                "note_id": "x1",
                "title": "测试",
                "source_url": "https://www.xiaohongshu.com/explore/x1",
                "summary_markdown": "# 测试",
            }
        ]
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_xiaohongshu_notes",
        note_id="x1",
        saved_at="2026-03-01 00:00:00",
    )

    listed = repo.list_xiaohongshu_notes()
    assert listed[0]["saved_at"] == "2026-03-01 08:00:00"

    fetched = repo.get_xiaohongshu_notes_by_ids(["x1"])
    assert fetched[0]["saved_at"] == "2026-03-01 08:00:00"


def test_asset_snapshots_can_upsert_list_and_delete(tmp_path: Path) -> None:
    db_path = tmp_path / "notes.db"
    repo = NoteLibraryRepository(str(db_path))

    repo.upsert_asset_snapshot(
        record_id="asset-1",
        saved_at="2026-03-08 10:00:00",
        total_amount_wan=12.5,
        amounts={"stock": 10.0, "gold": 2.5},
    )
    repo.upsert_asset_snapshot(
        record_id="asset-2",
        saved_at="2026-03-08 11:00:00",
        total_amount_wan=15.0,
        amounts={"stock": 12.0, "gold": 3.0},
    )
    repo.upsert_asset_snapshot(
        record_id="asset-1",
        saved_at="2026-03-08 12:00:00",
        total_amount_wan=18.0,
        amounts={"stock": 15.0, "gold": 3.0},
    )

    listed = repo.list_asset_snapshots()
    assert [item["id"] for item in listed] == ["asset-1", "asset-2"]
    assert listed[0]["saved_at"] == "2026-03-08 12:00:00"
    assert listed[0]["amounts"] == {"stock": 15.0, "gold": 3.0}

    deleted = repo.delete_asset_snapshot("asset-2")
    assert deleted == 1
    assert [item["id"] for item in repo.list_asset_snapshots()] == ["asset-1"]


def test_asset_current_can_upsert_and_read(tmp_path: Path) -> None:
    db_path = tmp_path / "notes.db"
    repo = NoteLibraryRepository(str(db_path))

    assert repo.get_asset_current() is None

    repo.upsert_asset_current(
        total_amount_wan=18.6,
        amounts={"stock": 15.1, "gold": 3.5},
    )
    current = repo.get_asset_current()
    assert current == {
        "total_amount_wan": 18.6,
        "amounts": {"gold": 3.5, "stock": 15.1},
    }

    repo.upsert_asset_current(
        total_amount_wan=9.0,
        amounts={"money_market_fund": 9.0},
    )
    current_after = repo.get_asset_current()
    assert current_after == {
        "total_amount_wan": 9.0,
        "amounts": {"money_market_fund": 9.0},
    }


def test_backup_database_prunes_old_timestamp_backups(tmp_path: Path) -> None:
    db_path = tmp_path / "notes.db"
    repo = NoteLibraryRepository(str(db_path))
    repo.save_bilibili_note(
        note_id="b1",
        title="测试",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        summary_markdown="# 测试",
        elapsed_ms=1,
        transcript_chars=2,
    )

    for _ in range(12):
        repo.backup_database(keep_latest_files=10)

    backup_dir = db_path.parent / "backups"
    timestamped = sorted(
        [
            path.name
            for path in backup_dir.glob("notes_*.db")
            if path.name != "notes_latest.db"
        ]
    )
    assert len(timestamped) == 10
    assert (backup_dir / "notes_latest.db").exists()


def test_search_notes_supports_keyword_source_limit_and_offset(tmp_path: Path) -> None:
    db_path = tmp_path / "notes.db"
    repo = NoteLibraryRepository(str(db_path))
    repo.save_bilibili_note(
        note_id="b1",
        title="宏观复盘",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        summary_markdown="# 美联储与降息",
        elapsed_ms=1,
        transcript_chars=2,
    )
    repo.save_bilibili_note(
        note_id="b2",
        title="科技行业",
        video_url="https://www.bilibili.com/video/BV1xx411c7mE",
        summary_markdown="# AI 芯片",
        elapsed_ms=1,
        transcript_chars=2,
    )
    repo.save_xiaohongshu_notes(
        [
            {
                "note_id": "x1",
                "title": "美联储观察",
                "source_url": "https://www.xiaohongshu.com/explore/x1",
                "summary_markdown": "# 降息交易",
            }
        ]
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_bilibili_notes",
        note_id="b1",
        saved_at="2026-03-01 00:00:00",
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_bilibili_notes",
        note_id="b2",
        saved_at="2026-03-02 00:00:00",
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_xiaohongshu_notes",
        note_id="x1",
        saved_at="2026-03-03 00:00:00",
    )

    total_all, all_items = repo.search_notes(keyword="美联储", limit=10, offset=0)
    assert total_all == 2
    assert [item["note_id"] for item in all_items] == ["x1", "b1"]

    total_bili, bili_items = repo.search_notes(
        keyword="AI",
        source="bilibili",
        limit=10,
        offset=0,
    )
    assert total_bili == 1
    assert bili_items[0]["note_id"] == "b2"
    assert bili_items[0]["source"] == "bilibili"

    total_page, page_items = repo.search_notes(limit=1, offset=1)
    assert total_page == 3
    assert len(page_items) == 1


def test_search_notes_supports_time_merged_and_sort_filters(tmp_path: Path) -> None:
    db_path = tmp_path / "notes.db"
    repo = NoteLibraryRepository(str(db_path))
    repo.save_bilibili_note(
        note_id="merged_note_1",
        title="合并后的宏观复盘",
        video_url="https://www.bilibili.com/video/BV1merged",
        summary_markdown="# 合并总结",
        elapsed_ms=1,
        transcript_chars=2,
    )
    repo.save_bilibili_note(
        note_id="b2",
        title="普通笔记",
        video_url="https://www.bilibili.com/video/BV1plain",
        summary_markdown="# 普通",
        elapsed_ms=1,
        transcript_chars=2,
    )
    repo.upsert_source_index_links(
        platform="bilibili",
        mappings={
            "merged_note_1": {
                "canonical_note_id": "merged_note_1",
                "merge_id": "merge-1",
                "state": "MERGED_PENDING_CONFIRM",
            },
            "b2": {
                "canonical_note_id": "b2",
                "merge_id": "",
                "state": "ACTIVE",
            },
        },
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_bilibili_notes",
        note_id="merged_note_1",
        saved_at="2026-03-10 00:00:00",
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_bilibili_notes",
        note_id="b2",
        saved_at="2026-03-11 00:00:00",
    )

    total_merged, merged_items = repo.search_notes(
        source="bilibili",
        merged=True,
        saved_from="2026-03-10 00:00:00",
        saved_to="2026-03-10 23:59:59",
        sort_by="title",
        sort_order="asc",
        limit=10,
        offset=0,
    )
    assert total_merged == 1
    assert merged_items[0]["note_id"] == "merged_note_1"
    assert merged_items[0]["merge_state"] == "MERGED_PENDING_CONFIRM"
    assert merged_items[0]["is_merged"] == 1

    total_unmerged, unmerged_items = repo.search_notes(
        source="bilibili",
        merged=False,
        sort_by="saved_at",
        sort_order="desc",
        limit=10,
        offset=0,
    )
    assert total_unmerged == 1
    assert unmerged_items[0]["note_id"] == "b2"


def test_search_notes_supports_saved_from_and_merged_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "notes.db"
    repo = NoteLibraryRepository(str(db_path))
    repo.save_bilibili_note(
        note_id="merged_note_1",
        title="合并后的宏观复盘",
        video_url="https://www.bilibili.com/video/BV1xx411c7mF",
        summary_markdown="# 合并总结",
        elapsed_ms=1,
        transcript_chars=2,
    )
    repo.save_bilibili_note(
        note_id="b1",
        title="普通笔记",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        summary_markdown="# 普通总结",
        elapsed_ms=1,
        transcript_chars=2,
    )
    repo.upsert_source_index_links(
        platform="bilibili",
        mappings={
            "merged_note_1": {
                "canonical_note_id": "merged_note_1",
                "merge_id": "merge-1",
                "state": "ACTIVE",
            },
            "b1": {
                "canonical_note_id": "b1",
                "merge_id": "",
                "state": "ACTIVE",
            },
        },
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_bilibili_notes",
        note_id="merged_note_1",
        saved_at="2026-03-10 00:00:00",
    )
    _update_saved_at(
        db_path=db_path,
        table="saved_bilibili_notes",
        note_id="b1",
        saved_at="2026-03-01 00:00:00",
    )

    total_merged, merged_items = repo.search_notes(
        saved_from="2026-03-05 00:00:00",
        merged=True,
        limit=10,
        offset=0,
    )
    assert total_merged == 1
    assert merged_items[0]["note_id"] == "merged_note_1"
    assert merged_items[0]["is_merged"] == 1
