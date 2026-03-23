from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import Settings, XiaohongshuConfig, XiaohongshuWebReadonlyConfig
from app.core.errors import AppError, ErrorCode
from app.repositories.note_repo import NoteLibraryRepository
from app.repositories.xiaohongshu_repo import XiaohongshuSyncRepository
from app.services.comment_insights import CommentSnippet
from app.services.xiaohongshu import (
    XiaohongshuNote,
    XiaohongshuPageBatch,
    XiaohongshuService,
    XiaohongshuWebReadonlySource,
)


class SimpleLLM:
    def __init__(self) -> None:
        self.last_text_kwargs: dict | None = None
        self.last_video_kwargs: dict | None = None
        self.last_comment_kwargs: dict | None = None

    async def summarize_xiaohongshu_note(self, **kwargs) -> str:
        self.last_text_kwargs = kwargs
        return "# 总结\n\n这是一段测试总结。"

    async def summarize_xiaohongshu_video_note(self, **kwargs) -> str:
        self.last_video_kwargs = kwargs
        return "# 视频总结\n\n- 结论 A"

    async def summarize_comment_insights(self, **kwargs) -> str:
        self.last_comment_kwargs = kwargs
        return "## 评论区洞察（含点赞权重）\n\n- 高赞观点：太实用了。"


class SingleUrlWebSource:
    def __init__(
        self,
        note: XiaohongshuNote,
        *,
        comments: list[CommentSnippet] | None = None,
    ) -> None:
        self._note = note
        self._comments = comments or []
        self.last_url = ""

    async def fetch_note_by_url(self, note_url: str) -> XiaohongshuNote:
        self.last_url = note_url
        return self._note

    async def fetch_comment_snippets(
        self,
        *,
        note: XiaohongshuNote,
        limit: int,
    ) -> list[CommentSnippet]:
        assert note.note_id == self._note.note_id
        return self._comments[:limit]


def _make_web_settings(
    tmp_path: Path | None = None,
    *,
    llm_enabled: bool = True,
    comment_insights: dict | None = None,
    **web_kwargs,
) -> Settings:
    db_path = str((tmp_path or Path(".tmp")) / "midas.db")
    base_web = {
        "request_url": "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
        "request_method": "GET",
        "request_headers": {"Cookie": "a=b"},
        "items_path": "data.notes",
        "note_id_field": "note_id",
        "title_field": "title",
        "content_field_candidates": ["desc"],
        "detail_fetch_mode": "never",
        "host_allowlist": ["www.xiaohongshu.com", "edith.xiaohongshu.com"],
    }
    base_web.update(web_kwargs)
    return Settings(
        llm={"enabled": llm_enabled},
        comment_insights=comment_insights or {},
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=db_path,
            web_readonly=XiaohongshuWebReadonlyConfig(**base_web),
        ),
    )


@pytest.mark.asyncio
async def test_web_readonly_summarize_url_marks_synced(tmp_path: Path) -> None:
    settings = _make_web_settings(tmp_path)
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    llm = SimpleLLM()
    note = XiaohongshuNote(
        note_id="u1",
        title="url-note",
        content="来自单篇 URL 的正文",
        source_url="https://www.xiaohongshu.com/explore/u1",
    )
    source = SingleUrlWebSource(
        note,
        comments=[CommentSnippet(text="太实用了。", like_count=12)],
    )
    service = XiaohongshuService(
        settings=settings,
        repository=repo,
        web_source=source,
        llm_service=llm,
    )

    result = await service.summarize_url("https://www.xiaohongshu.com/explore/u1")

    assert result.note_id == "u1"
    assert result.source_url == "https://www.xiaohongshu.com/explore/u1"
    assert source.last_url == "https://www.xiaohongshu.com/explore/u1"
    assert repo.is_synced("u1") is True
    assert "原文链接" in result.summary_markdown
    assert "评论区洞察（含点赞权重）" in result.summary_markdown
    assert llm.last_text_kwargs is not None
    assert llm.last_text_kwargs["note_id"] == "u1"


