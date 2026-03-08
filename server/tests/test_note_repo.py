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
