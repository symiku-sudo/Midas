from __future__ import annotations

import pytest

from app.models.schemas import XiaohongshuSummaryItem, XiaohongshuSyncData
from app.services.xiaohongshu_job import XiaohongshuSyncJobManager


def _build_sync_result(note_id: str) -> XiaohongshuSyncData:
    summary = XiaohongshuSummaryItem(
        note_id=note_id,
        title=f"title-{note_id}",
        source_url=f"https://www.xiaohongshu.com/explore/{note_id}",
        summary_markdown="# 总结",
    )
    return XiaohongshuSyncData(
        requested_limit=1,
        fetched_count=1,
        new_count=1,
        skipped_count=0,
        failed_count=0,
        circuit_opened=False,
        summaries=[summary],
    )


@pytest.mark.asyncio
async def test_manager_compacts_result_summaries_for_completed_job() -> None:
    manager = XiaohongshuSyncJobManager(max_jobs=20, completed_ttl_seconds=600)
    job = await manager.create_job(requested_limit=1)

    await manager.set_success(job.job_id, result=_build_sync_result("n1"))
    state = await manager.get_job(job.job_id)

    assert state is not None
    assert len(state.summaries) == 1
    assert state.result is not None
    assert state.result.new_count == 1
    # Completed state should keep one copy in `state.summaries`.
    assert state.result.summaries == []


@pytest.mark.asyncio
async def test_manager_evicts_old_completed_jobs_when_exceeding_capacity() -> None:
    manager = XiaohongshuSyncJobManager(max_jobs=2, completed_ttl_seconds=600)

    first = await manager.create_job(requested_limit=1)
    await manager.set_success(first.job_id, result=_build_sync_result("n1"))

    second = await manager.create_job(requested_limit=1)
    await manager.set_failed(second.job_id, code="UPSTREAM_ERROR", message="failed")

    third = await manager.create_job(requested_limit=1)

    assert await manager.get_job(first.job_id) is None
    assert await manager.get_job(second.job_id) is not None
    assert await manager.get_job(third.job_id) is not None
