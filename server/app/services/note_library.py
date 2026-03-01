from __future__ import annotations

import json
import logging
import re
import uuid
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.schemas import (
    BilibiliSavedNote,
    BilibiliSavedNotesData,
    NotesMergeCandidateItem,
    NotesMergeCandidateNote,
    NotesMergeCommitData,
    NotesMergeFinalizeData,
    NotesMergePreviewData,
    NotesMergeRollbackData,
    NotesMergeSuggestData,
    XiaohongshuSavedNote,
    XiaohongshuSavedNotesData,
    XiaohongshuSyncedNotesPruneData,
    XiaohongshuSummaryItem,
)
from app.repositories.note_repo import NoteLibraryRepository
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

_MERGE_SOURCE_BILIBILI = "bilibili"
_MERGE_SOURCE_XIAOHONGSHU = "xiaohongshu"
_SUPPORTED_MERGE_SOURCES = {_MERGE_SOURCE_BILIBILI, _MERGE_SOURCE_XIAOHONGSHU}
_MERGE_STATUS_PENDING_CONFIRM = "MERGED_PENDING_CONFIRM"
_MERGE_STATUS_ROLLED_BACK = "ROLLED_BACK"
_MERGE_STATUS_FINALIZED_DESTRUCTIVE = "FINALIZED_DESTRUCTIVE"
_SOURCE_INDEX_STATE_ACTIVE = "ACTIVE"
_TITLE_TOKEN_MIN_ANCHOR = 0.06
_TITLE_SURFACE_MIN_ANCHOR = 0.55
_ASCII_TOKEN_PATTERN = re.compile(r"[0-9a-z]+")
_CJK_BLOCK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "you",
    "are",
    "was",
    "were",
    "can",
    "will",
}
_CJK_STOPWORDS = {"的", "了", "和", "是", "在", "与", "及", "并", "对", "将"}


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
        self._llm = LLMService(settings)
        self._semantic_model: Any | None = None
        self._semantic_model_failed = False
        self._semantic_embeddings_cache: dict[str, list[float]] = {}

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
        self._repository.upsert_source_index_links(
            platform=_MERGE_SOURCE_BILIBILI,
            mappings={
                note_id: {
                    "canonical_note_id": note_id,
                    "merge_id": "",
                    "state": _SOURCE_INDEX_STATE_ACTIVE,
                }
            },
        )
        self._backup_database_after_note_save()
        items = self._repository.list_bilibili_notes()
        for item in items:
            if item["note_id"] == note_id:
                return BilibiliSavedNote(**item)
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
            mappings = {
                item["note_id"]: {
                    "canonical_note_id": item["note_id"],
                    "merge_id": "",
                    "state": _SOURCE_INDEX_STATE_ACTIVE,
                }
                for item in payload
            }
            self._repository.upsert_source_index_links(
                platform=_MERGE_SOURCE_XIAOHONGSHU,
                mappings=mappings,
            )
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

    def suggest_merge_candidates(
        self,
        *,
        source: str = "",
        limit: int = 20,
        min_score: float = 0.35,
    ) -> NotesMergeSuggestData:
        source_value = source.strip().lower()
        if source_value and source_value not in _SUPPORTED_MERGE_SOURCES:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"不支持的 merge source: {source}",
                status_code=400,
            )
        sources = [source_value] if source_value else sorted(_SUPPORTED_MERGE_SOURCES)

        candidates: list[NotesMergeCandidateItem] = []
        for one_source in sources:
            notes = self._list_notes_for_merge_source(one_source)
            if len(notes) < 2:
                continue
            for first, second in combinations(notes, 2):
                score_data = self._score_note_pair(first, second)
                if score_data["score"] < min_score:
                    continue
                candidate = NotesMergeCandidateItem(
                    source=one_source,
                    note_ids=[first["note_id"], second["note_id"]],
                    score=round(float(score_data["score"]), 4),
                    reason_codes=score_data["reason_codes"],
                    notes=[
                        NotesMergeCandidateNote(
                            note_id=first["note_id"],
                            title=first["title"],
                            saved_at=first.get("saved_at", ""),
                        ),
                        NotesMergeCandidateNote(
                            note_id=second["note_id"],
                            title=second["title"],
                            saved_at=second.get("saved_at", ""),
                        ),
                    ],
                )
                candidates.append(candidate)

        candidates.sort(key=lambda item: item.score, reverse=True)
        if limit > 0:
            candidates = candidates[:limit]
        return NotesMergeSuggestData(total=len(candidates), items=candidates)

    async def preview_merge(
        self,
        *,
        source: str,
        note_ids: list[str],
    ) -> NotesMergePreviewData:
        normalized_source = self._validate_merge_source(source)
        normalized_note_ids = self._normalize_note_ids(note_ids)
        notes = self._load_source_notes_by_ids(
            source=normalized_source,
            note_ids=normalized_note_ids,
        )
        merged_title, merged_summary, conflict_markers = await self._build_merged_content(
            source=normalized_source,
            notes=notes,
        )
        source_refs = [str(item.get("source_ref", "")).strip() for item in notes]
        return NotesMergePreviewData(
            source=normalized_source,
            note_ids=normalized_note_ids,
            merged_title=merged_title,
            merged_summary_markdown=merged_summary,
            source_refs=[ref for ref in source_refs if ref],
            conflict_markers=conflict_markers,
        )

    async def commit_merge(
        self,
        *,
        source: str,
        note_ids: list[str],
        merged_title: str = "",
        merged_summary_markdown: str = "",
    ) -> NotesMergeCommitData:
        preview = await self.preview_merge(source=source, note_ids=note_ids)
        notes = self._load_source_notes_by_ids(
            source=preview.source,
            note_ids=preview.note_ids,
        )
        final_title = merged_title.strip() or preview.merged_title
        final_summary = merged_summary_markdown.strip() or preview.merged_summary_markdown
        merge_id = f"merge_{uuid.uuid4().hex}"
        merged_note_id = f"merged_note_{uuid.uuid4().hex}"
        lineage_source_ids = self._expand_source_note_ids(
            source=preview.source,
            note_ids=preview.note_ids,
        )
        source_links_snapshot = self._repository.get_source_index_links(
            platform=preview.source,
            source_note_ids=lineage_source_ids,
        )
        normalized_snapshot: dict[str, str] = {}
        for source_note_id in lineage_source_ids:
            current = source_links_snapshot.get(source_note_id, {})
            canonical = str(current.get("canonical_note_id", "")).strip() or source_note_id
            normalized_snapshot[source_note_id] = canonical

        if preview.source == _MERGE_SOURCE_BILIBILI:
            primary = notes[0]
            elapsed_ms = int(primary.get("elapsed_ms", 0))
            transcript_chars = int(primary.get("transcript_chars", 0))
            for item in notes[1:]:
                elapsed_ms += int(item.get("elapsed_ms", 0))
                transcript_chars += int(item.get("transcript_chars", 0))
            self._repository.save_bilibili_note(
                note_id=merged_note_id,
                title=final_title[:200],
                video_url=str(primary.get("video_url", "")),
                summary_markdown=final_summary,
                elapsed_ms=elapsed_ms,
                transcript_chars=transcript_chars,
            )
        else:
            primary = notes[0]
            self._repository.save_xiaohongshu_notes(
                [
                    {
                        "note_id": merged_note_id,
                        "title": final_title[:200],
                        "source_url": str(primary.get("source_url", "")),
                        "summary_markdown": final_summary,
                    }
                ]
            )
        pending_mappings = {
            source_note_id: {
                "canonical_note_id": merged_note_id,
                "merge_id": merge_id,
                "state": _MERGE_STATUS_PENDING_CONFIRM,
            }
            for source_note_id in lineage_source_ids
        }
        pending_mappings[merged_note_id] = {
            "canonical_note_id": merged_note_id,
            "merge_id": merge_id,
            "state": _MERGE_STATUS_PENDING_CONFIRM,
        }
        self._repository.upsert_source_index_links(
            platform=preview.source,
            mappings=pending_mappings,
        )

        field_decisions = {
            "merged_title": final_title,
            "merged_summary_markdown": final_summary,
            "source_refs": preview.source_refs,
            "conflict_markers": preview.conflict_markers,
            "lineage_source_ids": lineage_source_ids,
            "source_link_snapshot": normalized_snapshot,
        }
        self._repository.save_merge_history(
            merge_id=merge_id,
            source=preview.source,
            status=_MERGE_STATUS_PENDING_CONFIRM,
            source_note_ids=preview.note_ids,
            merged_note_id=merged_note_id,
            field_decisions=field_decisions,
            operator="user",
        )
        self._backup_database_after_note_save()
        return NotesMergeCommitData(
            merge_id=merge_id,
            status=_MERGE_STATUS_PENDING_CONFIRM,
            source=preview.source,
            merged_note_id=merged_note_id,
            source_note_ids=preview.note_ids,
            can_rollback=True,
            can_finalize=True,
        )

    def rollback_merge(self, *, merge_id: str) -> NotesMergeRollbackData:
        history = self._must_get_merge_history(merge_id)
        if history["status"] != _MERGE_STATUS_PENDING_CONFIRM:
            raise AppError(
                code=ErrorCode.MERGE_NOT_ALLOWED,
                message="当前合并状态不允许回退。",
                status_code=409,
            )
        if not self._is_latest_merge_for_sources(history):
            raise AppError(
                code=ErrorCode.MERGE_NOT_ALLOWED,
                message="仅允许回退最近一次合并结果。",
                status_code=409,
            )

        source = str(history["source"])
        merged_note_id = str(history["merged_note_id"])
        source_note_ids = self._decode_json_note_ids(history["source_note_ids"])
        lineage_source_ids = self._read_lineage_source_ids(history)
        source_link_snapshot = self._read_source_link_snapshot(
            history=history,
            lineage_source_ids=lineage_source_ids,
        )
        if source == _MERGE_SOURCE_BILIBILI:
            deleted_merged_count = self._repository.delete_bilibili_note(merged_note_id)
        else:
            deleted_merged_count = self._repository.delete_xiaohongshu_note(merged_note_id)
        rollback_mappings = {
            source_note_id: {
                "canonical_note_id": source_link_snapshot.get(source_note_id, source_note_id),
                "merge_id": "",
                "state": _SOURCE_INDEX_STATE_ACTIVE,
            }
            for source_note_id in lineage_source_ids
        }
        rollback_mappings[merged_note_id] = {
            "canonical_note_id": merged_note_id,
            "merge_id": "",
            "state": _MERGE_STATUS_ROLLED_BACK,
        }
        self._repository.upsert_source_index_links(
            platform=source,
            mappings=rollback_mappings,
        )

        self._repository.update_merge_history_status(
            merge_id=merge_id,
            status=_MERGE_STATUS_ROLLED_BACK,
        )
        self._repository.save_merge_history(
            merge_id=f"rollback_{uuid.uuid4().hex}",
            source=source,
            status=_MERGE_STATUS_ROLLED_BACK,
            source_note_ids=source_note_ids,
            merged_note_id=merged_note_id,
            field_decisions={},
            rollback_of=merge_id,
            operator="user",
        )
        self._backup_database_after_note_save()
        return NotesMergeRollbackData(
            merge_id=merge_id,
            status=_MERGE_STATUS_ROLLED_BACK,
            deleted_merged_count=deleted_merged_count,
            restored_source_count=len(source_note_ids),
        )

    def finalize_merge(
        self,
        *,
        merge_id: str,
        confirm_destructive: bool,
    ) -> NotesMergeFinalizeData:
        if not confirm_destructive:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="缺少破坏性确认参数 confirm_destructive=true。",
                status_code=400,
            )
        history = self._must_get_merge_history(merge_id)
        if history["status"] != _MERGE_STATUS_PENDING_CONFIRM:
            raise AppError(
                code=ErrorCode.MERGE_NOT_ALLOWED,
                message="当前合并状态不允许确认。",
                status_code=409,
            )
        if not self._is_latest_merge_for_sources(history):
            raise AppError(
                code=ErrorCode.MERGE_NOT_ALLOWED,
                message="仅允许确认最近一次合并结果。",
                status_code=409,
            )

        source = str(history["source"])
        source_note_ids = self._decode_json_note_ids(history["source_note_ids"])
        merged_note_id = str(history["merged_note_id"])
        lineage_source_ids = self._read_lineage_source_ids(history)
        deleted_source_count = 0
        if source == _MERGE_SOURCE_BILIBILI:
            deleted_source_count = self._repository.delete_bilibili_notes(source_note_ids)
        else:
            deleted_source_count = self._repository.delete_xiaohongshu_notes(source_note_ids)
        finalized_mappings = {
            source_note_id: {
                "canonical_note_id": merged_note_id,
                "merge_id": merge_id,
                "state": _MERGE_STATUS_FINALIZED_DESTRUCTIVE,
            }
            for source_note_id in lineage_source_ids
        }
        finalized_mappings[merged_note_id] = {
            "canonical_note_id": merged_note_id,
            "merge_id": "",
            "state": _SOURCE_INDEX_STATE_ACTIVE,
        }
        self._repository.upsert_source_index_links(
            platform=source,
            mappings=finalized_mappings,
        )

        self._repository.update_merge_history_status(
            merge_id=merge_id,
            status=_MERGE_STATUS_FINALIZED_DESTRUCTIVE,
        )
        self._backup_database_after_note_save()
        return NotesMergeFinalizeData(
            merge_id=merge_id,
            status=_MERGE_STATUS_FINALIZED_DESTRUCTIVE,
            deleted_source_count=deleted_source_count,
            kept_merged_note_id=merged_note_id,
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

    def _validate_merge_source(self, source: str) -> str:
        normalized = source.strip().lower()
        if normalized not in _SUPPORTED_MERGE_SOURCES:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"不支持的 merge source: {source}",
                status_code=400,
            )
        return normalized

    def _normalize_note_ids(self, note_ids: list[str]) -> list[str]:
        normalized = [item.strip() for item in note_ids if item.strip()]
        if len(normalized) != 2 or len(set(normalized)) != 2:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="MVP 仅支持 2 条笔记合并，且 note_id 不能重复。",
                status_code=400,
            )
        return normalized

    def _list_notes_for_merge_source(self, source: str) -> list[dict[str, Any]]:
        if source == _MERGE_SOURCE_BILIBILI:
            rows = self._repository.list_bilibili_notes()
            source_ref_key = "video_url"
        else:
            rows = self._repository.list_xiaohongshu_notes()
            source_ref_key = "source_url"

        note_ids = [
            str(item.get("note_id", "")).strip()
            for item in rows
            if str(item.get("note_id", "")).strip()
        ]
        source_links = self._repository.get_source_index_links(
            platform=source,
            source_note_ids=note_ids,
        )

        filtered: list[dict[str, Any]] = []
        for item in rows:
            note_id = str(item.get("note_id", "")).strip()
            if not note_id:
                continue
            link = source_links.get(note_id)
            # Hide notes already participating in an unfinished/finished merge state.
            if link is not None and str(link.get("state", "")).strip() != _SOURCE_INDEX_STATE_ACTIVE:
                continue
            filtered.append(
                {
                    **item,
                    "source_ref": item.get(source_ref_key, ""),
                }
            )
        return filtered

    def _load_source_notes_by_ids(
        self,
        *,
        source: str,
        note_ids: list[str],
    ) -> list[dict[str, Any]]:
        if source == _MERGE_SOURCE_BILIBILI:
            rows = self._repository.get_bilibili_notes_by_ids(note_ids)
            by_id = {item["note_id"]: {**item, "source_ref": item.get("video_url", "")} for item in rows}
        else:
            rows = self._repository.get_xiaohongshu_notes_by_ids(note_ids)
            by_id = {item["note_id"]: {**item, "source_ref": item.get("source_url", "")} for item in rows}

        missing_ids = [item for item in note_ids if item not in by_id]
        if missing_ids:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"存在无效 note_id: {','.join(missing_ids)}",
                status_code=400,
            )
        return [by_id[item] for item in note_ids]

    def _score_note_pair(
        self,
        first: dict[str, Any],
        second: dict[str, Any],
    ) -> dict[str, Any]:
        first_title = str(first.get("title", ""))
        second_title = str(second.get("title", ""))
        first_summary = str(first.get("summary_markdown", ""))
        second_summary = str(second.get("summary_markdown", ""))

        keyword_overlap = self._token_jaccard(
            f"{first_title}\n{first_summary}",
            f"{second_title}\n{second_summary}",
        )
        title_token_similarity = self._token_jaccard(first_title, second_title)
        title_surface_similarity = SequenceMatcher(
            None,
            first_title.lower(),
            second_title.lower(),
        ).ratio()
        has_title_anchor = (
            title_token_similarity >= _TITLE_TOKEN_MIN_ANCHOR
            or title_surface_similarity >= _TITLE_SURFACE_MIN_ANCHOR
        )
        summary_similarity, _ = self._summary_similarity_with_mode(
            first_summary=first_summary,
            second_summary=second_summary,
        )
        if has_title_anchor:
            score = (
                0.35 * title_token_similarity
                + 0.50 * summary_similarity
                + 0.15 * keyword_overlap
            )
        else:
            score = 0.0

        reason_codes: list[str] = []
        if keyword_overlap >= 0.12:
            reason_codes.append("KEYWORD_OVERLAP")
        if title_token_similarity >= 0.08 or title_surface_similarity >= _TITLE_SURFACE_MIN_ANCHOR:
            reason_codes.append("TITLE_SIMILAR")
        if summary_similarity >= 0.62:
            reason_codes.append("SUMMARY_SIMILAR")
        if not reason_codes:
            reason_codes.append("LOW_CONFIDENCE")
        return {"score": score, "reason_codes": reason_codes}

    async def _build_merged_content(
        self,
        *,
        source: str,
        notes: list[dict[str, Any]],
    ) -> tuple[str, str, list[str]]:
        first = notes[0]
        second = notes[1]
        first_title = str(first.get("title", "")).strip()
        second_title = str(second.get("title", "")).strip()
        first_summary = str(first.get("summary_markdown", "")).strip()
        second_summary = str(second.get("summary_markdown", "")).strip()
        first_ref = str(first.get("source_ref", "")).strip()
        second_ref = str(second.get("source_ref", "")).strip()

        title_similarity = max(
            self._token_jaccard(first_title, second_title),
            SequenceMatcher(None, first_title.lower(), second_title.lower()).ratio(),
        )
        summary_similarity = SequenceMatcher(None, first_summary, second_summary).ratio()

        conflict_markers: list[str] = []
        if title_similarity < 0.45:
            conflict_markers.append("TITLE_CONFLICT")
        if summary_similarity < 0.35:
            conflict_markers.append("CONTENT_CONFLICT")

        merged_title = first_title if len(first_title) >= len(second_title) else second_title
        if not merged_title:
            merged_title = "合并笔记"
        try:
            merged_summary = await self._llm.merge_notes(
                source=source,
                first_title=first_title,
                first_content=first_summary,
                first_ref=first_ref,
                second_title=second_title,
                second_content=second_summary,
                second_ref=second_ref,
            )
        except AppError as exc:
            if exc.code not in {ErrorCode.UPSTREAM_ERROR, ErrorCode.RATE_LIMITED}:
                raise
            logger.warning(
                "Merge LLM failed, fallback to deterministic structured merge: code=%s message=%s",
                exc.code.value,
                exc.message,
            )
            merged_summary = self._build_structured_fallback_merge(
                merged_title=merged_title,
                first_summary=first_summary,
                second_summary=second_summary,
                first_ref=first_ref,
                second_ref=second_ref,
                conflict_markers=conflict_markers,
            )
        merged_summary = self._enforce_merge_format_contract(
            markdown=merged_summary,
            fallback_title=merged_title[:22] or "合并笔记",
            conflict_markers=conflict_markers,
        )

        merged_title = self._extract_h1_title(merged_summary, fallback=merged_title)
        return merged_title[:200], merged_summary, conflict_markers

    def _build_structured_fallback_merge(
        self,
        *,
        merged_title: str,
        first_summary: str,
        second_summary: str,
        first_ref: str,
        second_ref: str,
        conflict_markers: list[str],
    ) -> str:
        base = first_summary.strip() or second_summary.strip()
        if not base:
            base = f"# {merged_title[:22]}\n\n- 信息不足。"
        if not base.startswith("# "):
            base = f"# {merged_title[:22]}\n\n{base}".strip()

        fallback_conflicts = [marker for marker in conflict_markers if marker]
        refs = [item for item in [first_ref, second_ref] if item]
        for index, ref in enumerate(refs, start=1):
            fallback_conflicts.append(f"来源{index}: {ref}")
        return self._enforce_merge_format_contract(
            markdown=base,
            fallback_title=merged_title[:22] or "合并笔记",
            conflict_markers=fallback_conflicts,
        )

    def _extract_h1_title(self, markdown: str, *, fallback: str) -> str:
        for raw in markdown.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("# "):
                title = line[2:].strip()
                if title:
                    return title
                break
        return fallback

    def _token_jaccard(self, left: str, right: str) -> float:
        left_tokens = set(self._tokenize(left))
        right_tokens = set(self._tokenize(right))
        if not left_tokens or not right_tokens:
            return 0.0
        intersection = len(left_tokens & right_tokens)
        union = len(left_tokens | right_tokens)
        if union <= 0:
            return 0.0
        return intersection / union

    def _tokenize(self, text: str) -> list[str]:
        normalized = text.lower().strip()
        if not normalized:
            return []

        tokens: list[str] = []

        for token in _ASCII_TOKEN_PATTERN.findall(normalized):
            if len(token) <= 1:
                continue
            if token in _ASCII_STOPWORDS:
                continue
            tokens.append(token)

        for block in _CJK_BLOCK_PATTERN.findall(normalized):
            if not block:
                continue
            if len(block) == 1:
                if block not in _CJK_STOPWORDS:
                    tokens.append(block)
                continue
            # Use CJK bi-grams to improve recall on Chinese text similarity.
            for index in range(len(block) - 1):
                grams = block[index : index + 2]
                if any(ch in _CJK_STOPWORDS for ch in grams):
                    continue
                tokens.append(grams)

        return tokens

    def _summary_similarity(self, first_summary: str, second_summary: str) -> float:
        score, _ = self._summary_similarity_with_mode(
            first_summary=first_summary,
            second_summary=second_summary,
        )
        return score

    def _summary_similarity_with_mode(
        self,
        *,
        first_summary: str,
        second_summary: str,
    ) -> tuple[float, bool]:
        semantic_similarity = self._semantic_summary_similarity(
            left=first_summary,
            right=second_summary,
        )
        if semantic_similarity is not None:
            return semantic_similarity, True
        lexical_similarity = SequenceMatcher(None, first_summary, second_summary).ratio()
        # Keep fallback lexical scores on a comparable scale with embedding similarity.
        calibrated = max(0.0, min(1.0, float(lexical_similarity) * 2.0))
        return calibrated, False

    def _semantic_summary_similarity(self, *, left: str, right: str) -> float | None:
        settings = self._settings.notes_merge
        if not settings.semantic_similarity_enabled:
            return None
        left_text = left.strip()[: settings.semantic_max_chars]
        right_text = right.strip()[: settings.semantic_max_chars]
        if not left_text or not right_text:
            return 0.0
        model = self._load_semantic_model()
        if model is None:
            return None
        left_embedding = self._encode_semantic_text(left_text)
        right_embedding = self._encode_semantic_text(right_text)
        if left_embedding is None or right_embedding is None:
            return None
        if len(left_embedding) != len(right_embedding):
            return None
        dot = sum(a * b for a, b in zip(left_embedding, right_embedding))
        return max(0.0, min(1.0, float(dot)))

    def _load_semantic_model(self) -> Any | None:
        if self._semantic_model is not None:
            return self._semantic_model
        if self._semantic_model_failed:
            return None
        settings = self._settings.notes_merge
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as exc:
            logger.warning(
                "Local semantic similarity disabled: sentence-transformers unavailable: %s",
                exc,
            )
            self._semantic_model_failed = True
            return None
        try:
            self._semantic_model = SentenceTransformer(
                settings.semantic_model_name,
                device=settings.semantic_device,
            )
            logger.info(
                "Local semantic model loaded for notes merge: model=%s device=%s",
                settings.semantic_model_name,
                settings.semantic_device,
            )
        except Exception as exc:
            logger.warning(
                "Failed to load local semantic model (%s), fallback to lexical summary similarity: %s",
                settings.semantic_model_name,
                exc,
            )
            self._semantic_model_failed = True
            return None
        return self._semantic_model

    def _encode_semantic_text(self, text: str) -> list[float] | None:
        cached = self._semantic_embeddings_cache.get(text)
        if cached is not None:
            return cached
        model = self._load_semantic_model()
        if model is None:
            return None
        settings = self._settings.notes_merge
        try:
            raw_vector = model.encode(text, normalize_embeddings=True)
        except Exception as exc:
            logger.warning(
                "Local semantic encoding failed, fallback to lexical summary similarity: %s",
                exc,
            )
            self._semantic_model_failed = True
            self._semantic_model = None
            return None
        if hasattr(raw_vector, "tolist"):
            raw_vector = raw_vector.tolist()
        if not isinstance(raw_vector, list):
            return None
        vector = [float(item) for item in raw_vector]
        cache_size = max(64, int(settings.semantic_cache_size))
        if len(self._semantic_embeddings_cache) >= cache_size:
            oldest_key = next(iter(self._semantic_embeddings_cache))
            self._semantic_embeddings_cache.pop(oldest_key, None)
        self._semantic_embeddings_cache[text] = vector
        return vector

    def _must_get_merge_history(self, merge_id: str) -> dict[str, Any]:
        history = self._repository.get_merge_history(merge_id)
        if history is None:
            raise AppError(
                code=ErrorCode.MERGE_NOT_FOUND,
                message=f"未找到 merge_id={merge_id} 的历史记录。",
                status_code=404,
            )
        return history

    def _is_latest_merge_for_sources(self, history: dict[str, Any]) -> bool:
        source = str(history["source"])
        target_merge_id = str(history["merge_id"])
        target_ids = set(self._decode_json_note_ids(history["source_note_ids"]))
        rows = self._repository.list_merge_history_by_source(source)
        for row in rows:
            merge_id = str(row["merge_id"])
            if merge_id == target_merge_id:
                return True
            row_ids = set(self._decode_json_note_ids(row["source_note_ids"]))
            if target_ids & row_ids:
                return False
        return True

    def _decode_json_note_ids(self, raw: Any) -> list[str]:
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        if not isinstance(raw, str):
            return []
        if not raw.strip():
            return []
        try:
            parsed = json.loads(raw)
        except ValueError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item).strip() for item in parsed if str(item).strip()]

    def _decode_field_decisions(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return {}
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    def _expand_source_note_ids(self, *, source: str, note_ids: list[str]) -> list[str]:
        expanded: list[str] = []
        seen: set[str] = set()
        for note_id in note_ids:
            canonical = note_id.strip()
            if not canonical:
                continue
            linked_source_ids = self._repository.list_source_note_ids_by_canonical(
                platform=source,
                canonical_note_id=canonical,
            )
            if not linked_source_ids:
                linked_source_ids = [canonical]
            for source_id in linked_source_ids:
                candidate = source_id.strip()
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                expanded.append(candidate)
        return expanded

    def _read_lineage_source_ids(self, history: dict[str, Any]) -> list[str]:
        field_decisions = self._decode_field_decisions(history.get("field_decisions"))
        raw = field_decisions.get("lineage_source_ids")
        if isinstance(raw, list):
            values = [str(item).strip() for item in raw if str(item).strip()]
            if values:
                return values
        source = str(history.get("source", "")).strip()
        return self._expand_source_note_ids(
            source=source,
            note_ids=self._decode_json_note_ids(history.get("source_note_ids")),
        )

    def _read_source_link_snapshot(
        self,
        *,
        history: dict[str, Any],
        lineage_source_ids: list[str],
    ) -> dict[str, str]:
        field_decisions = self._decode_field_decisions(history.get("field_decisions"))
        raw_snapshot = field_decisions.get("source_link_snapshot")
        snapshot: dict[str, str] = {}
        if isinstance(raw_snapshot, dict):
            for key, value in raw_snapshot.items():
                source_id = str(key).strip()
                canonical = str(value).strip()
                if source_id and canonical:
                    snapshot[source_id] = canonical
        for source_id in lineage_source_ids:
            snapshot.setdefault(source_id, source_id)
        return snapshot

    def _enforce_merge_format_contract(
        self,
        *,
        markdown: str,
        fallback_title: str,
        conflict_markers: list[str],
    ) -> str:
        content = markdown.strip()
        if not content.startswith("# "):
            if content:
                content = f"# {fallback_title}\n\n{content}".strip()
            else:
                content = f"# {fallback_title}\n\n- 信息不足。"

        section_pattern = re.compile(
            r"(?ms)^##\s*差异与冲突\s*\n(.*?)(?=^##\s|\Z)"
        )
        existing_blocks = [
            match.group(1).strip()
            for match in section_pattern.finditer(content)
            if match.group(1).strip()
        ]
        cleaned = section_pattern.sub("", content).strip()
        if existing_blocks:
            conflict_body = existing_blocks[0]
        else:
            normalized_markers = [
                marker.strip() for marker in conflict_markers if marker.strip()
            ]
            if normalized_markers:
                conflict_body = "\n".join(f"- {marker}" for marker in normalized_markers)
            else:
                conflict_body = "- 未发现明显冲突。"
        if cleaned:
            return f"{cleaned}\n\n## 差异与冲突\n\n{conflict_body}"
        return f"## 差异与冲突\n\n{conflict_body}"
