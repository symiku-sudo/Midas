from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import Settings, XiaohongshuConfig, XiaohongshuWebReadonlyConfig
from app.core.errors import AppError, ErrorCode
from app.repositories.xiaohongshu_repo import XiaohongshuSyncRepository
from app.services.xiaohongshu import (
    XiaohongshuNote,
    XiaohongshuPageBatch,
    XiaohongshuSyncService,
    XiaohongshuWebReadonlySource,
)


class AlwaysFailLLM:
    async def summarize_xiaohongshu_note(self, **_: str) -> str:
        raise AppError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="mock llm failed",
            status_code=502,
        )


class FixedSource:
    def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
        data = [
            XiaohongshuNote(
                note_id="n1",
                title="t1",
                content="c1",
                source_url="https://www.xiaohongshu.com/explore/n1",
            ),
            XiaohongshuNote(
                note_id="n2",
                title="t2",
                content="c2",
                source_url="https://www.xiaohongshu.com/explore/n2",
            ),
        ]
        return data[:limit]


class FixedWebSource:
    async def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
        data = [
            XiaohongshuNote(
                note_id="w1",
                title="web-title-1",
                content="web-content-1",
                source_url="https://www.xiaohongshu.com/explore/w1",
            ),
            XiaohongshuNote(
                note_id="w2",
                title="web-title-2",
                content="web-content-2",
                source_url="https://www.xiaohongshu.com/explore/w2",
            ),
        ]
        return data[:limit]


class SimpleLLM:
    async def summarize_xiaohongshu_note(self, **_: str) -> str:
        return "# 总结\n\n这是一段测试总结。"


class CaptureLLM:
    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    async def summarize_xiaohongshu_note(self, **kwargs) -> str:
        self.last_kwargs = kwargs
        return "# 总结\n\n这是一段测试总结。"


class IterWebSource:
    def __init__(self, notes: list[XiaohongshuNote]) -> None:
        self._notes = notes

    async def iter_recent(self):
        for note in self._notes:
            yield note


class SingleUrlWebSource:
    def __init__(self, note: XiaohongshuNote) -> None:
        self._note = note
        self.last_url = ""

    async def fetch_note_by_url(self, note_url: str) -> XiaohongshuNote:
        self.last_url = note_url
        return self._note


class PendingCountWebSource:
    def __init__(self, batches: list[XiaohongshuPageBatch]) -> None:
        self._batches = batches
        self.calls: list[dict[str, object]] = []

    async def iter_pages(
        self,
        *,
        start_cursor: str | None = None,
        force_head: bool = False,
        max_pages: int | None = None,
    ):
        self.calls.append(
            {
                "start_cursor": start_cursor,
                "force_head": force_head,
                "max_pages": max_pages,
            }
        )
        for batch in self._batches:
            yield batch


class HybridCursorWebSource:
    def __init__(
        self,
        *,
        head_notes: list[XiaohongshuNote],
        head_next_cursor: str,
        resume_pages: dict[str, list[XiaohongshuPageBatch]],
        fail_cursors: set[str] | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._head_notes = head_notes
        self._head_next_cursor = head_next_cursor
        self._resume_pages = resume_pages
        self._fail_cursors = fail_cursors or set()

    async def iter_pages(
        self,
        *,
        start_cursor: str | None = None,
        force_head: bool = False,
        max_pages: int | None = None,
    ):
        self.calls.append(
            {
                "start_cursor": start_cursor,
                "force_head": force_head,
                "max_pages": max_pages,
            }
        )
        if force_head:
            yield XiaohongshuPageBatch(
                notes=self._head_notes,
                request_cursor="",
                next_cursor=self._head_next_cursor,
                exhausted=False,
            )
            return
        normalized_cursor = (start_cursor or "").strip()
        if normalized_cursor in self._fail_cursors:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="响应中 items_path 无法解析为列表：data.notes",
                status_code=502,
            )
        for batch in self._resume_pages.get(normalized_cursor, []):
            yield batch


@pytest.mark.asyncio
async def test_sync_circuit_breaker(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            circuit_breaker_failures=2,
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=FixedSource(),
        llm_service=AlwaysFailLLM(),
    )

    with pytest.raises(AppError) as exc_info:
        await service.sync(limit=2)

    err = exc_info.value
    assert err.code == ErrorCode.CIRCUIT_OPEN
    assert err.details["failed_count"] == 2
    assert err.details["circuit_opened"] is True


