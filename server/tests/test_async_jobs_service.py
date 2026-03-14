from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.core.errors import AppError, ErrorCode
from app.core.config import get_settings
from app.models.schemas import BilibiliSummaryData, XiaohongshuSummaryItem
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
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_async_job_service_runs_bilibili_job_and_persists_result(tmp_path: Path) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.runtime.temp_dir = str(tmp_path)

    async def fake_bilibili_runner(video_url: str) -> BilibiliSummaryData:
        await asyncio.sleep(0.01)
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

    service = AsyncJobService(
        settings,
        bilibili_runner=fake_bilibili_runner,
        xiaohongshu_runner=fake_xhs_runner,
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

    service = AsyncJobService(
        settings,
        bilibili_runner=fake_bilibili_runner,
        xiaohongshu_runner=fake_xhs_runner,
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
        await asyncio.sleep(0.01)
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

    service = AsyncJobService(
        settings,
        bilibili_runner=fake_bilibili_runner,
        xiaohongshu_runner=fake_xhs_runner,
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
