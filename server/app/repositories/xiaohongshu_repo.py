from __future__ import annotations

import sqlite3
from pathlib import Path


class XiaohongshuSyncRepository:
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
                CREATE TABLE IF NOT EXISTS xiaohongshu_runtime_state (
                    state_key TEXT PRIMARY KEY,
                    state_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def is_synced(self, note_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM xiaohongshu_synced_notes WHERE note_id = ? LIMIT 1",
                (note_id,),
            ).fetchone()
        return row is not None

    def mark_synced(self, note_id: str, title: str, source_url: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO xiaohongshu_synced_notes (note_id, title, source_url)
                VALUES (?, ?, ?)
                """,
                (note_id, title, source_url),
            )
            conn.commit()

    def get_state(self, state_key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state_value FROM xiaohongshu_runtime_state
                WHERE state_key = ?
                LIMIT 1
                """,
                (state_key,),
            ).fetchone()
        if row is None:
            return None
        return str(row["state_value"])

    def set_state(self, state_key: str, state_value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO xiaohongshu_runtime_state (state_key, state_value)
                VALUES (?, ?)
                """,
                (state_key, state_value),
            )
            conn.commit()
