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
