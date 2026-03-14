from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.core.errors import AppError, ErrorCode
from app.core.config import get_settings
from app.models.schemas import BilibiliSummaryData, XiaohongshuSummaryItem, XiaohongshuSyncData
from app.services.async_jobs import AsyncJobService


async def _wait_for_terminal_status(
    service: AsyncJobService, job_id: str, *, timeout_seconds: float = 3.0
) -> str:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        status = await service.get_job(job_id)
        if status.status in {"SUCCEEDED", "FAILED", "INTERRUPTED"}:
            return status.status
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"Timed out waiting for job {job_id}")
        await asyncio.sleep(0.005)


async def _wait_for_status(
    service: AsyncJobService,
    job_id: str,
    *,
    predicate,
    timeout_seconds: float = 3.0,
):
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        status = await service.get_job(job_id)
        if predicate(status):
            return status
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"Timed out waiting for expected state on job {job_id}")
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_async_job_service_runs_bilibili_job_and_persists_result(tmp_path: Path) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.runtime.temp_dir = str(tmp_path)

    async def fake_bilibili_runner(video_url: str) -> BilibiliSummaryData:
        await asyncio.sleep(0.05)
        return BilibiliSummaryData(
            video_url=video_url,
            summary_markdown="# done",
            elapsed_ms=12,
            transcript_chars=34,
        )

    async def fake_xhs_runner(url: str) -> XiaohongshuSummaryItem:
        return XiaohongshuSummaryItem(
            note_id="xhs-1",
            title="mock",
            source_url=url,
            summary_markdown="ok",
        )

    async def fake_xhs_sync_runner(limit, confirm_live, progress_callback) -> XiaohongshuSyncData:
        return XiaohongshuSyncData(
            requested_limit=limit or 2,
            fetched_count=2,
            new_count=2,
            skipped_count=0,
            failed_count=0,
            circuit_opened=False,
            summaries=[],
        )

    service = AsyncJobService(
        settings,
        bilibili_runner=fake_bilibili_runner,
        xiaohongshu_runner=fake_xhs_runner,
        xiaohongshu_sync_runner=fake_xhs_sync_runner,
    )
    await service.start()
    try:
        created = await service.create_bilibili_summary_job(
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
            request_id="req-1",
        )
        assert created.status == "PENDING"

        terminal = await _wait_for_terminal_status(service, created.job_id)
        assert terminal == "SUCCEEDED"

        status = await service.get_job(created.job_id)
        assert status.result is not None
        assert status.result["video_url"].endswith("BV1xx411c7mD")
        assert status.result["transcript_chars"] == 34

        listing = await service.list_jobs(limit=10)
        assert listing.total == 1
        assert listing.items[0].job_id == created.job_id

        store_path = tmp_path / "async_jobs.json"
        assert store_path.exists()
        payload = json.loads(store_path.read_text(encoding="utf-8"))
        assert payload["jobs"][0]["status"] == "SUCCEEDED"
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_async_job_service_marks_running_jobs_interrupted_on_restart(
    tmp_path: Path,
) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.runtime.temp_dir = str(tmp_path)
    store_path = tmp_path / "async_jobs.json"
    store_path.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_id": "job-running",
                        "job_type": "bilibili_summarize",
                        "status": "RUNNING",
                        "message": "任务执行中。",
                        "submitted_at": "2026-03-12 12:00:00",
                        "started_at": "2026-03-12 12:00:01",
                        "finished_at": "",
                        "request_payload": {
                            "video_url": "https://www.bilibili.com/video/BV1xx411c7mD"
                        },
                        "request_id": "req-old",
                        "result": None,
                        "error": None,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    async def fake_bilibili_runner(video_url: str) -> BilibiliSummaryData:
        return BilibiliSummaryData(
            video_url=video_url,
            summary_markdown="# done",
            elapsed_ms=12,
            transcript_chars=34,
        )

    async def fake_xhs_runner(url: str) -> XiaohongshuSummaryItem:
        return XiaohongshuSummaryItem(
            note_id="xhs-1",
            title="mock",
            source_url=url,
            summary_markdown="ok",
        )

    async def fake_xhs_sync_runner(limit, confirm_live, progress_callback) -> XiaohongshuSyncData:
        return XiaohongshuSyncData(
            requested_limit=limit or 1,
            fetched_count=1,
            new_count=1,
            skipped_count=0,
            failed_count=0,
            circuit_opened=False,
            summaries=[],
        )

    service = AsyncJobService(
        settings,
        bilibili_runner=fake_bilibili_runner,
        xiaohongshu_runner=fake_xhs_runner,
        xiaohongshu_sync_runner=fake_xhs_sync_runner,
    )
    await service.start()
    try:
        status = await service.get_job("job-running")
        assert status.status == "INTERRUPTED"
        assert status.error is not None
        assert status.error.message == "服务重启导致任务中断。"
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_async_job_service_retries_failed_job_with_same_payload(tmp_path: Path) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.runtime.temp_dir = str(tmp_path)
    bilibili_calls = 0

    async def fake_bilibili_runner(video_url: str) -> BilibiliSummaryData:
        nonlocal bilibili_calls
        bilibili_calls += 1
        await asyncio.sleep(0.05)
        if bilibili_calls == 1:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="上游暂时不可用。",
                status_code=502,
            )
        return BilibiliSummaryData(
            video_url=video_url,
            summary_markdown="# retry ok",
            elapsed_ms=22,
            transcript_chars=55,
        )

    async def fake_xhs_runner(url: str) -> XiaohongshuSummaryItem:
        return XiaohongshuSummaryItem(
            note_id="xhs-1",
            title="mock",
            source_url=url,
            summary_markdown="ok",
        )

    async def fake_xhs_sync_runner(limit, confirm_live, progress_callback) -> XiaohongshuSyncData:
        return XiaohongshuSyncData(
            requested_limit=limit or 1,
            fetched_count=1,
            new_count=1,
            skipped_count=0,
            failed_count=0,
            circuit_opened=False,
            summaries=[],
        )

    service = AsyncJobService(
        settings,
        bilibili_runner=fake_bilibili_runner,
        xiaohongshu_runner=fake_xhs_runner,
        xiaohongshu_sync_runner=fake_xhs_sync_runner,
    )
    await service.start()
    try:
        first = await service.create_bilibili_summary_job(
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
            request_id="req-first",
        )
        assert await _wait_for_terminal_status(service, first.job_id) == "FAILED"

        retried = await service.retry_job(first.job_id, request_id="req-retry")
        assert retried.retry_of_job_id == first.job_id
        assert await _wait_for_terminal_status(service, retried.job_id) == "SUCCEEDED"

        retried_status = await service.get_job(retried.job_id)
        assert retried_status.retry_of_job_id == first.job_id
        assert retried_status.request_payload["video_url"].endswith("BV1xx411c7mD")
        assert retried_status.result is not None
        assert retried_status.result["summary_markdown"] == "# retry ok"
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_async_job_service_tracks_xiaohongshu_sync_progress_and_completion(
    tmp_path: Path,
) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.runtime.temp_dir = str(tmp_path)

    async def fake_bilibili_runner(video_url: str) -> BilibiliSummaryData:
        return BilibiliSummaryData(
            video_url=video_url,
            summary_markdown="# done",
            elapsed_ms=12,
            transcript_chars=34,
        )

    async def fake_xhs_runner(url: str) -> XiaohongshuSummaryItem:
        return XiaohongshuSummaryItem(
            note_id="xhs-1",
            title="mock",
            source_url=url,
            summary_markdown="ok",
        )

    async def fake_xhs_sync_runner(limit, confirm_live, progress_callback) -> XiaohongshuSyncData:
        assert limit == 2
        assert confirm_live is True
        assert progress_callback is not None
        await progress_callback(
            {
                "current": 1,
                "total": 2,
                "message": "已完成有效同步：1/2（note-1）",
                "summaries": [
                    {
                        "note_id": "note-1",
                        "title": "第一条",
                        "source_url": "https://www.xiaohongshu.com/explore/note-1",
                        "summary_markdown": "# 1",
                    }
                ],
            }
        )
        await asyncio.sleep(0.25)
        return XiaohongshuSyncData(
            requested_limit=2,
            fetched_count=3,
            new_count=2,
            skipped_count=1,
            failed_count=0,
            circuit_opened=False,
            summaries=[
                XiaohongshuSummaryItem(
                    note_id="note-1",
                    title="第一条",
                    source_url="https://www.xiaohongshu.com/explore/note-1",
                    summary_markdown="# 1",
                ),
                XiaohongshuSummaryItem(
                    note_id="note-2",
                    title="第二条",
                    source_url="https://www.xiaohongshu.com/explore/note-2",
                    summary_markdown="# 2",
                ),
            ],
        )

    service = AsyncJobService(
        settings,
        bilibili_runner=fake_bilibili_runner,
        xiaohongshu_runner=fake_xhs_runner,
        xiaohongshu_sync_runner=fake_xhs_sync_runner,
    )
    await service.start()
    try:
        created = await service.create_xiaohongshu_sync_job(
            limit=2,
            confirm_live=True,
            request_id="req-sync",
        )
        assert created.job_type == "xiaohongshu_sync"
        assert created.progress_total == 2

        interim = await _wait_for_status(
            service,
            created.job_id,
            predicate=lambda status: (
                status.status == "RUNNING"
                and status.progress is not None
                and status.progress.current >= 1
                and status.result is not None
                and len(status.result.get("summaries", [])) == 1
            ),
        )
        assert interim.progress is not None
        assert interim.progress.current >= 1
        assert interim.progress.total == 2
        assert interim.result is not None
        assert len(interim.result["summaries"]) == 1

        terminal = await _wait_for_terminal_status(service, created.job_id)
        assert terminal == "SUCCEEDED"

        status = await service.get_job(created.job_id)
        assert status.progress is not None
        assert status.progress.current == 2
        assert status.progress.total == 2
        assert status.result is not None
        assert status.result["new_count"] == 2
        assert len(status.result["summaries"]) == 2
    finally:
        await service.stop()