@pytest.mark.asyncio
async def test_web_readonly_hybrid_scans_head_then_resume_saved_cursor(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    repo.mark_synced("h1", "head-1", "https://www.xiaohongshu.com/explore/h1")
    source = HybridCursorWebSource(
        head_notes=[
            XiaohongshuNote(
                note_id="h1",
                title="head-1",
                content="head-content-1",
                source_url="https://www.xiaohongshu.com/explore/h1",
            )
        ],
        head_next_cursor="head-next",
        resume_pages={
            "resume-cursor": [
                XiaohongshuPageBatch(
                    notes=[
                        XiaohongshuNote(
                            note_id="r1",
                            title="resume-1",
                            content="resume-content-1",
                            source_url="https://www.xiaohongshu.com/explore/r1",
                        )
                    ],
                    request_cursor="resume-cursor",
                    next_cursor="resume-next",
                    exhausted=False,
                ),
                XiaohongshuPageBatch(
                    notes=[
                        XiaohongshuNote(
                            note_id="r2",
                            title="resume-2",
                            content="resume-content-2",
                            source_url="https://www.xiaohongshu.com/explore/r2",
                        )
                    ],
                    request_cursor="resume-next",
                    next_cursor="",
                    exhausted=True,
                ),
            ]
        },
    )
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=source,
        llm_service=SimpleLLM(),
    )
    fingerprint = service._build_live_cursor_fingerprint()
    repo.set_state(service._LIVE_CURSOR_FINGERPRINT_STATE_KEY, fingerprint)
    repo.set_state(service._LIVE_CURSOR_STATE_KEY, "resume-cursor")

    result = await service.sync(limit=2, confirm_live=True)

    assert result.new_count == 2
    assert [item.note_id for item in result.summaries] == ["r1", "r2"]
    assert len(source.calls) == 2
    assert source.calls[0]["force_head"] is True
    assert source.calls[0]["max_pages"] == service._HEAD_SHORT_SCAN_PAGES
    assert source.calls[1]["start_cursor"] == "resume-cursor"
    assert repo.get_state(service._LIVE_CURSOR_STATE_KEY) == "resume-next"


@pytest.mark.asyncio
async def test_web_readonly_hybrid_uses_head_cursor_when_no_saved_cursor(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    repo.mark_synced("h1", "head-1", "https://www.xiaohongshu.com/explore/h1")
    source = HybridCursorWebSource(
        head_notes=[
            XiaohongshuNote(
                note_id="h1",
                title="head-1",
                content="head-content-1",
                source_url="https://www.xiaohongshu.com/explore/h1",
            )
        ],
        head_next_cursor="head-next",
        resume_pages={
            "head-next": [
                XiaohongshuPageBatch(
                    notes=[
                        XiaohongshuNote(
                            note_id="r1",
                            title="resume-1",
                            content="resume-content-1",
                            source_url="https://www.xiaohongshu.com/explore/r1",
                        )
                    ],
                    request_cursor="head-next",
                    next_cursor="",
                    exhausted=True,
                )
            ]
        },
    )
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=source,
        llm_service=SimpleLLM(),
    )

    result = await service.sync(limit=1, confirm_live=True)

    assert result.new_count == 1
    assert [item.note_id for item in result.summaries] == ["r1"]
    assert len(source.calls) == 2
    assert source.calls[1]["start_cursor"] == "head-next"
    assert repo.get_state(service._LIVE_CURSOR_STATE_KEY) == "head-next"


