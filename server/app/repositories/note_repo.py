from __future__ import annotations

import json
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


class NoteLibraryRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._backup_dir = self._db_path.parent / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS xiaohongshu_synced_notes (
                    note_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS note_merge_history (
                    merge_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_note_ids TEXT NOT NULL,
                    merged_note_id TEXT NOT NULL,
                    field_decisions TEXT NOT NULL DEFAULT '{}',
                    fallback_reason TEXT NOT NULL DEFAULT '',
                    rollback_of TEXT NOT NULL DEFAULT '',
                    operator TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    def backup_database(self) -> Path:
        suffix = self._db_path.suffix or ".db"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = self._backup_dir / f"{self._db_path.stem}_{timestamp}{suffix}"

        with self._connect() as source_conn:
            with sqlite3.connect(str(backup_path)) as backup_conn:
                source_conn.backup(backup_conn)
                backup_conn.commit()

        latest_path = self._backup_dir / f"{self._db_path.stem}_latest{suffix}"
        shutil.copy2(backup_path, latest_path)
        return backup_path

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

    def get_bilibili_notes_by_ids(self, note_ids: list[str]) -> list[dict[str, Any]]:
        if not note_ids:
            return []
        placeholders = ",".join("?" for _ in note_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT note_id, title, video_url, summary_markdown, elapsed_ms,
                       transcript_chars, saved_at
                FROM saved_bilibili_notes
                WHERE note_id IN ({placeholders})
                """,
                tuple(note_ids),
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

    def get_xiaohongshu_notes_by_ids(self, note_ids: list[str]) -> list[dict[str, Any]]:
        if not note_ids:
            return []
        placeholders = ",".join("?" for _ in note_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT note_id, title, source_url, summary_markdown, saved_at
                FROM saved_xiaohongshu_notes
                WHERE note_id IN ({placeholders})
                """,
                tuple(note_ids),
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

    def delete_bilibili_notes(self, note_ids: list[str]) -> int:
        if not note_ids:
            return 0
        placeholders = ",".join("?" for _ in note_ids)
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM saved_bilibili_notes WHERE note_id IN ({placeholders})",
                tuple(note_ids),
            )
            conn.commit()
            return int(cursor.rowcount)

    def delete_xiaohongshu_notes(self, note_ids: list[str]) -> int:
        if not note_ids:
            return 0
        placeholders = ",".join("?" for _ in note_ids)
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM saved_xiaohongshu_notes WHERE note_id IN ({placeholders})",
                tuple(note_ids),
            )
            conn.commit()
            return int(cursor.rowcount)

    def save_merge_history(
        self,
        *,
        merge_id: str,
        source: str,
        status: str,
        source_note_ids: list[str],
        merged_note_id: str,
        field_decisions: dict[str, Any] | None = None,
        fallback_reason: str = "",
        rollback_of: str = "",
        operator: str = "system",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO note_merge_history (
                    merge_id, source, status, source_note_ids, merged_note_id,
                    field_decisions, fallback_reason, rollback_of, operator
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    merge_id,
                    source,
                    status,
                    json.dumps(source_note_ids, ensure_ascii=False),
                    merged_note_id,
                    json.dumps(field_decisions or {}, ensure_ascii=False),
                    fallback_reason,
                    rollback_of,
                    operator,
                ),
            )
            conn.commit()

    def get_merge_history(self, merge_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT merge_id, source, status, source_note_ids, merged_note_id,
                       field_decisions, fallback_reason, rollback_of, operator,
                       created_at, updated_at
                FROM note_merge_history
                WHERE merge_id = ?
                """,
                (merge_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_merge_history_by_source(self, source: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT merge_id, source, status, source_note_ids, merged_note_id,
                       field_decisions, fallback_reason, rollback_of, operator,
                       created_at, updated_at
                FROM note_merge_history
                WHERE source = ?
                ORDER BY created_at DESC, rowid DESC
                """,
                (source,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_merge_history_status(
        self,
        *,
        merge_id: str,
        status: str,
        rollback_of: str | None = None,
    ) -> int:
        set_clause = "status = ?, updated_at = CURRENT_TIMESTAMP"
        params: list[Any] = [status]
        if rollback_of is not None:
            set_clause += ", rollback_of = ?"
            params.append(rollback_of)
        params.append(merge_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                UPDATE note_merge_history
                SET {set_clause}
                WHERE merge_id = ?
                """,
                tuple(params),
            )
            conn.commit()
            return int(cursor.rowcount)

    def prune_unsaved_xiaohongshu_synced_notes(self) -> tuple[int, int]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS candidate_count
                FROM xiaohongshu_synced_notes AS synced
                LEFT JOIN saved_xiaohongshu_notes AS saved
                  ON saved.note_id = synced.note_id
                WHERE saved.note_id IS NULL
                """
            ).fetchone()
            candidate_count = int(row["candidate_count"]) if row is not None else 0
            if candidate_count <= 0:
                return 0, 0

            cursor = conn.execute(
                """
                DELETE FROM xiaohongshu_synced_notes
                WHERE note_id IN (
                    SELECT synced.note_id
                    FROM xiaohongshu_synced_notes AS synced
                    LEFT JOIN saved_xiaohongshu_notes AS saved
                      ON saved.note_id = synced.note_id
                    WHERE saved.note_id IS NULL
                )
                """
            )
            conn.commit()
            deleted_count = int(cursor.rowcount)
            return candidate_count, deleted_count
