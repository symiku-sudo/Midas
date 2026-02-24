from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse

import httpx

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


class XiaohongshuWebReadonlySource:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
        cfg = self._settings.xiaohongshu.web_readonly
        request_url = cfg.request_url.strip()
        if not request_url:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="web_readonly 模式缺少 request_url 配置。",
                status_code=400,
            )

        parsed = urlparse(request_url)
        if parsed.scheme != "https":
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="web_readonly 仅允许 HTTPS 请求。",
                status_code=400,
            )
        if parsed.netloc not in set(cfg.host_allowlist):
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"请求域名不在白名单中：{parsed.netloc}",
                status_code=400,
            )

        method = cfg.request_method.strip().upper()
        if method not in {"GET", "POST"}:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"web_readonly 仅支持 GET/POST，当前为 {method}",
                status_code=400,
            )

        headers = {k: v for k, v in cfg.request_headers.items() if k and v}
        if self._settings.xiaohongshu.cookie and "Cookie" not in headers:
            headers["Cookie"] = self._settings.xiaohongshu.cookie
        if "User-Agent" not in headers:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )

        body = cfg.request_body.strip() if method == "POST" else None
        timeout = self._settings.xiaohongshu.request_timeout_seconds

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=request_url,
                    headers=headers,
                    content=body,
                )
        except httpx.HTTPError as exc:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="请求小红书网页端接口失败。",
                status_code=502,
            ) from exc

        if response.status_code in {401, 403}:
            raise AppError(
                code=ErrorCode.AUTH_EXPIRED,
                message="小红书鉴权失败，请检查 Cookie 是否失效。",
                status_code=401,
            )
        if response.status_code == 429:
            raise AppError(
                code=ErrorCode.RATE_LIMITED,
                message="小红书请求触发限流，请稍后重试。",
                status_code=429,
            )
        if response.status_code >= 400:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=f"小红书请求失败（HTTP {response.status_code}）。",
                status_code=502,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="小红书响应不是合法 JSON。",
                status_code=502,
            ) from exc

        records = self._dig(payload, cfg.items_path)
        if not isinstance(records, list):
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=f"响应中 items_path 无法解析为列表：{cfg.items_path}",
                status_code=502,
            )

        notes: list[XiaohongshuNote] = []
        for record in records:
            if len(notes) >= limit:
                break
            if not isinstance(record, dict):
                continue

            note_id = self._read_str(record, cfg.note_id_field)
            if not note_id:
                continue
            title = self._read_str(record, cfg.title_field) or f"未命名笔记 {note_id}"
            content = ""
            for field_name in cfg.content_field_candidates:
                content = self._read_str(record, field_name)
                if content:
                    break
            if not content:
                content = "（空内容）"

            source_url = self._read_str(record, cfg.source_url_field)
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

        if not notes:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="小红书响应中未提取到可用笔记。",
                status_code=502,
            )
        return notes

    def _dig(self, payload: dict, dot_path: str):
        current: object = payload
        for segment in dot_path.split("."):
            if not segment:
                continue
            if not isinstance(current, dict):
                return None
            current = current.get(segment)
        return current

    def _read_str(self, payload: dict, dot_path: str) -> str:
        current: object = payload
        for segment in dot_path.split("."):
            if not segment:
                continue
            if not isinstance(current, dict):
                return ""
            current = current.get(segment)
        if current is None:
            return ""
        return str(current).strip()


class XiaohongshuSyncService:
    def __init__(
        self,
        settings: Settings,
        repository: XiaohongshuSyncRepository | None = None,
        source: MockXiaohongshuSource | None = None,
        web_source: XiaohongshuWebReadonlySource | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository or XiaohongshuSyncRepository(
            settings.xiaohongshu.db_path
        )
        self._source = source or MockXiaohongshuSource(settings)
        self._web_source = web_source or XiaohongshuWebReadonlySource(settings)
        self._llm_service = llm_service or LLMService(settings)

    async def sync(
        self,
        limit: int | None,
        confirm_live: bool = False,
        progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
    ) -> XiaohongshuSyncData:
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
        if mode == "mock":
            notes = self._source.fetch_recent(requested_limit)
        elif mode == "web_readonly":
            if not confirm_live:
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=(
                        "web_readonly 模式需要显式确认。请在请求体中传 confirm_live=true。"
                    ),
                    status_code=400,
                )
            self._enforce_live_sync_interval()
            notes = await self._web_source.fetch_recent(requested_limit)
        else:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="当前仅支持 xiaohongshu.mode=mock 或 web_readonly。",
                status_code=400,
            )

        fetched_count = len(notes)
        await self._emit_progress(
            progress_callback,
            current=0,
            total=fetched_count,
            message="已拉取笔记列表，开始处理。",
        )

        processed_count = 0
        new_count = 0
        skipped_count = 0
        failed_count = 0
        consecutive_failures = 0
        summaries: list[XiaohongshuSummaryItem] = []

        for index, note in enumerate(notes):
            if self._repository.is_synced(note.note_id):
                skipped_count += 1
                processed_count += 1
                await self._emit_progress(
                    progress_callback,
                    current=processed_count,
                    total=fetched_count,
                    message=f"已跳过重复笔记：{note.note_id}",
                )
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
                processed_count += 1
                await self._emit_progress(
                    progress_callback,
                    current=processed_count,
                    total=fetched_count,
                    message=f"已处理笔记：{note.note_id}",
                )
            except AppError as exc:
                failed_count += 1
                consecutive_failures += 1
                processed_count += 1
                await self._emit_progress(
                    progress_callback,
                    current=processed_count,
                    total=fetched_count,
                    message=f"处理失败笔记：{note.note_id}",
                )
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
                            "processed_count": processed_count,
                            "circuit_opened": True,
                            "last_error_code": exc.code.value,
                            "last_error_message": exc.message,
                            "summaries": [item.model_dump() for item in summaries],
                        },
                    ) from exc

            if index < fetched_count - 1:
                await self._delay_between_requests(mode=mode)

        result = XiaohongshuSyncData(
            requested_limit=requested_limit,
            fetched_count=fetched_count,
            new_count=new_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            circuit_opened=False,
            summaries=summaries,
        )

        if mode == "web_readonly":
            self._repository.set_state("last_live_sync_ts", str(int(time.time())))

        return result

    async def _emit_progress(
        self,
        callback: Callable[[int, int, str], Awaitable[None]] | None,
        *,
        current: int,
        total: int,
        message: str,
    ) -> None:
        if callback is None:
            return
        await callback(current, total, message)

    def _enforce_live_sync_interval(self) -> None:
        last_sync_raw = self._repository.get_state("last_live_sync_ts")
        if not last_sync_raw:
            return
        try:
            last_sync = int(last_sync_raw)
        except ValueError:
            return

        min_interval = self._settings.xiaohongshu.min_live_sync_interval_seconds
        now = int(time.time())
        delta = now - last_sync
        if delta < min_interval:
            wait_seconds = max(min_interval - delta, 0)
            raise AppError(
                code=ErrorCode.RATE_LIMITED,
                message=f"为降低风控，距离上次真实同步过短，请 {wait_seconds} 秒后重试。",
                status_code=429,
                details={"wait_seconds": wait_seconds},
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