@pytest.mark.asyncio
async def test_web_readonly_hybrid_ignores_stale_cursor_on_fingerprint_change(
    tmp_path,
) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    repo.mark_synced("h1", "head-1", "https://www.xiaohongshu.com/explore/h1")
    source = HybridCursorWebSource(
        head_notes=[
            XiaohongshuNote(
                note_id="h1",
                title="head-1",
                content="head-content-1",
                source_url="https://www.xiaohongshu.com/explore/h1",
            )
        ],
        head_next_cursor="head-next",
        resume_pages={
            "head-next": [
                XiaohongshuPageBatch(
                    notes=[
                        XiaohongshuNote(
                            note_id="r1",
                            title="resume-1",
                            content="resume-content-1",
                            source_url="https://www.xiaohongshu.com/explore/r1",
                        )
                    ],
                    request_cursor="head-next",
                    next_cursor="",
                    exhausted=True,
                )
            ]
        },
    )
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=source,
        llm_service=SimpleLLM(),
    )
    repo.set_state(service._LIVE_CURSOR_FINGERPRINT_STATE_KEY, "stale-fingerprint")
    repo.set_state(service._LIVE_CURSOR_STATE_KEY, "stale-cursor")

    result = await service.sync(limit=1, confirm_live=True)

    assert result.new_count == 1
    assert [item.note_id for item in result.summaries] == ["r1"]
    assert len(source.calls) == 2
    assert source.calls[1]["start_cursor"] == "head-next"


@pytest.mark.asyncio
async def test_web_readonly_hybrid_fallback_to_head_cursor_when_saved_cursor_invalid(
    tmp_path,
) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    repo.mark_synced("h1", "head-1", "https://www.xiaohongshu.com/explore/h1")
    source = HybridCursorWebSource(
        head_notes=[
            XiaohongshuNote(
                note_id="h1",
                title="head-1",
                content="head-content-1",
                source_url="https://www.xiaohongshu.com/explore/h1",
            )
        ],
        head_next_cursor="head-next",
        resume_pages={
            "head-next": [
                XiaohongshuPageBatch(
                    notes=[
                        XiaohongshuNote(
                            note_id="r1",
                            title="resume-1",
                            content="resume-content-1",
                            source_url="https://www.xiaohongshu.com/explore/r1",
                        )
                    ],
                    request_cursor="head-next",
                    next_cursor="",
                    exhausted=True,
                )
            ]
        },
        fail_cursors={"stale-resume"},
    )
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=source,
        llm_service=SimpleLLM(),
    )
    fingerprint = service._build_live_cursor_fingerprint()
    repo.set_state(service._LIVE_CURSOR_FINGERPRINT_STATE_KEY, fingerprint)
    repo.set_state(service._LIVE_CURSOR_STATE_KEY, "stale-resume")

    result = await service.sync(limit=1, confirm_live=True)

    assert result.new_count == 1
    assert [item.note_id for item in result.summaries] == ["r1"]
    assert len(source.calls) == 3
    assert source.calls[1]["start_cursor"] == "stale-resume"
    assert source.calls[2]["start_cursor"] == "head-next"
    assert repo.get_state(service._LIVE_CURSOR_STATE_KEY) == "head-next"


@pytest.mark.asyncio
async def test_sync_failure_does_not_mark_note_as_synced(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            circuit_breaker_failures=10,
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=FixedSource(),
        llm_service=AlwaysFailLLM(),
    )

    result = await service.sync(limit=2)

    assert result.new_count == 0
    assert result.failed_count == 2
    assert repo.is_synced("n1") is False
    assert repo.is_synced("n2") is False


@pytest.mark.asyncio
async def test_web_readonly_requires_confirm_live(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=FixedWebSource(),
    )

    with pytest.raises(AppError) as exc_info:
        await service.sync(limit=1, confirm_live=False)
    assert exc_info.value.code == ErrorCode.INVALID_INPUT


@pytest.mark.asyncio
async def test_web_readonly_rate_limit_guard(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=1800,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    repo.set_state("last_live_sync_ts", str(int(time.time())))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=FixedWebSource(),
    )

    with pytest.raises(AppError) as exc_info:
        await service.sync(limit=1, confirm_live=True)
    assert exc_info.value.code == ErrorCode.RATE_LIMITED


@pytest.mark.asyncio
async def test_web_readonly_success_sets_last_sync_state(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=FixedWebSource(),
        llm_service=SimpleLLM(),
    )

    result = await service.sync(limit=1, confirm_live=True)
    assert result.new_count == 1
    assert result.fetched_count == 1
    assert repo.get_state("last_live_sync_ts") is not None


