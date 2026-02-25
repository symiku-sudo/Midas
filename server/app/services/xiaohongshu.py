from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Iterator
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.schemas import XiaohongshuSummaryItem, XiaohongshuSyncData
from app.repositories.xiaohongshu_repo import XiaohongshuSyncRepository
from app.services.asr import ASRService
from app.services.audio_fetcher import AudioFetcher
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
    is_video: bool = False


@dataclass(frozen=True)
class XiaohongshuPageBatch:
    notes: list[XiaohongshuNote]
    request_cursor: str = ""
    next_cursor: str = ""
    exhausted: bool = False


class MockXiaohongshuSource:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def iter_recent(self) -> Iterator[XiaohongshuNote]:
        records = self._load_records()
        for index, record in enumerate(records):
            yield self._build_note_from_record(index=index, record=record)

    def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
        notes: list[XiaohongshuNote] = []
        for index, note in enumerate(self.iter_recent()):
            if index >= limit:
                break
            notes.append(note)
        return notes

    def _build_note_from_record(self, *, index: int, record: dict[str, str]) -> XiaohongshuNote:
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
        is_video = bool(record.get("is_video", False))

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

        return XiaohongshuNote(
            note_id=note_id,
            title=title,
            content=content,
            source_url=source_url,
            image_urls=image_urls,
            is_video=is_video,
        )

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
    _INITIAL_STATE_PATTERN = re.compile(
        r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S
    )
    _HAS_MORE_PATHS = (
        "data.has_more",
        "data.hasMore",
        "has_more",
        "hasMore",
        "data.page.has_more",
        "data.page.hasMore",
    )
    _CURSOR_PATHS = (
        "data.cursor",
        "data.next_cursor",
        "data.nextCursor",
        "cursor",
        "next_cursor",
        "nextCursor",
        "data.page.cursor",
        "data.page.next_cursor",
        "data.page.nextCursor",
    )

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
        notes: list[XiaohongshuNote] = []
        async for note in self.iter_recent():
            notes.append(note)
            if len(notes) >= limit:
                break
        return notes

    async def iter_recent(self) -> AsyncIterator[XiaohongshuNote]:
        async for batch in self.iter_pages():
            for note in batch.notes:
                yield note

    async def iter_pages(
        self,
        *,
        start_cursor: str | None = None,
        force_head: bool = False,
        max_pages: int | None = None,
    ) -> AsyncIterator[XiaohongshuPageBatch]:
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

        page_url = request_url
        page_body = body
        page_cursor = ""
        normalized_start_cursor = (start_cursor or "").strip()
        if normalized_start_cursor and not force_head:
            next_page = self._build_next_page_request(
                method=method,
                current_url=request_url,
                current_body=body,
                next_cursor=normalized_start_cursor,
            )
            if next_page is not None:
                page_url, page_body = next_page
                page_cursor = normalized_start_cursor
        seen_page_tokens: set[tuple[str, str | None]] = set()
        emitted_any = False
        page_count = 0
        stopped_by_page_limit = False

        async with httpx.AsyncClient(timeout=timeout) as client:
            while True:
                payload = await self._request_json(
                    client=client,
                    method=method,
                    url=page_url,
                    headers=headers,
                    body=page_body,
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
                    if not isinstance(record, dict):
                        continue
                    note = await self._extract_note_from_record(
                        client=client,
                        record=record,
                        cfg=cfg,
                        headers=headers,
                        detail_fetch_mode=detail_fetch_mode,
                        detail_url_template=detail_url_template,
                        detail_method=detail_method,
                        detail_headers=detail_headers,
                        detail_body=detail_body,
                        max_images=max_images,
                    )
                    if note is None:
                        continue
                    emitted_any = True
                    notes.append(note)

                has_more = self._extract_has_more(payload)
                next_cursor = self._extract_next_cursor(payload)
                exhausted = (not has_more) and (not next_cursor)
                yield XiaohongshuPageBatch(
                    notes=notes,
                    request_cursor=page_cursor,
                    next_cursor=next_cursor,
                    exhausted=exhausted,
                )
                page_count += 1
                if max_pages is not None and max_pages > 0 and page_count >= max_pages:
                    stopped_by_page_limit = True
                    break
                if not has_more and not next_cursor:
                    break
                if not next_cursor:
                    break

                next_page = self._build_next_page_request(
                    method=method,
                    current_url=page_url,
                    current_body=page_body,
                    next_cursor=next_cursor,
                )
                if next_page is None:
                    break
                if next_page == (page_url, page_body):
                    break
                page_url, page_body = next_page
                page_cursor = next_cursor
                page_token = (page_url, page_body)
                if page_token in seen_page_tokens:
                    break
                seen_page_tokens.add(page_token)

        if not emitted_any and not stopped_by_page_limit:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=(
                    "小红书响应中未提取到可用正文。请检查列表字段映射、"
                    "笔记页解析或详情接口配置。"
                ),
                status_code=502,
            )

    async def _extract_note_from_record(
        self,
        *,
        client: httpx.AsyncClient,
        record: dict,
        cfg,
        headers: dict[str, str],
        detail_fetch_mode: str,
        detail_url_template: str,
        detail_method: str,
        detail_headers: dict[str, str],
        detail_body: str | None,
        max_images: int,
    ) -> XiaohongshuNote | None:
        note_id = self._read_str(record, cfg.note_id_field)
        if not note_id:
            return None

        title = self._read_str(record, cfg.title_field) or f"未命名笔记 {note_id}"
        source_url = self._read_str(record, cfg.source_url_field)
        if not source_url:
            source_url = f"https://www.xiaohongshu.com/explore/{note_id}"
        is_video = self._is_video_note(record)

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

        page_note = await self._fetch_note_from_page(
            client=client,
            note_id=note_id,
            source_url=source_url,
            record=record,
            headers=headers,
            host_allowlist=cfg.host_allowlist,
        )
        if page_note is not None:
            page_title = self._read_str(page_note, "title")
            if page_title:
                title = page_title

            page_content = self._pick_valid_content(
                payload=page_note,
                candidates=[
                    "desc",
                    "content",
                    "note_desc",
                    "noteDesc",
                    "note_text",
                ],
                title=title,
            )
            if page_content:
                content = page_content

            page_images = self._extract_image_urls(
                payload=page_note,
                candidates=["imageList", "image_list", "images", "cover"],
                max_count=max_images,
            )
            image_urls = self._merge_image_urls(
                primary=page_images,
                secondary=image_urls,
                max_count=max_images,
            )
            is_video = is_video or self._is_video_note(page_note)

        if (not is_video) and self._should_fetch_detail(
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
                is_video = is_video or self._is_video_note(detail_payload)
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

        if not content and not is_video:
            return None

        return XiaohongshuNote(
            note_id=note_id,
            title=title,
            content=content,
            source_url=source_url,
            image_urls=image_urls,
            is_video=is_video,
        )

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

    def _extract_has_more(self, payload: dict) -> bool:
        for path in self._HAS_MORE_PATHS:
            value = self._read_value(payload, path)
            parsed = self._coerce_bool(value)
            if parsed is not None:
                return parsed
        return False

    def _extract_next_cursor(self, payload: dict) -> str:
        for path in self._CURSOR_PATHS:
            value = self._read_str(payload, path)
            if value:
                return value
        return ""

    def _coerce_bool(self, value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y"}:
                return True
            if normalized in {"0", "false", "no", "n"}:
                return False
        return None

    def _build_next_page_request(
        self,
        *,
        method: str,
        current_url: str,
        current_body: str | None,
        next_cursor: str,
    ) -> tuple[str, str | None] | None:
        if not next_cursor:
            return None

        if method == "GET":
            parsed = urlparse(current_url)
            query_items = parse_qsl(parsed.query, keep_blank_values=True)
            cursor_key = next(
                (key for key, _ in query_items if "cursor" in key.lower()),
                "cursor",
            )
            replaced = False
            next_query_items: list[tuple[str, str]] = []
            for key, value in query_items:
                if key == cursor_key:
                    next_query_items.append((key, next_cursor))
                    replaced = True
                else:
                    next_query_items.append((key, value))
            if not replaced:
                next_query_items.append((cursor_key, next_cursor))
            next_query = urlencode(next_query_items, doseq=True)
            next_url = urlunparse(parsed._replace(query=next_query))
            return next_url, None

        if method == "POST":
            body_obj: dict[str, object]
            if current_body:
                try:
                    parsed_body = json.loads(current_body)
                except json.JSONDecodeError:
                    return None
                if not isinstance(parsed_body, dict):
                    return None
                body_obj = dict(parsed_body)
            else:
                body_obj = {}

            cursor_key = next(
                (key for key in body_obj.keys() if "cursor" in str(key).lower()),
                "cursor",
            )
            body_obj[cursor_key] = next_cursor
            next_body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
            return current_url, next_body

        return None

    async def _fetch_note_from_page(
        self,
        *,
        client: httpx.AsyncClient,
        note_id: str,
        source_url: str,
        record: dict,
        headers: dict[str, str],
        host_allowlist: list[str],
    ) -> dict | None:
        page_url = self._build_note_page_url(
            note_id=note_id, source_url=source_url, record=record
        )
        self._assert_https_and_host(page_url, host_allowlist)
        html = await self._request_text(
            client=client,
            method="GET",
            url=page_url,
            headers=headers,
            body=None,
            best_effort=True,
        )
        if not html:
            return None

        initial_state = self._extract_initial_state(html)
        if initial_state is None:
            return None
        return self._extract_note_from_initial_state(initial_state, note_id)

    async def _request_text(
        self,
        *,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: dict[str, str],
        body: str | None,
        best_effort: bool,
    ) -> str:
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
            )
        except httpx.HTTPError:
            if best_effort:
                return ""
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="请求小红书网页端接口失败。",
                status_code=502,
            ) from None

        if response.status_code in {401, 403, 429}:
            if best_effort:
                return ""

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
            if best_effort:
                return ""
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=f"小红书请求失败（HTTP {response.status_code}）。",
                status_code=502,
            )
        return str(getattr(response, "text", "") or "")

    def _build_note_page_url(self, *, note_id: str, source_url: str, record: dict) -> str:
        parsed_source = urlparse(source_url)
        if parsed_source.scheme == "https" and parsed_source.netloc == "www.xiaohongshu.com":
            base_url = f"https://www.xiaohongshu.com{parsed_source.path or f'/explore/{note_id}'}"
        else:
            base_url = f"https://www.xiaohongshu.com/explore/{note_id}"

        xsec_token = self._read_str(record, "xsec_token")
        xsec_source = self._read_str(record, "xsec_source") or "pc_feed"
        if not xsec_token:
            return base_url
        return (
            f"{base_url}?xsec_token={quote(xsec_token, safe='')}"
            f"&xsec_source={quote(xsec_source, safe='')}"
        )

    def _extract_initial_state(self, html: str) -> dict | None:
        match = self._INITIAL_STATE_PATTERN.search(html)
        if match is None:
            return None

        raw = match.group(1)
        normalized = re.sub(
            r"(?<=:)\s*(?:undefined|NaN|Infinity|void 0)\s*(?=[,}])",
            "null",
            raw,
        )
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _extract_note_from_initial_state(
        self, initial_state: dict, note_id: str
    ) -> dict | None:
        note_map = self._read_value(initial_state, "note.noteDetailMap")
        if isinstance(note_map, dict):
            note_node = note_map.get(note_id)
            if isinstance(note_node, dict):
                if isinstance(note_node.get("note"), dict):
                    return note_node["note"]
                return note_node
        return self._find_note_payload_by_id(initial_state, note_id)

    def _find_note_payload_by_id(self, payload: object, note_id: str) -> dict | None:
        if isinstance(payload, dict):
            current_note_id = self._read_str(payload, "noteId") or self._read_str(
                payload, "note_id"
            )
            if current_note_id == note_id and any(
                key in payload
                for key in (
                    "desc",
                    "title",
                    "imageList",
                    "image_list",
                    "type",
                    "video",
                    "videoInfo",
                )
            ):
                return payload

            note_node = payload.get("note")
            if isinstance(note_node, dict):
                note_node_id = self._read_str(note_node, "noteId") or self._read_str(
                    note_node, "note_id"
                )
                if note_node_id == note_id:
                    return note_node

            for value in payload.values():
                found = self._find_note_payload_by_id(value, note_id)
                if found is not None:
                    return found
            return None

        if isinstance(payload, list):
            for item in payload:
                found = self._find_note_payload_by_id(item, note_id)
                if found is not None:
                    return found
        return None

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

    def _is_video_note(self, payload: object) -> bool:
        for field_name in (
            "type",
            "note_type",
            "media_type",
            "note_card.type",
            "note_card.note_type",
            "data.items.0.note_card.type",
            "data.items.0.note_card.note_type",
        ):
            value = self._read_str(payload, field_name).lower()
            if value in {"video", "videonote", "video_note", "note_video", "短视频"}:
                return True

        for field_name in (
            "video",
            "video_info",
            "video_play_info",
            "note_card.video",
            "note_card.video_info",
            "note_card.video_play_info",
            "data.items.0.note_card.video",
            "data.items.0.note_card.video_info",
        ):
            if self._read_value(payload, field_name) is not None:
                return True
        return False

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
    _LIVE_CURSOR_STATE_KEY = "live_sync_cursor"
    _LIVE_CURSOR_FINGERPRINT_STATE_KEY = "live_sync_cursor_fingerprint"
    _HEAD_SHORT_SCAN_PAGES = 2

    def __init__(
        self,
        settings: Settings,
        repository: XiaohongshuSyncRepository | None = None,
        source: MockXiaohongshuSource | None = None,
        web_source: XiaohongshuWebReadonlySource | None = None,
        llm_service: LLMService | None = None,
        audio_fetcher: AudioFetcher | None = None,
        asr_service: ASRService | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository or XiaohongshuSyncRepository(
            settings.xiaohongshu.db_path
        )
        self._source = source or MockXiaohongshuSource(settings)
        self._web_source = web_source or XiaohongshuWebReadonlySource(settings)
        self._llm_service = llm_service or LLMService(settings)
        self._audio_fetcher = audio_fetcher or AudioFetcher(settings)
        self._asr_service = asr_service or ASRService(settings)

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
        if mode == "web_readonly":
            if not confirm_live:
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=(
                        "web_readonly 模式需要显式确认。请在请求体中传 confirm_live=true。"
                    ),
                    status_code=400,
                )
            self._enforce_live_sync_interval()
        elif mode != "mock":
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="当前仅支持 xiaohongshu.mode=mock 或 web_readonly。",
                status_code=400,
            )

        await self._emit_progress(
            progress_callback,
            current=0,
            total=requested_limit,
            message=f"开始同步，目标有效笔记 {requested_limit} 条。",
        )

        fetched_count = 0
        processed_count = 0
        new_count = 0
        skipped_count = 0
        failed_count = 0
        consecutive_failures = 0
        summaries: list[XiaohongshuSummaryItem] = []
        first_note = True
        seen_note_ids: set[str] = set()

        async for note in self._iter_candidate_notes(mode=mode, requested_limit=requested_limit):
            if mode != "mock":
                if first_note:
                    first_note = False
                else:
                    await self._delay_between_requests(mode=mode)

            if note.note_id in seen_note_ids:
                continue
            seen_note_ids.add(note.note_id)
            fetched_count += 1
            if self._repository.is_synced(note.note_id):
                skipped_count += 1
                processed_count += 1
                await self._emit_progress(
                    progress_callback,
                    current=new_count,
                    total=requested_limit,
                    message=f"已跳过重复笔记：{note.note_id}（有效 {new_count}/{requested_limit}）",
                )
                continue

            try:
                if note.is_video:
                    summary = await self._summarize_video_note(note)
                else:
                    summary = await self._llm_service.summarize_xiaohongshu_note(
                        note_id=note.note_id,
                        title=note.title,
                        content=note.content,
                        source_url=note.source_url,
                        image_urls=note.image_urls,
                    )
                summary = self._ensure_source_link(summary, note.source_url)
                summaries.append(
                    XiaohongshuSummaryItem(
                        note_id=note.note_id,
                        title=note.title,
                        source_url=note.source_url,
                        summary_markdown=summary,
                    )
                )
                # Only mark dedupe id after summary payload is successfully built.
                self._repository.mark_synced(
                    note_id=note.note_id, title=note.title, source_url=note.source_url
                )
                new_count += 1
                consecutive_failures = 0
                processed_count += 1
                await self._emit_progress(
                    progress_callback,
                    current=new_count,
                    total=requested_limit,
                    message=f"已完成有效同步：{new_count}/{requested_limit}（{note.note_id}）",
                )
            except AppError as exc:
                failed_count += 1
                consecutive_failures += 1
                processed_count += 1
                await self._emit_progress(
                    progress_callback,
                    current=new_count,
                    total=requested_limit,
                    message=f"处理失败笔记：{note.note_id}（有效 {new_count}/{requested_limit}）",
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

            if new_count >= requested_limit:
                break

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

    async def _iter_candidate_notes(
        self, *, mode: str, requested_limit: int
    ) -> AsyncIterator[XiaohongshuNote]:
        if mode == "mock":
            iter_recent = getattr(self._source, "iter_recent", None)
            if callable(iter_recent):
                for note in iter_recent():
                    yield note
                return
            for note in self._source.fetch_recent(requested_limit):
                yield note
            return

        iter_pages = getattr(self._web_source, "iter_pages", None)
        if callable(iter_pages):
            async for note in self._iter_web_candidate_notes_with_hybrid_cursor(
                iter_pages=iter_pages,
            ):
                yield note
            return

        iter_recent = getattr(self._web_source, "iter_recent", None)
        if callable(iter_recent):
            async for note in iter_recent():
                yield note
            return

        notes = await self._web_source.fetch_recent(requested_limit)
        for note in notes:
            yield note

    async def _iter_web_candidate_notes_with_hybrid_cursor(
        self,
        *,
        iter_pages: Callable[..., AsyncIterator[XiaohongshuPageBatch]],
    ) -> AsyncIterator[XiaohongshuNote]:
        seen_note_ids: set[str] = set()
        cursor_fingerprint = self._build_live_cursor_fingerprint()
        saved_cursor = self._load_live_cursor(fingerprint=cursor_fingerprint)

        head_next_cursor = ""
        head_exhausted = False
        async for batch in iter_pages(
            force_head=True,
            max_pages=max(self._HEAD_SHORT_SCAN_PAGES, 1),
        ):
            if batch.next_cursor:
                head_next_cursor = batch.next_cursor.strip()
            if batch.exhausted:
                head_exhausted = True
            for note in batch.notes:
                if note.note_id in seen_note_ids:
                    continue
                seen_note_ids.add(note.note_id)
                yield note

        if head_exhausted:
            return

        resume_cursor = saved_cursor or head_next_cursor
        if not resume_cursor:
            return

        async for batch in iter_pages(start_cursor=resume_cursor):
            page_cursor = batch.request_cursor.strip()
            if page_cursor:
                self._save_live_cursor(
                    cursor=page_cursor,
                    fingerprint=cursor_fingerprint,
                )
            for note in batch.notes:
                if note.note_id in seen_note_ids:
                    continue
                seen_note_ids.add(note.note_id)
                yield note
            if batch.exhausted:
                break

    def _build_live_cursor_fingerprint(self) -> str:
        cfg = self._settings.xiaohongshu.web_readonly
        fingerprint_payload = {
            "request_url": cfg.request_url,
            "request_method": cfg.request_method,
            "request_body": cfg.request_body,
            "request_headers": cfg.request_headers,
            "items_path": cfg.items_path,
            "note_id_field": cfg.note_id_field,
            "title_field": cfg.title_field,
            "source_url_field": cfg.source_url_field,
        }
        normalized = json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def _load_live_cursor(self, *, fingerprint: str) -> str | None:
        saved_fingerprint = self._repository.get_state(
            self._LIVE_CURSOR_FINGERPRINT_STATE_KEY
        )
        if saved_fingerprint != fingerprint:
            return None
        raw_cursor = self._repository.get_state(self._LIVE_CURSOR_STATE_KEY)
        if raw_cursor is None:
            return None
        cursor = raw_cursor.strip()
        if not cursor:
            return None
        return cursor

    def _save_live_cursor(self, *, cursor: str, fingerprint: str) -> None:
        normalized_cursor = cursor.strip()
        if not normalized_cursor:
            return
        self._repository.set_state(
            self._LIVE_CURSOR_FINGERPRINT_STATE_KEY,
            fingerprint,
        )
        self._repository.set_state(
            self._LIVE_CURSOR_STATE_KEY,
            normalized_cursor,
        )

    async def _summarize_video_note(self, note: XiaohongshuNote) -> str:
        transcript = ""
        transcript_error = ""
        try:
            transcript = await self._transcribe_video_note(note)
        except AppError as exc:
            transcript_error = exc.message
        except Exception as exc:
            transcript_error = str(exc)

        if transcript:
            return await self._llm_service.summarize_xiaohongshu_video_note(
                note_id=note.note_id,
                title=note.title,
                content=note.content,
                transcript=transcript,
                source_url=note.source_url,
                image_urls=note.image_urls,
            )

        content = note.content.strip()
        if content:
            summary = await self._llm_service.summarize_xiaohongshu_note(
                note_id=note.note_id,
                title=note.title,
                content=content,
                source_url=note.source_url,
                image_urls=note.image_urls,
            )
            if transcript_error:
                return (
                    f"{summary.rstrip()}\n\n> 注：视频音频转写失败，当前总结仅基于正文。"
                )
            return summary

        raise AppError(
            code=ErrorCode.UPSTREAM_ERROR,
            message=f"视频笔记处理失败：{transcript_error or '无法提取转写与正文'}",
            status_code=502,
        )

    async def _transcribe_video_note(self, note: XiaohongshuNote) -> str:
        base_temp = Path(self._settings.runtime.temp_dir)
        job_dir = base_temp / f"xhs-video-{uuid.uuid4().hex}"
        job_dir.mkdir(parents=True, exist_ok=True)

        headers = self._build_video_download_headers(note.source_url)
        try:
            audio_path = await asyncio.to_thread(
                self._audio_fetcher.fetch_audio,
                note.source_url,
                job_dir,
                headers,
            )
            transcript = await asyncio.to_thread(self._asr_service.transcribe, audio_path)
            return transcript.strip()
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

    def _build_video_download_headers(self, source_url: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        cfg_headers = self._settings.xiaohongshu.web_readonly.request_headers
        for key in ("User-Agent", "Referer", "Origin"):
            value = cfg_headers.get(key)
            if isinstance(value, str) and value.strip():
                headers[key] = value.strip()
        if source_url:
            headers.setdefault("Referer", source_url)

        cookie = self._settings.xiaohongshu.cookie.strip()
        if cookie:
            headers["Cookie"] = cookie
        else:
            fallback_cookie = cfg_headers.get("Cookie")
            if isinstance(fallback_cookie, str) and fallback_cookie.strip():
                headers["Cookie"] = fallback_cookie.strip()
        return headers

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
