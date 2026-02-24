from __future__ import annotations

import time

import pytest

from app.core.config import Settings, XiaohongshuConfig, XiaohongshuWebReadonlyConfig
from app.core.errors import AppError, ErrorCode
from app.repositories.xiaohongshu_repo import XiaohongshuSyncRepository
from app.services.xiaohongshu import XiaohongshuNote, XiaohongshuSyncService


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
    )

    result = await service.sync(limit=1, confirm_live=True)
    assert result.new_count == 1
    assert result.fetched_count == 1
    assert repo.get_state("last_live_sync_ts") is not None