@pytest.mark.asyncio
async def test_web_readonly_summarize_url_marks_synced(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    note = XiaohongshuNote(
        note_id="u1",
        title="url-note",
        content="来自单篇 URL 的正文",
        source_url="https://www.xiaohongshu.com/explore/u1",
    )
    source = SingleUrlWebSource(note)
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=source,
        llm_service=SimpleLLM(),
    )

    result = await service.summarize_url("https://www.xiaohongshu.com/explore/u1")

    assert result.note_id == "u1"
    assert result.source_url == "https://www.xiaohongshu.com/explore/u1"
    assert source.last_url == "https://www.xiaohongshu.com/explore/u1"
    assert repo.is_synced("u1") is True
    assert "原文链接" in result.summary_markdown


@pytest.mark.asyncio
async def test_web_readonly_pending_count_only_counts_unsynced_note_ids(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    repo.mark_synced("w2", "web-title-2", "https://www.xiaohongshu.com/explore/w2")
    source = PendingCountWebSource(
        batches=[
            XiaohongshuPageBatch(
                notes=[
                    XiaohongshuNote(
                        note_id="w1",
                        title="web-title-1",
                        content="web-content-1",
                        source_url="https://www.xiaohongshu.com/explore/w1",
                    ),
                    XiaohongshuNote(
                        note_id="w2",
                        title="web-title-2",
                        content="web-content-2",
                        source_url="https://www.xiaohongshu.com/explore/w2",
                    ),
                ],
                request_cursor="",
                next_cursor="cursor-2",
                exhausted=False,
            ),
            XiaohongshuPageBatch(
                notes=[
                    XiaohongshuNote(
                        note_id="w2",
                        title="web-title-2",
                        content="web-content-2",
                        source_url="https://www.xiaohongshu.com/explore/w2",
                    ),
                    XiaohongshuNote(
                        note_id="w3",
                        title="web-title-3",
                        content="web-content-3",
                        source_url="https://www.xiaohongshu.com/explore/w3",
                    ),
                ],
                request_cursor="cursor-2",
                next_cursor="",
                exhausted=True,
            ),
        ]
    )
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=source,
        llm_service=SimpleLLM(),
    )

    result = await service.get_pending_unsynced_count()

    assert result["mode"] == "web_readonly"
    assert result["scanned_count"] == 3
    assert result["pending_count"] == 2
    assert len(source.calls) == 1
    assert source.calls[0]["force_head"] is True


@pytest.mark.asyncio
async def test_web_readonly_skip_does_not_consume_requested_limit(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    repo.mark_synced("w1", "old-1", "https://www.xiaohongshu.com/explore/w1")
    repo.mark_synced("w2", "old-2", "https://www.xiaohongshu.com/explore/w2")
    source = IterWebSource(
        [
            XiaohongshuNote(
                note_id="w1",
                title="web-title-1",
                content="web-content-1",
                source_url="https://www.xiaohongshu.com/explore/w1",
            ),
            XiaohongshuNote(
                note_id="w2",
                title="web-title-2",
                content="web-content-2",
                source_url="https://www.xiaohongshu.com/explore/w2",
            ),
            XiaohongshuNote(
                note_id="w3",
                title="web-title-3",
                content="web-content-3",
                source_url="https://www.xiaohongshu.com/explore/w3",
            ),
            XiaohongshuNote(
                note_id="w4",
                title="web-title-4",
                content="web-content-4",
                source_url="https://www.xiaohongshu.com/explore/w4",
            ),
            XiaohongshuNote(
                note_id="w5",
                title="web-title-5",
                content="web-content-5",
                source_url="https://www.xiaohongshu.com/explore/w5",
            ),
        ]
    )
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=source,
        llm_service=SimpleLLM(),
    )

    result = await service.sync(limit=2, confirm_live=True)

    assert result.requested_limit == 2
    assert result.new_count == 2
    assert result.skipped_count == 2
    assert result.fetched_count == 4
    assert [item.note_id for item in result.summaries] == ["w3", "w4"]
    assert repo.is_synced("w5") is False