@pytest.mark.asyncio
async def test_summarize_url_returns_saved_summary_for_deduped_note(tmp_path: Path) -> None:
    settings = _make_web_settings(tmp_path)
    db_path = str(tmp_path / "midas.db")
    repo = XiaohongshuSyncRepository(db_path)
    notes_repo = NoteLibraryRepository(db_path)
    notes_repo.save_xiaohongshu_notes(
        [
            {
                "note_id": "u2",
                "title": "已保存标题",
                "source_url": "https://www.xiaohongshu.com/explore/u2",
                "summary_markdown": "# 旧总结\n\n这是旧内容。",
            }
        ]
    )
    repo.mark_synced("u2", "已保存标题", "https://www.xiaohongshu.com/explore/u2")
    note = XiaohongshuNote(
        note_id="u2",
        title="新标题不会覆盖",
        content="正文",
        source_url="https://www.xiaohongshu.com/explore/u2",
    )
    service = XiaohongshuService(
        settings=settings,
        repository=repo,
        web_source=SingleUrlWebSource(note),
        llm_service=SimpleLLM(),
    )

    result = await service.summarize_url("https://www.xiaohongshu.com/explore/u2")

    assert result.note_id == "u2"
    assert result.title == "已保存标题"
    assert "# 旧总结" in result.summary_markdown
    assert "原文链接" in result.summary_markdown


@pytest.mark.asyncio
async def test_summarize_url_passes_image_urls_to_llm(tmp_path: Path) -> None:
    settings = _make_web_settings(tmp_path)
    llm = SimpleLLM()
    note = XiaohongshuNote(
        note_id="img-1",
        title="图文笔记",
        content="正文",
        source_url="https://www.xiaohongshu.com/explore/img-1",
        image_urls=["https://sns-webpic-qc.xhscdn.com/abc/image-1"],
    )
    service = XiaohongshuService(
        settings=settings,
        repository=XiaohongshuSyncRepository(str(tmp_path / "midas.db")),
        web_source=SingleUrlWebSource(note),
        llm_service=llm,
    )

    result = await service.summarize_url(note.source_url)

    assert result.note_id == "img-1"
    assert llm.last_text_kwargs is not None
    assert llm.last_text_kwargs["image_urls"] == [
        "https://sns-webpic-qc.xhscdn.com/abc/image-1"
    ]


@pytest.mark.asyncio
async def test_summarize_url_video_note_uses_audio_asr_and_video_llm(tmp_path: Path) -> None:
    settings = _make_web_settings(tmp_path)

    class DummyFetcher:
        def __init__(self) -> None:
            self.last_headers: dict[str, str] | None = None

        def fetch_audio(self, video_url: str, output_dir: Path, headers=None):
            _ = video_url
            self.last_headers = headers
            audio_path = output_dir / "source.wav"
            audio_path.write_bytes(b"dummy-audio")
            return audio_path

    class DummyASR:
        def transcribe(self, audio_path: Path) -> str:
            assert audio_path.name == "source.wav"
            return "这是视频转写文本。"

    llm = SimpleLLM()
    fetcher = DummyFetcher()
    note = XiaohongshuNote(
        note_id="video-1",
        title="视频笔记",
        content="这是原笔记正文",
        source_url="https://www.xiaohongshu.com/explore/video-1",
        is_video=True,
    )
    service = XiaohongshuService(
        settings=settings,
        repository=XiaohongshuSyncRepository(str(tmp_path / "midas.db")),
        web_source=SingleUrlWebSource(note),
        llm_service=llm,
        audio_fetcher=fetcher,
        asr_service=DummyASR(),
    )

    result = await service.summarize_url(note.source_url)

    assert result.note_id == "video-1"
    assert llm.last_video_kwargs is not None
    assert llm.last_video_kwargs["transcript"] == "这是视频转写文本。"
    assert llm.last_video_kwargs["content"] == "这是原笔记正文"
    assert fetcher.last_headers is not None
    assert fetcher.last_headers["Referer"] == note.source_url
    assert "原文链接" in result.summary_markdown


