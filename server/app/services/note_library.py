from __future__ import annotations

import logging
import uuid

from app.core.config import Settings
from app.models.schemas import (
    BilibiliSavedNote,
    BilibiliSavedNotesData,
    XiaohongshuSavedNote,
    XiaohongshuSavedNotesData,
    XiaohongshuSyncedNotesPruneData,
    XiaohongshuSummaryItem,
)
from app.repositories.note_repo import NoteLibraryRepository

logger = logging.getLogger(__name__)


class NoteLibraryService:
    def __init__(
        self,
        settings: Settings,
        repository: NoteLibraryRepository | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository or NoteLibraryRepository(
            settings.xiaohongshu.db_path
        )

    def save_bilibili_note(
        self,
        *,
        video_url: str,
        summary_markdown: str,
        elapsed_ms: int,
        transcript_chars: int,
        title: str = "",
    ) -> BilibiliSavedNote:
        note_id = uuid.uuid4().hex
        normalized_title = self._normalize_bilibili_title(
            title=title,
            summary_markdown=summary_markdown,
            video_url=video_url,
        )
        self._repository.save_bilibili_note(
            note_id=note_id,
            title=normalized_title,
            video_url=video_url,
            summary_markdown=summary_markdown,
            elapsed_ms=elapsed_ms,
            transcript_chars=transcript_chars,
        )
        self._backup_database_after_note_save()
        items = self._repository.list_bilibili_notes()
        for item in items:
            if item["note_id"] == note_id:
                return BilibiliSavedNote(**item)
        # Fallback: should not happen, but keep response deterministic.
        return BilibiliSavedNote(
            note_id=note_id,
            title=normalized_title,
            video_url=video_url,
            summary_markdown=summary_markdown,
            elapsed_ms=elapsed_ms,
            transcript_chars=transcript_chars,
            saved_at="",
        )

    def list_bilibili_notes(self) -> BilibiliSavedNotesData:
        items = [BilibiliSavedNote(**item) for item in self._repository.list_bilibili_notes()]
        return BilibiliSavedNotesData(total=len(items), items=items)

    def delete_bilibili_note(self, note_id: str) -> int:
        return self._repository.delete_bilibili_note(note_id)

    def clear_bilibili_notes(self) -> int:
        return self._repository.clear_bilibili_notes()

    def save_xiaohongshu_notes(self, notes: list[XiaohongshuSummaryItem]) -> int:
        payload = [
            {
                "note_id": item.note_id,
                "title": item.title,
                "source_url": item.source_url,
                "summary_markdown": item.summary_markdown,
            }
            for item in notes
        ]
        saved_count = self._repository.save_xiaohongshu_notes(payload)
        if saved_count > 0:
            self._backup_database_after_note_save()
        return saved_count

    def list_xiaohongshu_notes(self) -> XiaohongshuSavedNotesData:
        items = [
            XiaohongshuSavedNote(**item)
            for item in self._repository.list_xiaohongshu_notes()
        ]
        return XiaohongshuSavedNotesData(total=len(items), items=items)

    def delete_xiaohongshu_note(self, note_id: str) -> int:
        return self._repository.delete_xiaohongshu_note(note_id)

    def clear_xiaohongshu_notes(self) -> int:
        return self._repository.clear_xiaohongshu_notes()

    def prune_unsaved_xiaohongshu_synced_notes(self) -> XiaohongshuSyncedNotesPruneData:
        candidate_count, deleted_count = (
            self._repository.prune_unsaved_xiaohongshu_synced_notes()
        )
        return XiaohongshuSyncedNotesPruneData(
            candidate_count=candidate_count,
            deleted_count=deleted_count,
        )

    def _normalize_bilibili_title(
        self,
        *,
        title: str,
        summary_markdown: str,
        video_url: str,
    ) -> str:
        candidate = title.strip()
        if candidate:
            return candidate[:200]
        for line in summary_markdown.splitlines():
            text = line.strip().lstrip("#").strip()
            if text:
                return text[:200]
        return f"B站总结 {video_url}"[:200]

    def _backup_database_after_note_save(self) -> None:
        try:
            backup_path = self._repository.backup_database()
            logger.info("Note database backup created: %s", backup_path)
        except Exception:
            logger.exception("Failed to backup note database after save.")
