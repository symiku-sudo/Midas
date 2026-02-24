from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
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
    image_urls: list[str] = field(default_factory=list)


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
            raw_images = record.get("image_urls", [])
            image_urls = []
            if isinstance(raw_images, list):
                image_urls = [
                    str(item).strip()
                    for item in raw_images
                    if isinstance(item, str) and str(item).strip()
                ]

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
                    image_urls=image_urls,
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
    _DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

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
        self._assert_https_and_host(request_url, cfg.host_allowlist)

        method = self._normalize_method(cfg.request_method, field_name="request_method")
        headers = self._build_headers(cfg.request_headers)
        body = cfg.request_body.strip() if method == "POST" else None

        detail_fetch_mode = cfg.detail_fetch_mode.strip().lower() or "auto"
        if detail_fetch_mode not in {"auto", "always", "never"}:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=(
                    "detail_fetch_mode 仅支持 auto/always/never，"
                    f"当前为 {cfg.detail_fetch_mode}"
                ),
                status_code=400,
            )
        detail_url_template = cfg.detail_request_url_template.strip()
        if detail_fetch_mode == "always" and not detail_url_template:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="detail_fetch_mode=always 时必须配置 detail_request_url_template。",
                status_code=400,
            )
        detail_method = self._normalize_method(
            cfg.detail_request_method, field_name="detail_request_method"
        )
        detail_headers = self._build_headers(
            cfg.detail_request_headers, fallback_headers=headers
        )
        detail_body = cfg.detail_request_body.strip() if detail_method == "POST" else None
        max_images = max(int(cfg.max_images_per_note), 0)
        timeout = self._settings.xiaohongshu.request_timeout_seconds

        async with httpx.AsyncClient(timeout=timeout) as client:
            payload = await self._request_json(
                client=client,
                method=method,
                url=request_url,
                headers=headers,
                body=body,
            )

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

                title = (
                    self._read_str(record, cfg.title_field) or f"未命名笔记 {note_id}"
                )
                source_url = self._read_str(record, cfg.source_url_field)
                if not source_url:
                    source_url = f"https://www.xiaohongshu.com/explore/{note_id}"

                content = self._pick_valid_content(
                    payload=record,
                    candidates=cfg.content_field_candidates,
                    title=title,
                )
                image_urls = self._extract_image_urls(
                    payload=record,
                    candidates=cfg.image_field_candidates,
                    max_count=max_images,
                )

                if self._should_fetch_detail(
                    detail_fetch_mode=detail_fetch_mode,
                    content=content,
                    image_urls=image_urls,
                ):
                    detail_payload = await self._fetch_detail_payload(
                        client=client,
                        detail_url_template=detail_url_template,
                        detail_method=detail_method,
                        detail_headers=detail_headers,
                        detail_body=detail_body,
                        note_id=note_id,
                        source_url=source_url,
                        record=record,
                        host_allowlist=cfg.host_allowlist,
                    )
                    if detail_payload is not None:
                        detail_content = self._pick_valid_content(
                            payload=detail_payload,
                            candidates=cfg.detail_content_field_candidates,
                            title=title,
                        )
                        if detail_content:
                            content = detail_content

                        detail_images = self._extract_image_urls(
                            payload=detail_payload,
                            candidates=cfg.detail_image_field_candidates,
                            max_count=max_images,
                        )
                        image_urls = self._merge_image_urls(
                            primary=detail_images,
                            secondary=image_urls,
                            max_count=max_images,
                        )

                if not content:
                    continue

                notes.append(
                    XiaohongshuNote(
                        note_id=note_id,
                        title=title,
                        content=content,
                        source_url=source_url,
                        image_urls=image_urls,
                    )
                )

        if not notes:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=(
                    "小红书响应中未提取到可用正文。请检查 content_field_candidates、"
                    "detail_content_field_candidates 或详情接口配置。"
                ),
                status_code=502,
            )
        return notes

    def _normalize_method(self, raw_method: str, *, field_name: str) -> str:
        method = raw_method.strip().upper() or "GET"
        if method not in {"GET", "POST"}:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"web_readonly.{field_name} 仅支持 GET/POST，当前为 {method}",
                status_code=400,
            )
        return method

    def _assert_https_and_host(self, url: str, host_allowlist: list[str]) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="web_readonly 仅允许 HTTPS 请求。",
                status_code=400,
            )
        if parsed.netloc not in set(host_allowlist):
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"请求域名不在白名单中：{parsed.netloc}",
                status_code=400,
            )

    def _build_headers(
        self,
        raw_headers: dict[str, str],
        fallback_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {}
        if fallback_headers:
            headers.update({k: v for k, v in fallback_headers.items() if k and v})
        headers.update({k: v for k, v in raw_headers.items() if k and v})
        if self._settings.xiaohongshu.cookie and "Cookie" not in headers:
            headers["Cookie"] = self._settings.xiaohongshu.cookie
        if "User-Agent" not in headers:
            headers["User-Agent"] = self._DEFAULT_USER_AGENT
        return headers

    async def _request_json(
        self,
        *,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: dict[str, str],
        body: str | None,
    ) -> dict:
        try:
            response = await client.request(
                method=method,
                url=url,
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
                message="小红书鉴权失败，请检查 Cookie 或 Header 是否失效。",
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

        if not isinstance(payload, dict):
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="小红书响应 JSON 顶层不是对象。",
                status_code=502,
            )
        return payload

    async def _fetch_detail_payload(
        self,
        *,
        client: httpx.AsyncClient,
        detail_url_template: str,
        detail_method: str,
        detail_headers: dict[str, str],
        detail_body: str | None,
        note_id: str,
        source_url: str,
        record: dict,
        host_allowlist: list[str],
    ) -> dict | None:
        if not detail_url_template:
            return None

        detail_url = self._build_detail_url(
            template=detail_url_template,
            note_id=note_id,
            source_url=source_url,
            record=record,
        )
        self._assert_https_and_host(detail_url, host_allowlist)
        return await self._request_json(
            client=client,
            method=detail_method,
            url=detail_url,
            headers=detail_headers,
            body=detail_body,
        )

    def _build_detail_url(
        self,
        *,
        template: str,
        note_id: str,
        source_url: str,
        record: dict,
    ) -> str:
        variables = {
            "note_id": note_id,
            "xsec_token": self._read_str(record, "xsec_token"),
            "xsec_source": self._read_str(record, "xsec_source"),
            "user_id": self._read_str(record, "user.user_id"),
            "source_url": source_url,
        }
        try:
            url = template.format(**variables).strip()
        except KeyError as exc:
            missing = str(exc).strip("'")
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"detail_request_url_template 包含未知占位符：{missing}",
                status_code=400,
            ) from exc
        if not url:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="detail_request_url_template 渲染后为空 URL。",
                status_code=400,
            )
        return url

    def _should_fetch_detail(
        self,
        *,
        detail_fetch_mode: str,
        content: str,
        image_urls: list[str],
    ) -> bool:
        if detail_fetch_mode == "always":
            return True
        if detail_fetch_mode == "never":
            return False
        return not content or not image_urls

    def _pick_valid_content(
        self,
        *,
        payload: object,
        candidates: list[str],
        title: str,
    ) -> str:
        title_trimmed = title.strip()
        for field_name in candidates:
            candidate = self._read_str(payload, field_name)
            if not candidate:
                continue
            if candidate.strip() == title_trimmed:
                continue
            return candidate
        return ""

    def _extract_image_urls(
        self,
        *,
        payload: object,
        candidates: list[str],
        max_count: int,
    ) -> list[str]:
        if max_count <= 0:
            return []

        urls: list[str] = []
        seen: set[str] = set()
        for field_name in candidates:
            value = self._read_value(payload, field_name)
            self._collect_image_urls(
                value=value,
                key_hint=field_name,
                urls=urls,
                seen=seen,
                max_count=max_count,
            )
            if len(urls) >= max_count:
                return urls

        if not urls:
            self._collect_image_urls(
                value=payload,
                key_hint="",
                urls=urls,
                seen=seen,
                max_count=max_count,
            )
        return urls

    def _collect_image_urls(
        self,
        *,
        value: object,
        key_hint: str,
        urls: list[str],
        seen: set[str],
        max_count: int,
    ) -> None:
        if len(urls) >= max_count or value is None:
            return

        if isinstance(value, str):
            candidate = value.strip()
            if self._looks_like_image_url(candidate, key_hint) and candidate not in seen:
                seen.add(candidate)
                urls.append(candidate)
            return

        if isinstance(value, dict):
            for key, item in value.items():
                if len(urls) >= max_count:
                    break
                nested_hint = f"{key_hint}.{key}" if key_hint else str(key)
                self._collect_image_urls(
                    value=item,
                    key_hint=nested_hint,
                    urls=urls,
                    seen=seen,
                    max_count=max_count,
                )
            return

        if isinstance(value, list):
            for item in value:
                if len(urls) >= max_count:
                    break
                self._collect_image_urls(
                    value=item,
                    key_hint=key_hint,
                    urls=urls,
                    seen=seen,
                    max_count=max_count,
                )

    def _looks_like_image_url(self, value: str, key_hint: str) -> bool:
        if not value or not value.startswith(("http://", "https://")):
            return False

        hint = key_hint.lower()
        if "avatar" in hint:
            return False

        lower = value.lower()
        if any(
            lower.endswith(ext)
            for ext in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif")
        ):
            return True
        if "xhscdn.com" in lower:
            return True
        if any(token in hint for token in ("image", "img", "cover", "pic", "photo")):
            return True
        return False

    def _merge_image_urls(
        self,
        *,
        primary: list[str],
        secondary: list[str],
        max_count: int,
    ) -> list[str]:
        if max_count <= 0:
            return []

        merged: list[str] = []
        seen: set[str] = set()
        for url in [*primary, *secondary]:
            item = str(url).strip()
            if not item or item in seen:
                continue
            seen.add(item)
            merged.append(item)
            if len(merged) >= max_count:
                break
        return merged

    def _dig(self, payload: object, dot_path: str):
        return self._read_value(payload, dot_path)

    def _read_value(self, payload: object, dot_path: str) -> object | None:
        current: object = payload
        for segment in dot_path.split("."):
            key = segment.strip()
            if not key:
                continue
            if isinstance(current, dict):
                current = current.get(key)
                continue
            if isinstance(current, list):
                if not key.isdigit():
                    return None
                index = int(key)
                if index < 0 or index >= len(current):
                    return None
                current = current[index]
                continue
            return None
        return current

    def _read_str(self, payload: object, dot_path: str) -> str:
        current = self._read_value(payload, dot_path)
        if current is None:
            return ""
        if isinstance(current, str):
            return current.strip()
        if isinstance(current, (int, float, bool)):
            return str(current).strip()
        if isinstance(current, list):
            texts = [
                str(item).strip()
                for item in current
                if isinstance(item, (str, int, float, bool)) and str(item).strip()
            ]
            return "\n".join(texts).strip()
        if isinstance(current, dict):
            for key in ("desc", "content", "text", "title"):
                value = current.get(key)
                if isinstance(value, (str, int, float, bool)):
                    text = str(value).strip()
                    if text:
                        return text
        return ""


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
                    image_urls=note.image_urls,
                )
                summary = self._ensure_source_link(summary, note.source_url)
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

    def _ensure_source_link(self, summary_markdown: str, source_url: str) -> str:
        if not source_url:
            return summary_markdown
        if source_url in summary_markdown:
            return summary_markdown
        summary = summary_markdown.rstrip()
        suffix = f"原文链接：[点击查看]({source_url})"
        if not summary:
            return suffix + "\n"
        return f"{summary}\n\n---\n\n{suffix}\n"

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
