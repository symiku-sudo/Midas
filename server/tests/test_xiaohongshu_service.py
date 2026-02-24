from __future__ import annotations

import time

import pytest

from app.core.config import Settings, XiaohongshuConfig, XiaohongshuWebReadonlyConfig
from app.core.errors import AppError, ErrorCode
from app.repositories.xiaohongshu_repo import XiaohongshuSyncRepository
from app.services.xiaohongshu import (
    XiaohongshuNote,
    XiaohongshuSyncService,
    XiaohongshuWebReadonlySource,
)


class AlwaysFailLLM:
    async def summarize_xiaohongshu_note(self, **_: str) -> str:
        raise AppError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="mock llm failed",
            status_code=502,
        )


class FixedSource:
    def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
        data = [
            XiaohongshuNote(
                note_id="n1",
                title="t1",
                content="c1",
                source_url="https://www.xiaohongshu.com/explore/n1",
            ),
            XiaohongshuNote(
                note_id="n2",
                title="t2",
                content="c2",
                source_url="https://www.xiaohongshu.com/explore/n2",
            ),
        ]
        return data[:limit]


class FixedWebSource:
    async def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
        data = [
            XiaohongshuNote(
                note_id="w1",
                title="web-title-1",
                content="web-content-1",
                source_url="https://www.xiaohongshu.com/explore/w1",
            ),
            XiaohongshuNote(
                note_id="w2",
                title="web-title-2",
                content="web-content-2",
                source_url="https://www.xiaohongshu.com/explore/w2",
            ),
        ]
        return data[:limit]


class SimpleLLM:
    async def summarize_xiaohongshu_note(self, **_: str) -> str:
        return "# 总结\n\n这是一段测试总结。"


class CaptureLLM:
    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    async def summarize_xiaohongshu_note(self, **kwargs) -> str:
        self.last_kwargs = kwargs
        return "# 总结\n\n这是一段测试总结。"


@pytest.mark.asyncio
async def test_sync_circuit_breaker(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            circuit_breaker_failures=2,
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=FixedSource(),
        llm_service=AlwaysFailLLM(),
    )

    with pytest.raises(AppError) as exc_info:
        await service.sync(limit=2)

    err = exc_info.value
    assert err.code == ErrorCode.CIRCUIT_OPEN
    assert err.details["failed_count"] == 2
    assert err.details["circuit_opened"] is True


@pytest.mark.asyncio
async def test_web_readonly_requires_confirm_live(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=FixedWebSource(),
    )

    with pytest.raises(AppError) as exc_info:
        await service.sync(limit=1, confirm_live=False)
    assert exc_info.value.code == ErrorCode.INVALID_INPUT


@pytest.mark.asyncio
async def test_web_readonly_rate_limit_guard(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=1800,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    repo.set_state("last_live_sync_ts", str(int(time.time())))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=FixedWebSource(),
    )

    with pytest.raises(AppError) as exc_info:
        await service.sync(limit=1, confirm_live=True)
    assert exc_info.value.code == ErrorCode.RATE_LIMITED


@pytest.mark.asyncio
async def test_web_readonly_success_sets_last_sync_state(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=str(tmp_path / "midas.db"),
            min_live_sync_interval_seconds=0,
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://www.xiaohongshu.com/api/some/path"
            ),
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        web_source=FixedWebSource(),
        llm_service=SimpleLLM(),
    )

    result = await service.sync(limit=1, confirm_live=True)
    assert result.new_count == 1
    assert result.fetched_count == 1
    assert repo.get_state("last_live_sync_ts") is not None


@pytest.mark.asyncio
async def test_sync_result_markdown_contains_source_url(tmp_path) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=FixedSource(),
        llm_service=SimpleLLM(),
    )

    result = await service.sync(limit=1)
    assert len(result.summaries) == 1
    assert "https://www.xiaohongshu.com/explore/n1" in result.summaries[0].summary_markdown
    assert "原文链接" in result.summaries[0].summary_markdown


@pytest.mark.asyncio
async def test_sync_passes_image_urls_to_llm(tmp_path) -> None:
    class _ImageSource:
        def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
            return [
                XiaohongshuNote(
                    note_id="n1",
                    title="t1",
                    content="c1",
                    source_url="https://www.xiaohongshu.com/explore/n1",
                    image_urls=["https://sns-webpic-qc.xhscdn.com/abc/image-1"],
                )
            ][:limit]

    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    llm = CaptureLLM()
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=_ImageSource(),
        llm_service=llm,
    )

    result = await service.sync(limit=1)
    assert result.new_count == 1
    assert llm.last_kwargs is not None
    assert llm.last_kwargs["image_urls"] == [
        "https://sns-webpic-qc.xhscdn.com/abc/image-1"
    ]


