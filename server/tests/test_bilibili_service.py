from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.bilibili import BilibiliSummarizer
from app.services.comment_insights import CommentSnippet
from app.services.bilibili import _normalize_bilibili_video_url


def test_normalize_bvid_to_full_url() -> None:
    assert _normalize_bilibili_video_url("BV1xx411c7mD") == (
        "https://www.bilibili.com/video/BV1xx411c7mD"
    )


def test_normalize_bvid_with_spaces_and_lowercase_prefix() -> None:
    assert _normalize_bilibili_video_url("  bv1xx411c7mD  ") == (
        "https://www.bilibili.com/video/BV1xx411c7mD"
    )


def test_normalize_non_bvid_input_keeps_original_text_except_trim() -> None:
    assert _normalize_bilibili_video_url("  https://www.bilibili.com/video/BV1xx411c7mD  ") == (
        "https://www.bilibili.com/video/BV1xx411c7mD"
    )


def test_extract_bvid_from_url_and_text() -> None:
    summarizer = BilibiliSummarizer(Settings())
    assert (
        summarizer._extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD?p=1")
        == "BV1xx411c7mD"
    )
    assert summarizer._extract_bvid("看看这个 bv1xx411c7mD") == "BV1xx411c7mD"


@pytest.mark.asyncio
async def test_append_comment_insights_adds_weighted_section(monkeypatch) -> None:
    summarizer = BilibiliSummarizer(
        Settings(
            llm={"enabled": False},
            comment_insights={"enabled": True},
        )
    )

    async def _fake_fetch(_video_url: str) -> list[CommentSnippet]:
        return [
            CommentSnippet(text="这条内容很实用，已经收藏。", like_count=25),
            CommentSnippet(text="有帮助，但有些观点偏片面。", like_count=9),
        ]

    monkeypatch.setattr(summarizer, "_fetch_comment_snippets", _fake_fetch)
    output = await summarizer._append_comment_insights(
        summary_markdown="# 标题\n\n原始摘要内容。",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
    )

    assert "## 评论区洞察（含点赞权重）" in output
    assert "### 公众态度" in output
    assert "### 高赞分析" in output
    assert "👍25" in output
