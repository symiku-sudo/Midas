from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.comment_insights import CommentInsightService, CommentSnippet


@pytest.mark.asyncio
async def test_build_insight_section_uses_like_weight_and_highlights() -> None:
    service = CommentInsightService(
        Settings(
            llm={"enabled": False},
            comment_insights={
                "enabled": True,
                "max_highlight_items": 2,
                "max_comments_for_summary": 5,
            },
        )
    )

    section = await service.build_insight_section(
        platform="bilibili",
        source_title="示例标题",
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        comments=[
            CommentSnippet(text="这条真的很实用，马上能落地。", like_count=33),
            CommentSnippet(text="一般般，有点营销味。", like_count=4),
            CommentSnippet(text="受用，讲得很清晰。", like_count=12),
        ],
    )

    assert "## 评论区洞察（含点赞权重）" in section
    assert "### 公众态度" in section
    assert "### 高赞分析" in section
    assert "👍33" in section
    assert "👍12" in section
    assert "👍4" not in section


def test_append_section_is_idempotent() -> None:
    service = CommentInsightService(Settings())
    base = "# 标题\n\n内容"
    section = "## 评论区洞察（含点赞权重）\n\n- 示例"
    merged_once = service.append_section(summary_markdown=base, section_markdown=section)
    merged_twice = service.append_section(
        summary_markdown=merged_once,
        section_markdown=section,
    )
    assert merged_twice.count("## 评论区洞察（含点赞权重）") == 1