@pytest.mark.asyncio
async def test_summarize_url_video_note_falls_back_to_text_summary_when_asr_fails(
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(tmp_path)

    class BrokenFetcher:
        def fetch_audio(self, video_url: str, output_dir: Path, headers=None):
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="音频下载失败",
                status_code=502,
            )

    llm = SimpleLLM()
    note = XiaohongshuNote(
        note_id="video-2",
        title="视频笔记",
        content="保底正文",
        source_url="https://www.xiaohongshu.com/explore/video-2",
        is_video=True,
    )
    service = XiaohongshuService(
        settings=settings,
        repository=XiaohongshuSyncRepository(str(tmp_path / "midas.db")),
        web_source=SingleUrlWebSource(note),
        llm_service=llm,
        audio_fetcher=BrokenFetcher(),
    )

    result = await service.summarize_url(note.source_url)

    assert llm.last_text_kwargs is not None
    assert llm.last_video_kwargs is None
    assert "视频音频转写失败" in result.summary_markdown
    assert "原文链接" in result.summary_markdown


@pytest.mark.asyncio
async def test_web_readonly_fetch_note_by_url_resolves_xhslink(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(tmp_path, request_url="https://www.xiaohongshu.com/api/some/path")
    source = XiaohongshuWebReadonlySource(settings)

    class FakeResponse:
        url = "https://www.xiaohongshu.com/explore/abc123"
        text = ""

    class FakeAsyncClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_args, **_kwargs):
            return FakeResponse()

    async def fake_extract_note_from_record(*_args, **_kwargs):
        return XiaohongshuNote(
            note_id="abc123",
            title="短链解析测试",
            content="正文",
            source_url="https://www.xiaohongshu.com/explore/abc123",
        )

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_extract_note_from_record",
        fake_extract_note_from_record,
    )

    note = await source.fetch_note_by_url("http://xhslink.com/o/eNmdwzRjEI")
    assert note.note_id == "abc123"
    assert note.source_url == "https://www.xiaohongshu.com/explore/abc123"


@pytest.mark.asyncio
async def test_web_readonly_fetch_note_by_url_resolves_xhslink_when_final_url_is_not_note(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(tmp_path, request_url="https://www.xiaohongshu.com/api/some/path")
    source = XiaohongshuWebReadonlySource(settings)

    class FakeResponse:
        url = "https://www.xiaohongshu.com/explore"
        text = '{"jump":"https:\\/\\/www.xiaohongshu.com\\/discovery\\/item\\/abc123"}'

    class FakeAsyncClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_args, **_kwargs):
            return FakeResponse()

    async def fake_extract_note_from_record(*_args, **_kwargs):
        return XiaohongshuNote(
            note_id="abc123",
            title="短链回退解析测试",
            content="正文",
            source_url="https://www.xiaohongshu.com/discovery/item/abc123",
        )

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_extract_note_from_record",
        fake_extract_note_from_record,
    )

    note = await source.fetch_note_by_url("http://xhslink.com/o/eNmdwzRjEI")
    assert note.note_id == "abc123"
    assert note.source_url == "https://www.xiaohongshu.com/discovery/item/abc123"


