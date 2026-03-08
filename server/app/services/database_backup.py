from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.core.config import Settings
from app.repositories.note_repo import NoteLibraryRepository

logger = logging.getLogger(__name__)


class PeriodicDatabaseBackupService:
    def __init__(
        self,
        settings: Settings,
        repository: NoteLibraryRepository | None = None,
    ) -> None:
        self._settings = settings
        self._db_path = Path(settings.xiaohongshu.db_path).expanduser().resolve()
        self._repository = repository
        self._backup_dir = self._db_path.parent / "backups"

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def backup_dir(self) -> Path:
        return self._backup_dir

    def run_once(self) -> Path | None:
        if not self._db_path.exists():
            logger.info("Periodic database backup skipped: db not found at %s", self._db_path)
            return None
        repository = self._repository or NoteLibraryRepository(str(self._db_path))
        self._repository = repository
        backup_path = repository.backup_database(
            keep_latest_files=self._settings.runtime.backup.keep_latest_files
        )
        logger.info("Periodic database backup created: %s", backup_path)
        return backup_path

    async def run(self, stop_event: asyncio.Event) -> None:
        backup_cfg = self._settings.runtime.backup
        if not backup_cfg.enabled:
            logger.info("Periodic database backup disabled.")
            return

        interval_seconds = max(int(backup_cfg.interval_seconds), 0)
        startup_delay_seconds = max(int(backup_cfg.startup_delay_seconds), 0)
        if interval_seconds <= 0:
            logger.info("Periodic database backup disabled: interval_seconds=%s", interval_seconds)
            return

        logger.info(
            "Periodic database backup enabled: db=%s backup_dir=%s interval=%ss startup_delay=%ss",
            self._db_path,
            self._backup_dir,
            interval_seconds,
            startup_delay_seconds,
        )
        if startup_delay_seconds > 0 and not await self._sleep_or_stop(
            stop_event,
            startup_delay_seconds,
        ):
            return

        while not stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Periodic database backup failed.")
            if not await self._sleep_or_stop(stop_event, interval_seconds):
                return

    async def _sleep_or_stop(
        self,
        stop_event: asyncio.Event,
        seconds: int,
    ) -> bool:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(seconds, 0))
            return False
        except asyncio.TimeoutError:
            return True
