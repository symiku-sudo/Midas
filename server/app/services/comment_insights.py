from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Iterable

from app.core.config import Settings
from app.core.errors import AppError
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

_SECTION_TITLE = "评论区洞察（含点赞权重）"
_SECTION_HEADING = f"## {_SECTION_TITLE}"
_SECTION_PATTERN = re.compile(r"(?m)^##\s*评论区洞察（含点赞权重）\s*$")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_POSITIVE_HINTS = (
    "赞同",
    "支持",
    "有用",
    "干货",
    "实用",
    "清晰",
    "靠谱",
    "受用",
    "启发",
    "收藏了",
)
_NEGATIVE_HINTS = (
    "不行",
    "误导",
    "片面",
    "夸张",
    "营销",
    "鸡汤",
    "反对",
    "踩雷",
    "看不懂",
    "忽悠",
)


@dataclass(frozen=True)
class CommentSnippet:
    text: str
    like_count: int = 0


class CommentInsightService:
    def __init__(
        self,
        settings: Settings,
        llm_service: LLMService | None = None,
    ) -> None:
        self._settings = settings
        self._llm = llm_service or LLMService(settings)

    async def build_insight_section(
        self,
        *,
        platform: str,
        source_title: str,
        source_url: str,
        comments: Iterable[CommentSnippet],
    ) -> str:
        normalized_comments = self._normalize_comments(comments)
        if not normalized_comments:
            return self._build_empty_section()

        if self._settings.llm.enabled:
            try:
                llm_section = await self._llm.summarize_comment_insights(
                    platform=platform,
                    source_title=source_title,
                    source_url=source_url,
                    comments=[
                        {"text": item.text, "like_count": item.like_count}
                        for item in normalized_comments
                    ],
                    max_highlight_items=self._settings.comment_insights.max_highlight_items,
                )
                normalized = self._normalize_llm_section(llm_section)
                if normalized:
                    return normalized
            except AppError as exc:
                logger.warning(
                    "Comment insights LLM summarize failed, fallback to local: code=%s message=%s",
                    exc.code.value,
                    exc.message,
                )

        return self._build_local_section(normalized_comments)

    def append_section(self, *, summary_markdown: str, section_markdown: str) -> str:
        base = summary_markdown.rstrip()
        section = section_markdown.strip()
        if not section:
            return summary_markdown
        if _SECTION_PATTERN.search(base):
            return summary_markdown
        if not base:
            return section + "\n"
        return f"{base}\n\n{section}\n"

    def _normalize_comments(self, comments: Iterable[CommentSnippet]) -> list[CommentSnippet]:
        max_items = max(int(self._settings.comment_insights.max_comments_for_summary), 1)
        max_comment_length = max(int(self._settings.comment_insights.max_comment_length), 32)
        seen: set[str] = set()
        normalized: list[CommentSnippet] = []
        for item in comments:
            text = _WHITESPACE_PATTERN.sub(" ", str(item.text).strip())
            if not text:
                continue
            if len(text) > max_comment_length:
                text = text[: max_comment_length - 1].rstrip() + "…"
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            like_count = max(int(item.like_count), 0)
            normalized.append(CommentSnippet(text=text, like_count=like_count))

        normalized.sort(
            key=lambda item: (item.like_count, len(item.text)),
            reverse=True,
        )
        return normalized[:max_items]

    def _normalize_llm_section(self, raw_markdown: str) -> str:
        markdown = str(raw_markdown or "").strip()
        if not markdown:
            return ""

        lines = [line.rstrip() for line in markdown.splitlines()]
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines:
            return ""

        body_lines = lines
        first_line = body_lines[0].strip()
        if first_line.startswith("#"):
            body_lines = body_lines[1:]
            while body_lines and not body_lines[0].strip():
                body_lines.pop(0)

        body = "\n".join(body_lines).strip()
        if not body:
            return self._build_empty_section()
        if _SECTION_PATTERN.search(body):
            return body
        return f"{_SECTION_HEADING}\n\n{body}"

    def _build_empty_section(self) -> str:
        return (
            f"{_SECTION_HEADING}\n\n"
            "### 公众态度\n\n"
            "- 暂未提取到可用评论，无法判断倾向。\n\n"
            "### 高赞分析\n\n"
            "- 暂无可提炼观点。\n"
        )

    def _build_local_section(self, comments: list[CommentSnippet]) -> str:
        attitude = self._estimate_attitude(comments)
        max_highlights = max(int(self._settings.comment_insights.max_highlight_items), 1)
        highlights = sorted(
            comments,
            key=lambda item: (item.like_count, len(item.text)),
            reverse=True,
        )[:max_highlights]
        highlight_lines = [f"- 👍{item.like_count}: {item.text}" for item in highlights]
        total_likes = sum(item.like_count for item in comments)
        return (
            f"{_SECTION_HEADING}\n\n"
            "### 公众态度\n\n"
            f"- {attitude}\n\n"
            "### 高赞分析\n\n"
            f"{chr(10).join(highlight_lines)}\n\n"
            "### 样本说明\n\n"
            f"- 纳入评论：{len(comments)} 条\n"
            f"- 累计点赞：{total_likes}\n"
            "- 已按点赞数对观点权重做加权。\n"
        )

    def _estimate_attitude(self, comments: list[CommentSnippet]) -> str:
        weighted_score = 0.0
        for item in comments:
            score = self._sentiment_score(item.text)
            weight = math.log2(item.like_count + 2)
            weighted_score += score * weight

        if weighted_score >= 1.8:
            return "整体偏正向，评论区更认可内容的实用性与可执行性。"
        if weighted_score <= -1.8:
            return "整体偏负向，评论区对观点准确性或适用性有明显质疑。"
        return "整体观点偏分歧/中性，认可与质疑并存。"

    def _sentiment_score(self, text: str) -> int:
        normalized = text.lower()
        positive_hits = sum(1 for token in _POSITIVE_HINTS if token in normalized)
        negative_hits = sum(1 for token in _NEGATIVE_HINTS if token in normalized)
        if positive_hits > negative_hits:
            return 1
        if negative_hits > positive_hits:
            return -1
        return 0
