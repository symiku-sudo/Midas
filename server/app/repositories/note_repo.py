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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS note_source_index (
                    platform TEXT NOT NULL,
                    source_note_id TEXT NOT NULL,
                    canonical_note_id TEXT NOT NULL,
                    merge_id TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL DEFAULT 'ACTIVE',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (platform, source_note_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_snapshot_history (
                    id TEXT PRIMARY KEY,
                    saved_at TEXT NOT NULL,
                    total_amount_wan REAL NOT NULL,
                    amounts_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_stats_current (
                    profile_id TEXT PRIMARY KEY,
                    total_amount_wan REAL NOT NULL,
                    amounts_json TEXT NOT NULL DEFAULT '{}',
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

    def upsert_asset_snapshot(
        self,
        *,
        record_id: str,
        saved_at: str,
        total_amount_wan: float,
        amounts: dict[str, float],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO asset_snapshot_history
                (id, saved_at, total_amount_wan, amounts_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    saved_at = excluded.saved_at,
                    total_amount_wan = excluded.total_amount_wan,
                    amounts_json = excluded.amounts_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    record_id,
                    saved_at,
                    total_amount_wan,
                    json.dumps(amounts, ensure_ascii=False, sort_keys=True),
                ),
            )
            conn.commit()

    def list_asset_snapshots(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, saved_at, total_amount_wan, amounts_json
                FROM asset_snapshot_history
                ORDER BY saved_at DESC, updated_at DESC, id DESC
                """
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            try:
                amounts = json.loads(str(payload.get("amounts_json", "{}")))
            except Exception:
                amounts = {}
            payload["amounts"] = amounts if isinstance(amounts, dict) else {}
            payload.pop("amounts_json", None)
            items.append(payload)
        return items

    def delete_asset_snapshot(self, record_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM asset_snapshot_history WHERE id = ?",
                (record_id,),
            )
            conn.commit()
            return int(cursor.rowcount)

    def get_asset_current(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT total_amount_wan, amounts_json
                FROM asset_stats_current
                WHERE profile_id = 'default'
                """
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        try:
            amounts = json.loads(str(payload.get("amounts_json", "{}")))
        except Exception:
            amounts = {}
        return {
            "total_amount_wan": float(payload.get("total_amount_wan", 0.0) or 0.0),
            "amounts": amounts if isinstance(amounts, dict) else {},
        }

    def upsert_asset_current(
        self,
        *,
        total_amount_wan: float,
        amounts: dict[str, float],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO asset_stats_current
                (profile_id, total_amount_wan, amounts_json, updated_at)
                VALUES ('default', ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(profile_id) DO UPDATE SET
                    total_amount_wan = excluded.total_amount_wan,
                    amounts_json = excluded.amounts_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    total_amount_wan,
                    json.dumps(amounts, ensure_ascii=False, sort_keys=True),
                ),
            )
            conn.commit()

    def backup_database(self, *, keep_latest_files: int | None = None) -> Path:
        suffix = self._db_path.suffix or ".db"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = self._backup_dir / f"{self._db_path.stem}_{timestamp}{suffix}"

        with self._connect() as source_conn:
            with sqlite3.connect(str(backup_path)) as backup_conn:
                source_conn.backup(backup_conn)
                backup_conn.commit()

        latest_path = self._backup_dir / f"{self._db_path.stem}_latest{suffix}"
        shutil.copy2(backup_path, latest_path)
        self._prune_timestamp_backups(keep_latest_files=keep_latest_files, suffix=suffix)
        return backup_path

    def _prune_timestamp_backups(
        self,
        *,
        keep_latest_files: int | None,
        suffix: str,
    ) -> None:
        if keep_latest_files is None:
            return
        keep_count = max(int(keep_latest_files), 0)
        backups = sorted(
            [
                path
                for path in self._backup_dir.glob(f"{self._db_path.stem}_*{suffix}")
                if path.name != f"{self._db_path.stem}_latest{suffix}"
            ],
            key=lambda path: (path.stat().st_mtime_ns, path.name),
            reverse=True,
        )
        for path in backups[keep_count:]:
            path.unlink(missing_ok=True)

    def list_bilibili_notes(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT note_id, title, video_url, summary_markdown, elapsed_ms,
                       transcript_chars,
                       strftime('%Y-%m-%d %H:%M:%S', datetime(saved_at, '+8 hours')) AS saved_at
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
                       transcript_chars,
                       strftime('%Y-%m-%d %H:%M:%S', datetime(saved_at, '+8 hours')) AS saved_at
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

    def update_bilibili_note_summary(self, *, note_id: str, summary_markdown: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE saved_bilibili_notes
                SET summary_markdown = ?
                WHERE note_id = ?
                """,
                (summary_markdown, note_id),
            )
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
                SELECT note_id, title, source_url, summary_markdown,
                       strftime('%Y-%m-%d %H:%M:%S', datetime(saved_at, '+8 hours')) AS saved_at
                FROM saved_xiaohongshu_notes
                ORDER BY saved_at DESC, rowid DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def search_notes(
        self,
        *,
        keyword: str = "",
        source: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        normalized_keyword = keyword.strip()
        normalized_source = source.strip().lower()
        pattern = f"%{normalized_keyword.lower()}%"
        conditions_bilibili = []
        params_bilibili: list[Any] = []
        conditions_xhs = []
        params_xhs: list[Any] = []
        if normalized_keyword:
            clause = "LOWER(title || '\n' || summary_markdown) LIKE ?"
            conditions_bilibili.append(clause)
            conditions_xhs.append(clause)
            params_bilibili.append(pattern)
            params_xhs.append(pattern)
        where_bilibili = f"WHERE {' AND '.join(conditions_bilibili)}" if conditions_bilibili else ""
        where_xhs = f"WHERE {' AND '.join(conditions_xhs)}" if conditions_xhs else ""

        bilibili_sql = f"""
            SELECT 'bilibili' AS source, note_id, title, video_url AS source_url, summary_markdown,
                   strftime('%Y-%m-%d %H:%M:%S', datetime(saved_at, '+8 hours')) AS saved_at
            FROM saved_bilibili_notes
            {where_bilibili}
        """
        xhs_sql = f"""
            SELECT 'xiaohongshu' AS source, note_id, title, source_url, summary_markdown,
                   strftime('%Y-%m-%d %H:%M:%S', datetime(saved_at, '+8 hours')) AS saved_at
            FROM saved_xiaohongshu_notes
            {where_xhs}
        """
        if normalized_source == "bilibili":
            union_sql = bilibili_sql
            params = params_bilibili
        elif normalized_source == "xiaohongshu":
            union_sql = xhs_sql
            params = params_xhs
        else:
            union_sql = f"{bilibili_sql} UNION ALL {xhs_sql}"
            params = params_bilibili + params_xhs

        with self._connect() as conn:
            count_row = conn.execute(
                f"SELECT COUNT(*) AS total FROM ({union_sql}) AS unified_notes",
                tuple(params),
            ).fetchone()
            rows = conn.execute(
                f"""
                SELECT source, note_id, title, source_url, summary_markdown, saved_at
                FROM ({union_sql}) AS unified_notes
                ORDER BY saved_at DESC, note_id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params) + (limit, offset),
            ).fetchall()
        total = int(dict(count_row or {}).get("total", 0) or 0)
        return total, [dict(row) for row in rows]

    def get_xiaohongshu_notes_by_ids(self, note_ids: list[str]) -> list[dict[str, Any]]:
        if not note_ids:
            return []
        placeholders = ",".join("?" for _ in note_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT note_id, title, source_url, summary_markdown,
                       strftime('%Y-%m-%d %H:%M:%S', datetime(saved_at, '+8 hours')) AS saved_at
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

    def update_xiaohongshu_note_summary(self, *, note_id: str, summary_markdown: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE saved_xiaohongshu_notes
                SET summary_markdown = ?
                WHERE note_id = ?
                """,
                (summary_markdown, note_id),
            )
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

    def get_latest_merge_history_by_merged_note_id(
        self,
        *,
        source: str,
        merged_note_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT merge_id, source, status, source_note_ids, merged_note_id,
                       field_decisions, fallback_reason, rollback_of, operator,
                       created_at, updated_at
                FROM note_merge_history
                WHERE source = ?
                  AND merged_note_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (source, merged_note_id),
            ).fetchone()
        return dict(row) if row is not None else None

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

    def update_merge_history_field_decisions(
        self,
        *,
        merge_id: str,
        field_decisions: dict[str, Any],
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE note_merge_history
                SET field_decisions = ?, updated_at = CURRENT_TIMESTAMP
                WHERE merge_id = ?
                """,
                (json.dumps(field_decisions or {}, ensure_ascii=False), merge_id),
            )
            conn.commit()
            return int(cursor.rowcount)

    def upsert_source_index_links(
        self,
        *,
        platform: str,
        mappings: dict[str, dict[str, str]],
    ) -> None:
        if not mappings:
            return
        rows: list[tuple[str, str, str, str, str]] = []
        for source_note_id, payload in mappings.items():
            source_value = str(source_note_id).strip()
            if not source_value:
                continue
            canonical = str(payload.get("canonical_note_id", "")).strip()
            if not canonical:
                continue
            merge_id = str(payload.get("merge_id", "")).strip()
            state = str(payload.get("state", "ACTIVE")).strip() or "ACTIVE"
            rows.append((platform, source_value, canonical, merge_id, state))
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO note_source_index (
                    platform, source_note_id, canonical_note_id, merge_id, state
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(platform, source_note_id) DO UPDATE SET
                    canonical_note_id = excluded.canonical_note_id,
                    merge_id = excluded.merge_id,
                    state = excluded.state,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )
            conn.commit()

    def get_source_index_links(
        self,
        *,
        platform: str,
        source_note_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        normalized = [item.strip() for item in source_note_ids if item.strip()]
        if not normalized:
            return {}
        placeholders = ",".join("?" for _ in normalized)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT platform, source_note_id, canonical_note_id, merge_id, state, updated_at
                FROM note_source_index
                WHERE platform = ?
                  AND source_note_id IN ({placeholders})
                """,
                tuple([platform, *normalized]),
            ).fetchall()
        output: dict[str, dict[str, Any]] = {}
        for row in rows:
            data = dict(row)
            output[str(data["source_note_id"])] = data
        return output

    def list_source_note_ids_by_canonical(
        self,
        *,
        platform: str,
        canonical_note_id: str,
    ) -> list[str]:
        canonical = canonical_note_id.strip()
        if not canonical:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source_note_id
                FROM note_source_index
                WHERE platform = ?
                  AND canonical_note_id = ?
                ORDER BY source_note_id ASC
                """,
                (platform, canonical),
            ).fetchall()
        return [str(row["source_note_id"]).strip() for row in rows if str(row["source_note_id"]).strip()]

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