@pytest.mark.asyncio
async def test_web_readonly_stops_when_all_note_ids_are_already_synced(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    notes = [
        XiaohongshuNote(
            note_id="w1",
            title="web-title-1",
            content="web-content-1",
            source_url="https://www.xiaohongshu.com/explore/w1",
        ),
        XiaohongshuNote(
            note_id="w2",
            title="web-title-2",
            content="web-content-2",
            source_url="https://www.xiaohongshu.com/explore/w2",
        ),
        XiaohongshuNote(
            note_id="w3",
            title="web-title-3",
            content="web-content-3",
            source_url="https://www.xiaohongshu.com/explore/w3",
        ),
    ]
    for note in notes:
        repo.mark_synced(note.note_id, note.title, note.source_url)

    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=IterWebSource(notes),
        llm_service=SimpleLLM(),
    )

    result = await service.sync(limit=2, confirm_live=True)

    assert result.requested_limit == 2
    assert result.new_count == 0
    assert result.skipped_count == 3
    assert result.fetched_count == 3
    assert result.failed_count == 0
    assert result.summaries == []


@pytest.mark.asyncio
async def test_sync_result_markdown_contains_source_url(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=FixedSource(),
        llm_service=SimpleLLM(),
    )

    result = await service.sync(limit=1)
    assert len(result.summaries) == 1
    assert "https://www.xiaohongshu.com/explore/n1" in result.summaries[0].summary_markdown
    assert "原文链接" in result.summaries[0].summary_markdown


@pytest.mark.asyncio
async def test_sync_passes_image_urls_to_llm(tmp_path) -> None:
    class _ImageSource:
        def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
            return [
                XiaohongshuNote(
                    note_id="n1",
                    title="t1",
                    content="c1",
                    source_url="https://www.xiaohongshu.com/explore/n1",
                    image_urls=["https://sns-webpic-qc.xhscdn.com/abc/image-1"],
                )
            ][:limit]

    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    llm = CaptureLLM()
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=_ImageSource(),
        llm_service=llm,
    )

    result = await service.sync(limit=1)
    assert result.new_count == 1
    assert llm.last_kwargs is not None
    assert llm.last_kwargs["image_urls"] == [
        "https://sns-webpic-qc.xhscdn.com/abc/image-1"
    ]


@pytest.mark.asyncio
async def test_sync_video_note_uses_audio_asr_and_llm(tmp_path) -> None:
    class _VideoSource:
        def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
            return [
                XiaohongshuNote(
                    note_id="v1",
                    title="视频笔记标题",
                    content="这是原笔记正文",
                    source_url="https://www.xiaohongshu.com/explore/v1",
                    is_video=True,
                )
            ][:limit]

    class _VideoLLM:
        def __init__(self) -> None:
            self.video_kwargs: dict | None = None
            self.text_called = False

        async def summarize_xiaohongshu_note(self, **kwargs) -> str:
            self.text_called = True
            return "SHOULD_NOT_BE_CALLED"

        async def summarize_xiaohongshu_video_note(self, **kwargs) -> str:
            self.video_kwargs = kwargs
            return "# 视频总结\n\n- 结论 A"

    class _DummyFetcher:
        def __init__(self) -> None:
            self.last_headers: dict[str, str] | None = None

        def fetch_audio(
            self,
            video_url: str,
            output_dir,
            headers: dict[str, str] | None = None,
        ):
            self.last_headers = headers
            audio_path = output_dir / "source.wav"
            audio_path.write_bytes(b"dummy-audio")
            return audio_path

    class _DummyASR:
        def transcribe(self, audio_path) -> str:
            return "这是视频转写文本。"

    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    llm = _VideoLLM()
    fetcher = _DummyFetcher()
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=_VideoSource(),
        llm_service=llm,
        audio_fetcher=fetcher,
        asr_service=_DummyASR(),
    )

    result = await service.sync(limit=1)
    assert result.new_count == 1
    assert llm.video_kwargs is not None
    assert llm.video_kwargs["transcript"] == "这是视频转写文本。"
    assert llm.video_kwargs["content"] == "这是原笔记正文"
    assert llm.text_called is False
    assert fetcher.last_headers is not None
    assert fetcher.last_headers.get("Referer") == "https://www.xiaohongshu.com/explore/v1"
    assert "原文链接" in result.summaries[0].summary_markdown
    assert "https://www.xiaohongshu.com/explore/v1" in result.summaries[0].summary_markdown


