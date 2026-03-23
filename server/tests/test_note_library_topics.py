from __future__ import annotations

from app.models.schemas import UnifiedNoteItem
from app.services.note_library import NoteLibraryService


def test_extract_note_topics_filters_generic_labels_and_surfaces_named_entities() -> None:
    service = object.__new__(NoteLibraryService)

    topics = NoteLibraryService._extract_note_topics(
        service,
        title="Anthropic 人类技能替代率报告",
        summary_markdown=(
            "# Anthropic 人类技能替代率报告\n\n"
            "## 摘要\nAI 正在重塑高学历脑力岗位。\n\n"
            "## 评论区洞察\n围绕程序员、金融、法律岗位的替代风险展开讨论。\n"
        ),
    )

    assert "Anthropic" in topics
    assert any("技能替代率" in topic for topic in topics)
    assert "评论区洞察" not in topics
    assert "摘要" not in topics


def test_review_notes_by_topics_groups_secondary_topics_too() -> None:
    class _StubRepository:
        def list_unified_notes(self, **_: object) -> list[dict[str, object]]:
            return [
                {"note_id": "1", "topics": ["OpenAI", "模型"]},
                {"note_id": "2", "topics": ["微软", "OpenAI"]},
                {"note_id": "3", "topics": ["微软"]},
            ]

    service = object.__new__(NoteLibraryService)
    service._repository = _StubRepository()

    def _build_item(row: dict[str, object]) -> UnifiedNoteItem:
        note_id = str(row["note_id"])
        topics = list(row["topics"])
        return UnifiedNoteItem(
            source="bilibili",
            note_id=note_id,
            title=f"note-{note_id}",
            source_url=f"https://example.com/{note_id}",
            summary_markdown="",
            saved_at=f"2026-03-0{note_id} 10:00:00",
            topics=topics,
        )

    service._build_unified_note_item = _build_item  # type: ignore[attr-defined]

    result = NoteLibraryService.review_notes_by_topics(
        service,
        days=30,
        limit=5,
        per_topic_limit=5,
    )

    grouped = {item.topic: item.total for item in result.items}
    assert grouped["OpenAI"] == 2
    assert grouped["微软"] == 2
