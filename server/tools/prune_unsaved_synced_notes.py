from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.config import load_settings


def _resolve_db_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (SERVER_ROOT / path).resolve()


def _ensure_tables(conn: sqlite3.Connection) -> None:
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
        CREATE TABLE IF NOT EXISTS saved_xiaohongshu_notes (
            note_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source_url TEXT NOT NULL,
            summary_markdown TEXT NOT NULL,
            saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _list_orphan_note_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT synced.note_id
        FROM xiaohongshu_synced_notes AS synced
        LEFT JOIN saved_xiaohongshu_notes AS saved
          ON saved.note_id = synced.note_id
        WHERE saved.note_id IS NULL
        ORDER BY synced.synced_at ASC, synced.note_id ASC
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def prune_orphan_synced_note_ids(
    db_path: Path,
    *,
    dry_run: bool,
) -> tuple[int, int, list[str]]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        _ensure_tables(conn)
        orphan_note_ids = _list_orphan_note_ids(conn)
        candidate_count = len(orphan_note_ids)
        if dry_run or candidate_count == 0:
            return candidate_count, 0, orphan_note_ids

        conn.executemany(
            "DELETE FROM xiaohongshu_synced_notes WHERE note_id = ?",
            [(note_id,) for note_id in orphan_note_ids],
        )
        conn.commit()
        return candidate_count, candidate_count, orphan_note_ids


def main() -> int:
    default_db_path = _resolve_db_path(load_settings().xiaohongshu.db_path)
    parser = argparse.ArgumentParser(
        description=(
            "删除去重表中“已记录但未保存到笔记库”的小红书 note_id。"
        )
    )
    parser.add_argument(
        "--db-path",
        default=str(default_db_path),
        help="SQLite 数据库路径（默认读取 config.yaml 的 xiaohongshu.db_path）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览待删除 note_id，不执行删除。",
    )
    parser.add_argument(
        "--show-ids",
        action="store_true",
        help="打印待删除 note_id 列表。",
    )
    args = parser.parse_args()

    db_path = _resolve_db_path(args.db_path)
    candidate_count, deleted_count, orphan_note_ids = prune_orphan_synced_note_ids(
        db_path,
        dry_run=args.dry_run,
    )

    print(f"[prune_unsaved_synced_notes] db={db_path}")
    print(f"[prune_unsaved_synced_notes] candidates={candidate_count}")
    if args.dry_run:
        print("[prune_unsaved_synced_notes] mode=dry-run (no deletion)")
    else:
        print(f"[prune_unsaved_synced_notes] deleted={deleted_count}")

    if args.show_ids and orphan_note_ids:
        print("[prune_unsaved_synced_notes] orphan note_id list:")
        for note_id in orphan_note_ids:
            print(f"  - {note_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
