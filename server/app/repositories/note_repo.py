from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class NoteLibraryRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_bilibili_notes (
                    note_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    video_url TEXT NOT NULL,
                    summary_markdown TEXT NOT NULL,
                    elapsed_ms INTEGER NOT NULL,
                    transcript_chars INTEGER NOT NULL,
                    saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_xiaohongshu_notes (
                    note_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    summary_markdown TEXT NOT NULL,
                    saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def save_bilibili_note(
        self,
        *,
        note_id: str,
        title: str,
        video_url: str,
        summary_markdown: str,
        elapsed_ms: int,
        transcript_chars: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO saved_bilibili_notes
                (note_id, title, video_url, summary_markdown, elapsed_ms, transcript_chars)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    title,
                    video_url,
                    summary_markdown,
                    elapsed_ms,
                    transcript_chars,
                ),
            )
            conn.commit()

    def list_bilibili_notes(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT note_id, title, video_url, summary_markdown, elapsed_ms,
                       transcript_chars, saved_at
                FROM saved_bilibili_notes
                ORDER BY saved_at DESC, rowid DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_bilibili_note(self, note_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM saved_bilibili_notes WHERE note_id = ?",
                (note_id,),
            )
            conn.commit()
            return int(cursor.rowcount)

    def clear_bilibili_notes(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM saved_bilibili_notes")
            conn.commit()
            return int(cursor.rowcount)

    def save_xiaohongshu_notes(self, notes: list[dict[str, str]]) -> int:
        if not notes:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO saved_xiaohongshu_notes
                (note_id, title, source_url, summary_markdown)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        item["note_id"],
                        item["title"],
                        item["source_url"],
                        item["summary_markdown"],
                    )
                    for item in notes
                ],
            )
            conn.commit()
        return len(notes)

    def list_xiaohongshu_notes(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT note_id, title, source_url, summary_markdown, saved_at
                FROM saved_xiaohongshu_notes
                ORDER BY saved_at DESC, rowid DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_xiaohongshu_note(self, note_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM saved_xiaohongshu_notes WHERE note_id = ?",
                (note_id,),
            )
            conn.commit()
            return int(cursor.rowcount)

    def clear_xiaohongshu_notes(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM saved_xiaohongshu_notes")
            conn.commit()
            return int(cursor.rowcount)
