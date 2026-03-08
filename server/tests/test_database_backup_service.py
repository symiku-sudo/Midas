from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.config import RuntimeConfig, Settings, XiaohongshuConfig
from app.repositories.note_repo import NoteLibraryRepository
from app.services.database_backup import PeriodicDatabaseBackupService


def _build_settings(db_path: Path) -> Settings:
    return Settings(
        xiaohongshu=XiaohongshuConfig(db_path=str(db_path)),
        runtime=RuntimeConfig(
            temp_dir=str(db_path.parent),
            backup=RuntimeConfig.BackupConfig(
                enabled=True,
                interval_seconds=1,
                startup_delay_seconds=0,
            ),
        ),
    )


def test_periodic_backup_run_once_skips_when_db_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    service = PeriodicDatabaseBackupService(_build_settings(db_path))

    assert service.run_once() is None
    assert not (tmp_path / "backups").exists()


def test_periodic_backup_run_once_creates_backup(tmp_path: Path) -> None:
    db_path = tmp_path / "midas.db"
    repo = NoteLibraryRepository(str(db_path))
    repo.save_bilibili_note(
        note_id="b1",
        title="测试",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        summary_markdown="# 测试",
        elapsed_ms=1,
        transcript_chars=1,
    )
    service = PeriodicDatabaseBackupService(_build_settings(db_path), repository=repo)

    backup_path = service.run_once()

    assert backup_path is not None
    assert backup_path.exists()
    latest_backup = db_path.parent / "backups" / "midas_latest.db"
    assert latest_backup.exists()


def test_periodic_backup_run_stops_cleanly(tmp_path: Path) -> None:
    db_path = tmp_path / "midas.db"
    repo = NoteLibraryRepository(str(db_path))
    repo.save_bilibili_note(
        note_id="b1",
        title="测试",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        summary_markdown="# 测试",
        elapsed_ms=1,
        transcript_chars=1,
    )
    service = PeriodicDatabaseBackupService(_build_settings(db_path), repository=repo)
    stop_event = asyncio.Event()

    async def _run() -> None:
        task = asyncio.create_task(service.run(stop_event))
        await asyncio.sleep(0.05)
        stop_event.set()
        await task

    asyncio.run(_run())

    backup_dir = db_path.parent / "backups"
    assert backup_dir.exists()
    assert list(backup_dir.glob("midas_*.db"))
