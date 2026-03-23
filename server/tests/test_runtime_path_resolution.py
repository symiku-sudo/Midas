from __future__ import annotations

from pathlib import Path

import app.core.config as config_module

from app.core.config import RuntimeConfig, Settings, XiaohongshuConfig, resolve_runtime_path
from app.models.schemas import BilibiliSummaryData, XiaohongshuSummaryItem
from app.services.asset_snapshots import AssetSnapshotService
from app.services.async_jobs import AsyncJobService
from app.services.database_backup import PeriodicDatabaseBackupService
from app.services.note_library import NoteLibraryService


def test_resolve_runtime_path_uses_server_root_for_relative_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config_module, "_project_root", lambda: tmp_path)

    resolved = resolve_runtime_path(".tmp/midas.db")

    assert resolved == (tmp_path / ".tmp/midas.db").resolve()


def test_services_resolve_relative_paths_from_server_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config_module, "_project_root", lambda: tmp_path)
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(db_path=".tmp/midas.db"),
        runtime=RuntimeConfig(temp_dir=".tmp"),
    )
    expected_db_path = (tmp_path / ".tmp/midas.db").resolve()
    expected_jobs_path = (tmp_path / ".tmp/async_jobs.json").resolve()

    backup_service = PeriodicDatabaseBackupService(settings)
    note_service = NoteLibraryService(settings)
    asset_service = AssetSnapshotService(settings)

    async def fake_bilibili_runner(video_url: str) -> BilibiliSummaryData:
        return BilibiliSummaryData(
            video_url=video_url,
            summary_markdown="# ok",
            elapsed_ms=1,
            transcript_chars=1,
        )

    async def fake_xiaohongshu_runner(url: str) -> XiaohongshuSummaryItem:
        return XiaohongshuSummaryItem(
            note_id="xhs-1",
            title="mock",
            source_url=url,
            summary_markdown="# ok",
        )

    async_job_service = AsyncJobService(
        settings,
        bilibili_runner=fake_bilibili_runner,
        xiaohongshu_runner=fake_xiaohongshu_runner,
    )

    assert backup_service.db_path == expected_db_path
    assert note_service._repository._db_path == expected_db_path
    assert asset_service._repository._db_path == expected_db_path
    assert async_job_service._store_path == expected_jobs_path
