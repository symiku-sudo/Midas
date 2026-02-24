from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.response import success_response
from app.models.schemas import BilibiliSummaryRequest, HealthData
from app.services.bilibili import BilibiliSummarizer

router = APIRouter()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_summarizer() -> BilibiliSummarizer:
    settings = get_settings()
    return BilibiliSummarizer(settings)


@router.get("/health")
async def health(request: Request) -> dict:
    data = HealthData().model_dump()
    return success_response(data=data, request_id=request.state.request_id)


@router.post("/api/bilibili/summarize")
async def bilibili_summarize(payload: BilibiliSummaryRequest, request: Request) -> dict:
    logger.info("Receive summarize request: %s", payload.video_url)
    summarizer = _get_summarizer()
    result = await summarizer.summarize(payload.video_url)
    return success_response(data=result.model_dump(), request_id=request.state.request_id)
