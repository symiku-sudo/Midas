from __future__ import annotations

import pytest

from app.core.config import Settings, XiaohongshuConfig
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
