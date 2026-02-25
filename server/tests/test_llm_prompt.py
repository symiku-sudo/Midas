from __future__ import annotations

from app.services.llm import _SYSTEM_PROMPT


def test_bilibili_prompt_requires_concise_non_template_title() -> None:
    assert "首行必须是一级标题" in _SYSTEM_PROMPT
    assert "不超过18个字" in _SYSTEM_PROMPT
    assert "标题禁止使用“这是一份关于……的知识整理”" in _SYSTEM_PROMPT
    assert "只能放在摘要首句" in _SYSTEM_PROMPT