@pytest.mark.asyncio
async def test_web_readonly_fetch_note_by_url_keeps_image_only_note(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(
        tmp_path,
        request_url="https://www.xiaohongshu.com/api/some/path",
        detail_fetch_mode="never",
    )
    source = XiaohongshuWebReadonlySource(settings)

    class FakeResp:
        def __init__(self, *, text: str = "", status_code: int = 200) -> None:
            self.status_code = status_code
            self.text = text

        @staticmethod
        def json() -> dict:
            return {}

    class FakeClient:
        calls: list[str] = []

        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **kwargs):
            url = kwargs["url"]
            self.calls.append(url)
            html = """
            <html><body>
            <script>
            window.__INITIAL_STATE__ = {"note":{"noteDetailMap":{"imgonly1":{"note":{"noteId":"imgonly1","title":"图片笔记标题","desc":"","type":"normal","imageList":[{"urlDefault":"https://sns-webpic-qc.xhscdn.com/imgonly-1"}]}}}}};
            </script>
            </body></html>
            """
            return FakeResp(text=html)

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", FakeClient)

    note = await source.fetch_note_by_url(
        "https://www.xiaohongshu.com/discovery/item/imgonly1"
    )
    assert note.note_id == "imgonly1"
    assert note.title == "图片笔记标题"
    assert note.content == ""
    assert note.image_urls == ["https://sns-webpic-qc.xhscdn.com/imgonly-1"]
    assert note.is_video is False
    assert any("/discovery/item/imgonly1" in url for url in FakeClient.calls)


def test_extract_note_id_from_url_supports_note_and_notes_paths(tmp_path: Path) -> None:
    settings = _make_web_settings(tmp_path, request_url="https://www.xiaohongshu.com/api/some/path")
    source = XiaohongshuWebReadonlySource(settings)

    assert source.extract_note_id_from_url("https://www.xiaohongshu.com/note/abc123") == "abc123"
    assert source.extract_note_id_from_url("https://www.xiaohongshu.com/notes/xyz987") == "xyz987"


def test_build_note_page_url_inherits_xsec_token_from_source_url_query(tmp_path: Path) -> None:
    settings = _make_web_settings(tmp_path, request_url="https://www.xiaohongshu.com/api/some/path")
    source = XiaohongshuWebReadonlySource(settings)

    built = source._build_note_page_url(
        note_id="abc123",
        source_url=(
            "https://www.xiaohongshu.com/discovery/item/abc123"
            "?xsec_token=token-1&xsec_source=app_share"
        ),
        record={},
    )
    assert "xsec_token=token-1" in built
    assert "xsec_source=app_share" in built


@pytest.mark.asyncio
async def test_web_readonly_rejects_title_only_content(monkeypatch, tmp_path: Path) -> None:
    settings = _make_web_settings(
        tmp_path,
        title_field="display_title",
        content_field_candidates=["display_title", "desc"],
    )
    source = XiaohongshuWebReadonlySource(settings)

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "data": {
                    "notes": [
                        {
                            "note_id": "n1",
                            "display_title": "只有标题",
                            "desc": "只有标题",
                        }
                    ]
                }
            }

    class FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **_):
            return FakeResp()

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", FakeClient)

    with pytest.raises(AppError) as exc_info:
        await source.fetch_recent(limit=1)
    assert exc_info.value.code == ErrorCode.UPSTREAM_ERROR
    assert "未提取到可用正文" in exc_info.value.message


@pytest.mark.asyncio
async def test_web_readonly_auto_fallback_to_playwright_on_http_406(monkeypatch, tmp_path: Path) -> None:
    settings = _make_web_settings(tmp_path, page_fetch_driver="auto")
    source = XiaohongshuWebReadonlySource(settings)
    calls = {"http": 0, "playwright": 0}

    async def fake_iter_pages_http(self, **_kwargs):
        _ = self
        calls["http"] += 1
        raise AppError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="小红书请求失败（HTTP 406）。",
            status_code=502,
            details={"status_code": 406},
        )
        yield XiaohongshuPageBatch(notes=[])

    async def fake_iter_pages_playwright(self, **_kwargs):
        _ = self
        calls["playwright"] += 1
        yield XiaohongshuPageBatch(
            notes=[
                XiaohongshuNote(
                    note_id="p1",
                    title="playwright-1",
                    content="正文1",
                    source_url="https://www.xiaohongshu.com/explore/p1",
                )
            ],
            request_cursor="cursor-1",
            next_cursor="",
            exhausted=True,
        )

    monkeypatch.setattr(XiaohongshuWebReadonlySource, "_iter_pages_http", fake_iter_pages_http)
    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_iter_pages_playwright",
        fake_iter_pages_playwright,
    )

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].note_id == "p1"
    assert calls["http"] == 1
    assert calls["playwright"] == 1