@pytest.mark.asyncio
async def test_sync_video_note_skips_llm_and_emits_placeholder(tmp_path) -> None:
    class _VideoSource:
        def fetch_recent(self, limit: int) -> list[XiaohongshuNote]:
            return [
                XiaohongshuNote(
                    note_id="v1",
                    title="视频笔记标题",
                    content="",
                    source_url="https://www.xiaohongshu.com/explore/v1",
                    is_video=True,
                )
            ][:limit]

    class _NeverCallLLM:
        def __init__(self) -> None:
            self.called = False

        async def summarize_xiaohongshu_note(self, **kwargs) -> str:
            self.called = True
            return "SHOULD_NOT_BE_CALLED"

    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="mock",
            db_path=str(tmp_path / "midas.db"),
            max_limit=30,
            default_limit=20,
        )
    )
    repo = XiaohongshuSyncRepository(str(tmp_path / "midas.db"))
    llm = _NeverCallLLM()
    service = XiaohongshuSyncService(
        settings=settings,
        repository=repo,
        source=_VideoSource(),
        llm_service=llm,
    )

    result = await service.sync(limit=1)
    assert result.new_count == 1
    assert llm.called is False
    assert "这是一个视频笔记" in result.summaries[0].summary_markdown
    assert "暂不进行视频内容总结" in result.summaries[0].summary_markdown
    assert "原文链接" in result.summaries[0].summary_markdown
    assert "https://www.xiaohongshu.com/explore/v1" in result.summaries[0].summary_markdown


@pytest.mark.asyncio
async def test_web_readonly_rejects_title_only_content(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="display_title",
                content_field_candidates=["display_title", "desc"],
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
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

    class _FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **_):
            return _FakeResp()

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    with pytest.raises(AppError) as exc_info:
        await source.fetch_recent(limit=1)
    assert exc_info.value.code == ErrorCode.UPSTREAM_ERROR
    assert "未提取到可用正文" in exc_info.value.message


@pytest.mark.asyncio
async def test_web_readonly_page_fallback_extracts_content_and_images(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="display_title",
                content_field_candidates=["display_title", "desc"],
                max_images_per_note=3,
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        def __init__(self, payload: dict | None = None, text: str = "", status_code: int = 200) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self) -> dict:
            return self._payload

    class _FakeClient:
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
                return _FakeResp(
                    {
                        "data": {
                            "notes": [
                                {
                                    "note_id": "n2",
                                    "display_title": "列表标题",
                                    "desc": "列表标题",
                                    "xsec_token": "token-2",
                                }
                            ]
                        }
                    }
                )
            html = """
            <html><body>
            <script>
            window.__INITIAL_STATE__ = {"note":{"noteDetailMap":{"n2":{"note":{"noteId":"n2","title":"页面标题","desc":"页面正文","type":"normal","imageList":[{"urlDefault":"https://sns-webpic-qc.xhscdn.com/page-1"}]}}}}};
            </script>
            </body></html>
            """
            return _FakeResp(text=html)

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].title == "页面标题"
    assert notes[0].content == "页面正文"
    assert notes[0].image_urls == ["https://sns-webpic-qc.xhscdn.com/page-1"]
    assert len(_FakeClient.calls) == 2
    assert any("/explore/n2" in url for url in _FakeClient.calls)


@pytest.mark.asyncio
async def test_web_readonly_detail_fetch_extracts_content_and_images(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
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
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        def __init__(
            self, payload: dict | None = None, text: str = "", status_code: int = 200
        ) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self) -> dict:
            return self._payload

    class _FakeClient:
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
                return _FakeResp(
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
                return _FakeResp(status_code=404)
            return _FakeResp(
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

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].content == "这是详情正文"
    assert notes[0].image_urls == [
        "https://sns-webpic-qc.xhscdn.com/detail-1",
        "https://sns-webpic-qc.xhscdn.com/detail-2",
        "https://sns-webpic-qc.xhscdn.com/cover-1",
    ]
    assert len(_FakeClient.calls) == 3
    assert any("/explore/n1" in url for url in _FakeClient.calls)
    assert any("/note/detail?" in url for url in _FakeClient.calls)


@pytest.mark.asyncio
async def test_web_readonly_video_note_kept_without_content(monkeypatch) -> None:
    settings = Settings(
        xiaohongshu=XiaohongshuConfig(
            mode="web_readonly",
            db_path=".tmp/test-midas.db",
            web_readonly=XiaohongshuWebReadonlyConfig(
                request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                request_method="GET",
                request_headers={"Cookie": "a=b"},
                items_path="data.notes",
                note_id_field="note_id",
                title_field="display_title",
                content_field_candidates=["desc"],
                detail_fetch_mode="never",
            ),
        )
    )
    source = XiaohongshuWebReadonlySource(settings)

    class _FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "data": {
                    "notes": [
                        {
                            "note_id": "v100",
                            "display_title": "这是个视频",
                            "type": "video",
                        }
                    ]
                }
            }

    class _FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, **_):
            return _FakeResp()

    monkeypatch.setattr("app.services.xiaohongshu.httpx.AsyncClient", _FakeClient)

    notes = await source.fetch_recent(limit=1)
    assert len(notes) == 1
    assert notes[0].note_id == "v100"
    assert notes[0].is_video is True
    assert notes[0].content == ""