@pytest.mark.asyncio
async def test_web_readonly_rejects_title_only_content(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="display_title",
                content_field_candidates=["display_title", "desc"],
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "data": {
                    "notes": [
                        {
                            "note_id": "n1",
                            "display_title": "只有标题",
                            "desc": "只有标题",
                        }
                    ]
                }
            }

    class _FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **_):
            return _FakeResp()

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    with pytest.raises(AppError) as exc_info:
        await source.fetch_recent(limit=1)
    assert exc_info.value.code == ErrorCode.UPSTREAM_ERROR
    assert "未提取到可用正文" in exc_info.value.message


@pytest.mark.asyncio
async def test_web_readonly_auto_fallback_to_playwright_on_http_406(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                page_fetch_driver="auto",
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="title",
                content_field_candidates=["desc"],
                detail_fetch_mode="never",
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)
    calls: dict[str, int] = {"http": 0, "playwright": 0}

    async def _fake_iter_pages_http(self, **_kwargs):
        calls["http"] += 1
        raise AppError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="小红书请求失败（HTTP 406）。",
            status_code=502,
            details={"status_code": 406},
        )
        yield XiaohongshuPageBatch(notes=[])

    async def _fake_iter_pages_playwright(self, **_kwargs):
        calls["playwright"] += 1
        yield XiaohongshuPageBatch(
            notes=[
                XiaohongshuNote(
                    note_id="p1",
                    title="playwright-1",
                    content="正文1",
                    source_url="https://www.xiaohongshu.com/explore/p1",
                )
            ],
            request_cursor="cursor-1",
            next_cursor="",
            exhausted=True,
        )

    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_iter_pages_http",
        _fake_iter_pages_http,
    )
    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_iter_pages_playwright",
        _fake_iter_pages_playwright,
    )

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].note_id == "p1"
    assert calls["http"] == 1
    assert calls["playwright"] == 1


@pytest.mark.asyncio
async def test_web_readonly_http_driver_does_not_fallback_to_playwright(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                page_fetch_driver="http",
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="title",
                content_field_candidates=["desc"],
                detail_fetch_mode="never",
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)
    calls: dict[str, int] = {"http": 0, "playwright": 0}

    async def _fake_iter_pages_http(self, **_kwargs):
        calls["http"] += 1
        raise AppError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="小红书请求失败（HTTP 406）。",
            status_code=502,
            details={"status_code": 406},
        )
        yield XiaohongshuPageBatch(notes=[])

    async def _fake_iter_pages_playwright(self, **_kwargs):
        calls["playwright"] += 1
        yield XiaohongshuPageBatch(notes=[], exhausted=True)

    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_iter_pages_http",
        _fake_iter_pages_http,
    )
    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_iter_pages_playwright",
        _fake_iter_pages_playwright,
    )

    with pytest.raises(AppError) as exc_info:
        await source.fetch_recent(limit=1)
    assert exc_info.value.code == ErrorCode.UPSTREAM_ERROR
    assert calls["http"] == 1
    assert calls["playwright"] == 0


@pytest.mark.asyncio
async def test_web_readonly_playwright_driver_skips_http_path(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                page_fetch_driver="playwright",
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="title",
                content_field_candidates=["desc"],
                detail_fetch_mode="never",
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)
    calls: dict[str, int] = {"http": 0, "playwright": 0}

    async def _fake_iter_pages_http(self, **_kwargs):
        calls["http"] += 1
        yield XiaohongshuPageBatch(notes=[], exhausted=True)

    async def _fake_iter_pages_playwright(self, **_kwargs):
        calls["playwright"] += 1
        yield XiaohongshuPageBatch(
            notes=[
                XiaohongshuNote(
                    note_id="p2",
                    title="playwright-2",
                    content="正文2",
                    source_url="https://www.xiaohongshu.com/explore/p2",
                )
            ],
            request_cursor="cursor-2",
            next_cursor="",
            exhausted=True,
        )

    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_iter_pages_http",
        _fake_iter_pages_http,
    )
    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_iter_pages_playwright",
        _fake_iter_pages_playwright,
    )

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].note_id == "p2"
    assert calls["playwright"] == 1
    assert calls["http"] == 0


@pytest.mark.asyncio
async def test_web_readonly_business_auth_expired_maps_to_auth_error(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="display_title",
                content_field_candidates=["display_title", "desc"],
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {"code": -100, "success": False, "msg": "登录已过期", "data": {}}

    class _FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **_):
            return _FakeResp()

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    with pytest.raises(AppError) as exc_info:
        await source.fetch_recent(limit=1)
    assert exc_info.value.code == ErrorCode.AUTH_EXPIRED