@pytest.mark.asyncio
async def test_web_readonly_http_driver_does_not_fallback_to_playwright(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(tmp_path, page_fetch_driver="http")
    source = XiaohongshuWebReadonlySource(settings)
    calls = {"http": 0, "playwright": 0}

    async def fake_iter_pages_http(self, **_kwargs):
        _ = self
        calls["http"] += 1
        raise AppError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="小红书请求失败（HTTP 406）。",
            status_code=502,
            details={"status_code": 406},
        )
        yield XiaohongshuPageBatch(notes=[])

    async def fake_iter_pages_playwright(self, **_kwargs):
        _ = self
        calls["playwright"] += 1
        yield XiaohongshuPageBatch(notes=[], exhausted=True)

    monkeypatch.setattr(XiaohongshuWebReadonlySource, "_iter_pages_http", fake_iter_pages_http)
    monkeypatch.setattr(
        XiaohongshuWebReadonlySource,
        "_iter_pages_playwright",
        fake_iter_pages_playwright,
    )

    with pytest.raises(AppError) as exc_info:
        await source.fetch_recent(limit=1)
    assert exc_info.value.code == ErrorCode.UPSTREAM_ERROR
    assert calls["http"] == 1
    assert calls["playwright"] == 0


@pytest.mark.asyncio
async def test_web_readonly_business_auth_expired_maps_to_auth_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(
        tmp_path,
        title_field="display_title",
        content_field_candidates=["display_title", "desc"],
    )
    source = XiaohongshuWebReadonlySource(settings)

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {"code": -100, "success": False, "msg": "登录已过期", "data": {}}

    class FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **_):
            return FakeResp()

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", FakeClient)

    with pytest.raises(AppError) as exc_info:
        await source.fetch_recent(limit=1)
    assert exc_info.value.code == ErrorCode.AUTH_EXPIRED


@pytest.mark.asyncio
async def test_web_readonly_detail_fetch_extracts_content_and_images(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(
        tmp_path,
        title_field="display_title",
        content_field_candidates=["display_title", "desc"],
        image_field_candidates=["cover.url_pre"],
        detail_fetch_mode="always",
        detail_request_url_template=(
            "https://edith.xiaohongshu.com/api/sns/web/v1/note/detail?"
            "note_id={note_id}&xsec_token={xsec_token}"
        ),
        detail_content_field_candidates=["data.items.0.note_card.desc"],
        detail_image_field_candidates=["data.items.0.note_card.image_list"],
        max_images_per_note=3,
    )
    source = XiaohongshuWebReadonlySource(settings)

    class FakeResp:
        def __init__(self, payload: dict | None = None, text: str = "", status_code: int = 200) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        calls: list[str] = []

        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **kwargs):
            url = kwargs["url"]
            self.calls.append(url)
            if "collect/page" in url:
                return FakeResp(
                    {
                        "data": {
                            "notes": [
                                {
                                    "note_id": "n1",
                                    "display_title": "只有标题",
                                    "desc": "只有标题",
                                    "xsec_token": "token-1",
                                    "cover": {"url_pre": "https://sns-webpic-qc.xhscdn.com/cover-1"},
                                }
                            ]
                        }
                    }
                )
            if "/explore/" in url:
                return FakeResp(status_code=404)
            return FakeResp(
                {
                    "data": {
                        "items": [
                            {
                                "note_card": {
                                    "desc": "这是详情正文",
                                    "image_list": [
                                        {"url_default": "https://sns-webpic-qc.xhscdn.com/detail-1"},
                                        {"url_default": "https://sns-webpic-qc.xhscdn.com/detail-2"},
                                    ],
                                }
                            }
                        ]
                    }
                }
            )

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", FakeClient)

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].content == "这是详情正文"
    assert notes[0].image_urls == [
        "https://sns-webpic-qc.xhscdn.com/detail-1",
        "https://sns-webpic-qc.xhscdn.com/detail-2",
        "https://sns-webpic-qc.xhscdn.com/cover-1",
    ]
    assert any("/note/detail?" in url for url in FakeClient.calls)


