from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.prune_unsaved_synced_notes import (
    _ensure_tables,
    prune_orphan_synced_note_ids,
)


def _seed_db(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        _ensure_tables(conn)
        conn.executemany(
            """
            INSERT INTO xiaohongshu_synced_notes (note_id, title, source_url)
            VALUES (?, ?, ?)
            """,
            [
                ("n1", "t1", "https://www.xiaohongshu.com/explore/n1"),
                ("n2", "t2", "https://www.xiaohongshu.com/explore/n2"),
                ("n3", "t3", "https://www.xiaohongshu.com/explore/n3"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO saved_xiaohongshu_notes (note_id, title, source_url, summary_markdown)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("n2", "saved-2", "https://www.xiaohongshu.com/explore/n2", "# s2"),
            ],
        )
        conn.commit()


def test_prune_orphan_synced_note_ids_dry_run(tmp_path: Path) -> None:
    db_path = tmp_path / "midas.db"
    _seed_db(db_path)

    candidates, deleted, note_ids = prune_orphan_synced_note_ids(
        db_path,
        dry_run=True,
    )

    assert candidates == 2
    assert deleted == 0
    assert note_ids == ["n1", "n3"]

    with sqlite3.connect(str(db_path)) as conn:
        count = conn.execute(
            "SELECT COUNT(1) FROM xiaohongshu_synced_notes"
        ).fetchone()[0]
    assert count == 3


def test_prune_orphan_synced_note_ids_delete(tmp_path: Path) -> None:
    db_path = tmp_path / "midas.db"
    _seed_db(db_path)

    candidates, deleted, note_ids = prune_orphan_synced_note_ids(
        db_path,
        dry_run=False,
    )

    assert candidates == 2
    assert deleted == 2
    assert note_ids == ["n1", "n3"]

    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT note_id FROM xiaohongshu_synced_notes ORDER BY note_id"
        ).fetchall()
    assert [row[0] for row in rows] == ["n2"]


def test_prune_orphan_synced_note_ids_handles_empty_db(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"

    candidates, deleted, note_ids = prune_orphan_synced_note_ids(
        db_path,
        dry_run=False,
    )

    assert candidates == 0
    assert deleted == 0
    assert note_ids == []