@pytest.mark.asyncio
async def test_web_readonly_page_fallback_extracts_content_and_images(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="display_title",
                content_field_candidates=["display_title", "desc"],
                max_images_per_note=3,
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        def __init__(self, payload: dict | None = None, text: str = "", status_code: int = 200) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self) -> dict:
            return self._payload

    class _FakeClient:
        calls: list[str] = []

        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **kwargs):
            url = kwargs["url"]
            self.calls.append(url)
            if "collect/page" in url:
                return _FakeResp(
                    {
                        "data": {
                            "notes": [
                                {
                                    "note_id": "n2",
                                    "display_title": "列表标题",
                                    "desc": "列表标题",
                                    "xsec_token": "token-2",
                                }
                            ]
                        }
                    }
                )
            html = """
            <html><body>
            <script>
            window.__INITIAL_STATE__ = {"note":{"noteDetailMap":{"n2":{"note":{"noteId":"n2","title":"页面标题","desc":"页面正文","type":"normal","imageList":[{"urlDefault":"https://sns-webpic-qc.xhscdn.com/page-1"}]}}}}};
            </script>
            </body></html>
            """
            return _FakeResp(text=html)

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].title == "页面标题"
    assert notes[0].content == "页面正文"
    assert notes[0].image_urls == ["https://sns-webpic-qc.xhscdn.com/page-1"]
    assert len(_FakeClient.calls) == 2
    assert any("/explore/n2" in url for url in _FakeClient.calls)


@pytest.mark.asyncio
async def test_web_readonly_detail_fetch_extracts_content_and_images(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="display_title",
                content_field_candidates=["display_title", "desc"],
                image_field_candidates=["cover.url_pre"],
                detail_fetch_mode="always",
                detail_request_url_template=(
                    "https://edith.xiaohongshu.com/api/sns/web/v1/note/detail?"
                    "note_id={note_id}&xsec_token={xsec_token}"
                ),
                detail_content_field_candidates=["data.items.0.note_card.desc"],
                detail_image_field_candidates=["data.items.0.note_card.image_list"],
                max_images_per_note=3,
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        def __init__(
            self, payload: dict | None = None, text: str = "", status_code: int = 200
        ) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self) -> dict:
            return self._payload

    class _FakeClient:
        calls: list[str] = []

        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **kwargs):
            url = kwargs["url"]
            self.calls.append(url)
            if "collect/page" in url:
                return _FakeResp(
                    {
                        "data": {
                            "notes": [
                                {
                                    "note_id": "n1",
                                    "display_title": "只有标题",
                                    "desc": "只有标题",
                                    "xsec_token": "token-1",
                                    "cover": {"url_pre": "https://sns-webpic-qc.xhscdn.com/cover-1"},
                                }
                            ]
                        }
                    }
                )
            if "/explore/" in url:
                return _FakeResp(status_code=404)
            return _FakeResp(
                {
                    "data": {
                        "items": [
                            {
                                "note_card": {
                                    "desc": "这是详情正文",
                                    "image_list": [
                                        {"url_default": "https://sns-webpic-qc.xhscdn.com/detail-1"},
                                        {"url_default": "https://sns-webpic-qc.xhscdn.com/detail-2"},
                                    ],
                                }
                            }
                        ]
                    }
                }
            )

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].content == "这是详情正文"
    assert notes[0].image_urls == [
        "https://sns-webpic-qc.xhscdn.com/detail-1",
        "https://sns-webpic-qc.xhscdn.com/detail-2",
        "https://sns-webpic-qc.xhscdn.com/cover-1",
    ]
    assert len(_FakeClient.calls) == 3
    assert any("/explore/n1" in url for url in _FakeClient.calls)
    assert any("/note/detail?" in url for url in _FakeClient.calls)


