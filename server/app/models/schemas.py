from __future__ import annotations

from pydantic import BaseModel, Field


class HealthData(BaseModel):
    status: str = "ok"


class BilibiliSummaryRequest(BaseModel):
    video_url: str = Field(min_length=3, max_length=2000)


class BilibiliSummaryData(BaseModel):
    video_url: str
    summary_markdown: str
    elapsed_ms: int
    transcript_chars: int