def test_extract_image_urls_prefers_ordered_single_url_per_image() -> None:
    source = XiaohongshuWebReadonlySource(Settings())
    payload = {
        "note_card": {
            "image_list": [
                {
                    "url_default": "https://sns-webpic-qc.xhscdn.com/img-1-default",
                    "url_pre": "https://sns-webpic-qc.xhscdn.com/img-1-pre",
                    "info_list": [{"url": "https://sns-webpic-qc.xhscdn.com/img-1-info"}],
                },
                {
                    "url_default": "https://sns-webpic-qc.xhscdn.com/img-2-default",
                    "url_pre": "https://sns-webpic-qc.xhscdn.com/img-2-pre",
                },
                {
                    "url_pre": "https://sns-webpic-qc.xhscdn.com/img-3-pre",
                    "info_list": [{"url": "https://sns-webpic-qc.xhscdn.com/img-3-info"}],
                },
            ]
        }
    }

    image_urls = source._extract_image_urls(
        payload=payload,
        candidates=["note_card.image_list"],
        max_count=3,
    )

    assert image_urls == [
        "https://sns-webpic-qc.xhscdn.com/img-1-default",
        "https://sns-webpic-qc.xhscdn.com/img-2-default",
        "https://sns-webpic-qc.xhscdn.com/img-3-pre",
    ]


@pytest.mark.asyncio
async def test_web_readonly_empty_notes_list_with_guest_cookie_raises_auth_expired(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(
        tmp_path,
        request_url=(
            "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page?"
            "num=30&cursor=&user_id=old-user"
        ),
    )
    source = XiaohongshuWebReadonlySource(settings)

    class FakeResp:
        def __init__(self, payload: dict) -> None:
            self.status_code = 200
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **kwargs):
            url = kwargs["url"]
            if "/api/sns/web/v2/user/me" in url:
                return FakeResp({"code": 0, "success": True, "data": {"guest": True}})
            return FakeResp({"code": 0, "success": True, "data": {"notes": []}})

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", FakeClient)

    with pytest.raises(AppError) as exc_info:
        await source.fetch_recent(limit=5)
    assert exc_info.value.code == ErrorCode.AUTH_EXPIRED
    assert "游客态" in exc_info.value.message


def test_build_playwright_collect_page_url_prefers_live_user_id_override() -> None:
    source = XiaohongshuWebReadonlySource(Settings())
    url = source._build_playwright_collect_page_url(
        request_url=(
            "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page?"
            "num=30&cursor=&user_id=old-user"
        ),
        template="https://www.xiaohongshu.com/user/profile/{user_id}?tab=collect",
        user_id_override="new-user",
    )
    assert url == "https://www.xiaohongshu.com/user/profile/new-user?tab=collect"


def test_playwright_collect_candidate_rejects_telemetry_collect_endpoint() -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                host_allowlist=["www.xiaohongshu.com", "edith.xiaohongshu.com"],
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    ok = source._is_playwright_collect_response_candidate(
        response_url="https://t2.xiaohongshu.com/api/v2/collect",
        request_method="POST",
        configured_method="GET",
        configured_host="edith.xiaohongshu.com",
        configured_path="/api/sns/web/v2/note/collect/page",
        host_allowlist=["www.xiaohongshu.com", "edith.xiaohongshu.com"],
    )

    assert ok is False