@pytest.mark.asyncio
async def test_web_readonly_paginate_until_limit(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url=(
                    "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page?num=2&cursor="
                ),
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="title",
                content_field_candidates=["desc"],
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        def __init__(
            self, payload: dict | None = None, text: str = "", status_code: int = 200
        ) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self) -> dict:
            return self._payload

    class _FakeClient:
        list_urls: list[str] = []

        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **kwargs):
            url = kwargs["url"]
            if "collect/page" in url:
                self.list_urls.append(url)
                cursor = parse_qs(urlparse(url).query).get("cursor", [""])[0]
                if cursor == "":
                    return _FakeResp(
                        {
                            "data": {
                                "notes": [
                                    {
                                        "note_id": "n1",
                                        "title": "标题1",
                                        "desc": "正文1",
                                    },
                                    {
                                        "note_id": "n2",
                                        "title": "标题2",
                                        "desc": "正文2",
                                    },
                                ],
                                "has_more": True,
                                "cursor": "cursor-page-2",
                            }
                        }
                    )
                if cursor == "cursor-page-2":
                    return _FakeResp(
                        {
                            "data": {
                                "notes": [
                                    {
                                        "note_id": "n3",
                                        "title": "标题3",
                                        "desc": "正文3",
                                    },
                                    {
                                        "note_id": "n4",
                                        "title": "标题4",
                                        "desc": "正文4",
                                    },
                                ],
                                "has_more": False,
                                "cursor": "cursor-page-3",
                            }
                        }
                    )
                return _FakeResp({"data": {"notes": [], "has_more": False}})

            # Note page fallback can safely fail in this case.
            if "/explore/" in url:
                return _FakeResp(status_code=404)
            return _FakeResp({"data": {"notes": [], "has_more": False}})

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    notes = await source.fetch_recent(limit=3)
    assert [item.note_id for item in notes] == ["n1", "n2", "n3"]
    assert len(_FakeClient.list_urls) == 2
    assert "cursor=cursor-page-2" in _FakeClient.list_urls[1]


@pytest.mark.asyncio
async def test_web_readonly_video_note_kept_without_content(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="display_title",
                content_field_candidates=["desc"],
                detail_fetch_mode="never",
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "data": {
                    "notes": [
                        {
                            "note_id": "v100",
                            "display_title": "这是个视频",
                            "type": "video",
                        }
                    ]
                }
            }

    class _FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **_):
            return _FakeResp()

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].note_id == "v100"
    assert notes[0].is_video is True
    assert notes[0].content == ""


@pytest.mark.asyncio
async def test_web_readonly_fallback_items_path_and_note_card_shape(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="title",
                content_field_candidates=["desc"],
                detail_fetch_mode="never",
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "data": {
                    "items": [
                        {
                            "xsec_token": "token-1",
                            "note_card": {
                                "note_id": "n100",
                                "title": "回退路径标题",
                                "desc": "回退路径正文",
                                "image_list": [
                                    {
                                        "url_default": "https://sns-webpic-qc.xhscdn.com/fallback-1"
                                    }
                                ],
                            },
                        }
                    ],
                    "has_more": False,
                }
            }

    class _FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **_):
            return _FakeResp()

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].note_id == "n100"
    assert notes[0].title == "回退路径标题"
    assert notes[0].content == "回退路径正文"
    assert notes[0].image_urls == ["https://sns-webpic-qc.xhscdn.com/fallback-1"]


def test_live_sync_cooldown_allowed_when_no_history(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=1800,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        llm_service=SimpleLLM(),
    )

    cooldown = service.get_live_sync_cooldown()
    assert cooldown["mode"] == "web_readonly"
    assert cooldown["allowed"] is True
    assert cooldown["remaining_seconds"] == 0
    assert cooldown["next_allowed_at_epoch"] == 0
    assert cooldown["last_sync_at_epoch"] == 0
    assert cooldown["min_interval_seconds"] == 1800


def test_live_sync_cooldown_reports_remaining_seconds(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=60,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        llm_service=SimpleLLM(),
    )
    now = int(time.time())
    repo.set_state("last_live_sync_ts", str(now - 7))

    cooldown = service.get_live_sync_cooldown()
    assert cooldown["mode"] == "web_readonly"
    assert cooldown["allowed"] is False
    # allow tiny timing drift in CI
    assert 52 <= int(cooldown["remaining_seconds"]) <= 53
    assert int(cooldown["last_sync_at_epoch"]) == now - 7
    assert now + 52 <= int(cooldown["next_allowed_at_epoch"]) <= now + 53
