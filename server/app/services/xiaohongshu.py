from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.schemas import XiaohongshuSummaryItem, XiaohongshuSyncData
from app.repositories.xiaohongshu_repo import XiaohongshuSyncRepository
from app.services.llm import LLMService

_DEFAULT_NOTES: list[dict[str, str]] = [
    {
        "note_id": "mock-note-001",
        "title": "高效晨间流程",
        "content": "早起后先补水、10分钟拉伸、列出3件最重要任务。",
        "source_url": "https://www.xiaohongshu.com/explore/mock-note-001",
    },
    {
        "note_id": "mock-note-002",
        "title": "低成本办公桌改造",
        "content": "通过灯光分层和收纳分区，让工作空间更专注。",
        "source_url": "https://www.xiaohongshu.com/explore/mock-note-002",
    },
    {
        "note_id": "mock-note-003",
        "title": "一周健身计划",
        "content": "周一上肢、周三下肢、周五全身耐力，穿插轻有氧。",
        "source_url": "https://www.xiaohongshu.com/explore/mock-note-003",
    },
    {
        "note_id": "mock-note-004",
        "title": "阅读笔记方法",
        "content": "每章记录关键词、核心观点和行动建议，周末统一复盘。",
        "source_url": "https://www.xiaohongshu.com/explore/mock-note-004",
    },
    {
        "note_id": "mock-note-005",
        "title": "视频剪辑效率清单",
        "content": "先做脚本分镜，再建模板工程，最后批量套用字幕样式。",
        "source_url": "https://www.xiaohongshu.com/explore/mock-note-005",
    },
]


@dataclass(frozen=True)
class XiaohongshuNote:
    note_id: str
    title: str
    content: str
    source_url: str


class MockXiaohongshuSource:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
        records = self._load_records()
        notes: list[XiaohongshuNote] = []
        for index, record in enumerate(records[:limit]):
            note_id = str(record.get("note_id", "")).strip()
            title = str(record.get("title", "")).strip()
            content = str(record.get("content", "")).strip()
            source_url = str(record.get("source_url", "")).strip()

            if not note_id:
                raise AppError(
                    code=ErrorCode.UPSTREAM_ERROR,
                    message=f"mock 数据第 {index + 1} 条缺少 note_id。",
                    status_code=500,
                )
            if not title:
                title = f"未命名笔记 {note_id}"
            if not content:
                content = "（空内容）"
            if not source_url:
                source_url = f"https://www.xiaohongshu.com/explore/{note_id}"

            notes.append(
                XiaohongshuNote(
                    note_id=note_id,
                    title=title,
                    content=content,
                    source_url=source_url,
                )
            )
        return notes

    def _load_records(self) -> list[dict[str, str]]:
        mock_path = self._settings.xiaohongshu.mock_notes_path.strip()
        if not mock_path:
            return _DEFAULT_NOTES

        path = Path(mock_path).expanduser()
        if not path.exists():
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"mock_notes_path 不存在: {path}",
                status_code=400,
            )

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="mock_notes_path JSON 格式错误。",
                status_code=400,
            ) from exc

        if not isinstance(raw, list):
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="mock_notes_path 必须是 JSON 数组。",
                status_code=400,
            )
        return raw


class XiaohongshuSyncService:
    def __init__(
        self,
        settings: Settings,
        repository: XiaohongshuSyncRepository | None = None,
        source: MockXiaohongshuSource | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository or XiaohongshuSyncRepository(
            settings.xiaohongshu.db_path
        )
        self._source = source or MockXiaohongshuSource(settings)
        self._llm_service = llm_service or LLMService(settings)

    async def sync(self, limit: int | None) -> XiaohongshuSyncData:
        requested_limit = limit or self._settings.xiaohongshu.default_limit
        if requested_limit > self._settings.xiaohongshu.max_limit:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=(
                    f"limit 超过上限，当前最大允许 {self._settings.xiaohongshu.max_limit}。"
                ),
                status_code=400,
            )

        mode = self._settings.xiaohongshu.mode.strip().lower()
        if mode != "mock":
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="当前仅支持 xiaohongshu.mode=mock。",
                status_code=400,
            )

        notes = self._source.fetch_recent(requested_limit)
        fetched_count = len(notes)
        new_count = 0
        skipped_count = 0
        failed_count = 0
        consecutive_failures = 0
        summaries: list[XiaohongshuSummaryItem] = []

        for index, note in enumerate(notes):
            if self._repository.is_synced(note.note_id):
                skipped_count += 1
                continue

            try:
                summary = await self._llm_service.summarize_xiaohongshu_note(
                    note_id=note.note_id,
                    title=note.title,
                    content=note.content,
                    source_url=note.source_url,
                )
                self._repository.mark_synced(
                    note_id=note.note_id, title=note.title, source_url=note.source_url
                )
                summaries.append(
                    XiaohongshuSummaryItem(
                        note_id=note.note_id,
                        title=note.title,
                        source_url=note.source_url,
                        summary_markdown=summary,
                    )
                )
                new_count += 1
                consecutive_failures = 0
            except AppError as exc:
                failed_count += 1
                consecutive_failures += 1
                if (
                    consecutive_failures
                    >= self._settings.xiaohongshu.circuit_breaker_failures
                ):
                    raise AppError(
                        code=ErrorCode.CIRCUIT_OPEN,
                        message="小红书同步连续失败已触发熔断，本次任务已停止。",
                        status_code=429,
                        details={
                            "requested_limit": requested_limit,
                            "fetched_count": fetched_count,
                            "new_count": new_count,
                            "skipped_count": skipped_count,
                            "failed_count": failed_count,
                            "circuit_opened": True,
                            "last_error_code": exc.code.value,
                            "last_error_message": exc.message,
                            "summaries": [item.model_dump() for item in summaries],
                        },
                    ) from exc

            if index < fetched_count - 1:
                await self._delay_between_requests(mode=mode)

        return XiaohongshuSyncData(
            requested_limit=requested_limit,
            fetched_count=fetched_count,
            new_count=new_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            circuit_opened=False,
            summaries=summaries,
        )

    async def _delay_between_requests(self, *, mode: str) -> None:
        if mode == "mock":
            return

        min_delay = self._settings.xiaohongshu.random_delay_min_seconds
        max_delay = self._settings.xiaohongshu.random_delay_max_seconds
        if min_delay < 0 or max_delay < 0:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="随机延迟配置不能为负数。",
                status_code=400,
            )
        if max_delay < min_delay:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="随机延迟配置错误：max_delay 小于 min_delay。",
                status_code=400,
            )

        await asyncio.sleep(random.uniform(min_delay, max_delay))