def test_extract_request_cursor_from_request_supports_json_and_form_body() -> None:
    source = XiaohongshuWebReadonlySource(Settings())

    cursor_from_json = source._extract_request_cursor_from_request(
        request_url="https://t2.xiaohongshu.com/api/v2/collect",
        request_body='{"cursor":"abc123","num":30}',
    )
    cursor_from_form = source._extract_request_cursor_from_request(
        request_url="https://t2.xiaohongshu.com/api/v2/collect",
        request_body="num=30&cursor=xyz789",
    )

    assert cursor_from_json == "abc123"
    assert cursor_from_form == "xyz789"


@pytest.mark.asyncio
async def test_fetch_comment_snippets_fallbacks_to_comment_api_when_initial_empty(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(
        tmp_path,
        comment_insights={"request_timeout_seconds": 8},
    )
    source = XiaohongshuWebReadonlySource(settings)
    note = XiaohongshuNote(
        note_id="n1",
        title="标题",
        content="正文",
        source_url=(
            "https://www.xiaohongshu.com/discovery/item/n1"
            "?xsec_token=token-1&xsec_source=app_share"
        ),
    )

    async def fake_request_text(*_args, **_kwargs) -> str:
        return "<html>ok</html>"

    monkeypatch.setattr(source, "_request_text", fake_request_text)
    monkeypatch.setattr(
        source,
        "_extract_initial_state",
        lambda _html: {
            "note": {
                "noteDetailMap": {
                    "n1": {
                        "comments": {
                            "list": [],
                            "hasMore": True,
                            "firstRequestFinish": False,
                        }
                    }
                }
            }
        },
    )

    captured_urls: list[str] = []

    async def fake_request_json(*, client, method, url, headers, body):
        _ = client
        _ = headers
        _ = body
        assert method == "GET"
        captured_urls.append(url)
        return {
            "msg": "成功",
            "data": {
                "has_more": False,
                "cursor": "",
                "comments": [
                    {"content": "第一条评论", "like_count": "12"},
                    {"content": "第二条评论", "liked_count": "3"},
                ],
            },
        }

    monkeypatch.setattr(source, "_request_json", fake_request_json)

    comments = await source.fetch_comment_snippets(note=note, limit=5)

    assert len(comments) == 2
    assert comments[0].text == "第一条评论"
    assert comments[0].like_count == 12
    assert comments[1].text == "第二条评论"
    assert comments[1].like_count == 3
    parsed = urlparse(captured_urls[0])
    assert parsed.path == "/api/sns/web/v2/comment/page"
    query = parse_qs(parsed.query)
    assert query["note_id"] == ["n1"]
    assert query["xsec_token"] == ["token-1"]
    assert query["xsec_source"] == ["app_share"]


@pytest.mark.asyncio
async def test_fetch_comment_snippets_uses_initial_state_without_comment_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = _make_web_settings(tmp_path)
    source = XiaohongshuWebReadonlySource(settings)
    note = XiaohongshuNote(
        note_id="n2",
        title="标题2",
        content="正文2",
        source_url="https://www.xiaohongshu.com/discovery/item/n2",
    )

    async def fake_request_text(*_args, **_kwargs) -> str:
        return "<html>ok</html>"

    monkeypatch.setattr(source, "_request_text", fake_request_text)
    monkeypatch.setattr(
        source,
        "_extract_initial_state",
        lambda _html: {
            "note": {
                "noteDetailMap": {
                    "n2": {
                        "comments": {
                            "list": [
                                {"content": "首包评论", "like_count": "9"},
                            ],
                            "hasMore": False,
                            "firstRequestFinish": True,
                        }
                    }
                }
            }
        },
    )

    async def unexpected_request_json(*_args, **_kwargs):
        raise AssertionError("initial_state 已有评论时不应再请求 comment API")

    monkeypatch.setattr(source, "_request_json", unexpected_request_json)

    comments = await source.fetch_comment_snippets(note=note, limit=5)
    assert len(comments) == 1
    assert comments[0].text == "首包评论"
    assert comments[0].like_count == 9
