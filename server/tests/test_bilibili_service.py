from __future__ import annotations

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
