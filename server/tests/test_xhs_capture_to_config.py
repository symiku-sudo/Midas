from __future__ import annotations

import json

import pytest

from tools.xhs_capture_to_config import (
    FieldInference,
    RequestCapture,
    apply_capture_to_config,
    apply_capture_from_default_auth_source_to_env,
    build_env_updates,
    extract_best_har_capture,
    infer_fields_from_payload,
    parse_curl_text,
    upsert_env_file,
)


def test_parse_curl_text_basic() -> None:
    curl = (
        "curl 'https://edith.xiaohongshu.com/api/sns/web/v1/collect/list' "
        "-H 'Cookie: a=b; c=d' "
        "-H 'User-Agent: UA' "
        "--data-raw '{\"cursor\":\"\"}'"
    )
    capture = parse_curl_text(curl)

    assert capture.request_url == "https://edith.xiaohongshu.com/api/sns/web/v1/collect/list"
    assert capture.request_method == "POST"
    assert capture.request_headers["Cookie"] == "a=b; c=d"
    assert capture.request_body == '{"cursor":""}'


def test_parse_curl_text_supports_cookie_option_b() -> None:
    curl = (
        "curl 'https://edith.xiaohongshu.com/api/sns/web/v1/collect/list' "
        "-b 'a=b; c=d' "
        "-A 'UA'"
    )
    capture = parse_curl_text(curl)

    assert capture.request_url == "https://edith.xiaohongshu.com/api/sns/web/v1/collect/list"
    assert capture.request_method == "GET"
    assert capture.request_headers["Cookie"] == "a=b; c=d"
    assert capture.request_headers["User-Agent"] == "UA"


def test_parse_curl_text_supports_windows_multiline_continuation() -> None:
    curl = (
        "curl \"https://edith.xiaohongshu.com/api/sns/web/v1/collect/list\" ^\n"
        "  --cookie \"a=b; c=d\" ^\n"
        "  --user-agent \"UA-WIN\""
    )
    capture = parse_curl_text(curl)

    assert capture.request_url == "https://edith.xiaohongshu.com/api/sns/web/v1/collect/list"
    assert capture.request_method == "GET"
    assert capture.request_headers["Cookie"] == "a=b; c=d"
    assert capture.request_headers["User-Agent"] == "UA-WIN"


def test_infer_fields_from_payload() -> None:
    payload = {
        "code": 0,
        "data": {
            "notes": [
                {
                    "note_id": "n1",
                    "title": "标题",
                    "desc": "正文",
                    "url": "https://www.xiaohongshu.com/explore/n1",
                }
            ]
        },
    }
    inference, score = infer_fields_from_payload(payload)

    assert inference is not None
    assert score >= 4
    assert inference.items_path == "data.notes"
    assert inference.note_id_field == "note_id"
    assert inference.title_field == "title"
    assert inference.source_url_field == "url"
    assert "desc" in inference.content_field_candidates


def test_extract_best_har_capture_prefers_note_list() -> None:
    suggestion_resp = {
        "code": 1000,
        "success": True,
        "data": {
            "queries": [{"title": "猜你想搜", "search_word": "x"}],
        },
    }
    notes_resp = {
        "code": 1000,
        "success": True,
        "data": {
            "notes": [
                {
                    "note_id": "abc",
                    "title": "A",
                    "desc": "B",
                    "url": "https://www.xiaohongshu.com/explore/abc",
                }
            ]
        },
    }
    har = {
        "log": {
            "entries": [
                {
                    "request": {
                        "method": "GET",
                        "url": "https://edith.xiaohongshu.com/api/sns/web/v1/search/hint",
                        "headers": [],
                    },
                    "response": {
                        "status": 200,
                        "content": {"text": json.dumps(suggestion_resp)},
                    },
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://edith.xiaohongshu.com/api/sns/web/v1/collect/list",
                        "headers": [{"name": "Cookie", "value": "a=b"}],
                    },
                    "response": {
                        "status": 200,
                        "content": {"text": json.dumps(notes_resp)},
                    },
                },
            ]
        }
    }

    capture = extract_best_har_capture(har)
    assert capture.request_url.endswith("/collect/list")
    assert capture.request_method == "GET"
    assert capture.inference is not None
    assert capture.inference.items_path == "data.notes"


def test_apply_capture_to_config() -> None:
    capture = RequestCapture(
        request_url="https://edith.xiaohongshu.com/api/sns/web/v1/collect/list",
        request_method="POST",
        request_headers={"Cookie": "a=b"},
        request_body='{"cursor":""}',
        inference=FieldInference(
            items_path="data.notes",
            note_id_field="note_id",
            title_field="title",
            content_field_candidates=["desc", "content"],
            source_url_field="url",
        ),
    )

    merged = apply_capture_to_config({}, capture)
    assert merged["xiaohongshu"]["mode"] == "web_readonly"
    assert merged["xiaohongshu"]["web_readonly"]["request_method"] == "POST"
    assert merged["xiaohongshu"]["web_readonly"]["items_path"] == "data.notes"


def test_build_env_updates_from_capture_case_insensitive_headers() -> None:
    capture = RequestCapture(
        request_url="https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page?num=30",
        request_method="GET",
        request_headers={
            "accept": "application/json, text/plain, */*",
            "cookie": "a=b; c=d",
            "origin": "https://www.xiaohongshu.com",
            "referer": "https://www.xiaohongshu.com/",
            "user-agent": "UA",
            "x-s": "x-s-token",
            "x-s-common": "x-s-common-token",
            "x-t": "1771936884011",
        },
        request_body="",
    )

    updates = build_env_updates(capture)
    assert updates["XHS_REQUEST_URL"].startswith(
        "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page"
    )
    assert updates["XHS_HEADER_ACCEPT"] == "application/json, text/plain, */*"
    assert updates["XHS_HEADER_COOKIE"] == "a=b; c=d"
    assert updates["XHS_HEADER_X_S"] == "x-s-token"
    assert updates["XHS_HEADER_X_S_COMMON"] == "x-s-common-token"
    assert updates["XHS_HEADER_X_T"] == "1771936884011"


def test_upsert_env_file_updates_existing_and_appends_new(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "GEMINI_API_KEY=test-key\nXHS_HEADER_COOKIE=old-cookie\n",
        encoding="utf-8",
    )

    upsert_env_file(
        env_path,
        {
            "XHS_HEADER_COOKIE": "new-cookie",
            "XHS_REQUEST_URL": "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
            "XHS_HEADER_X_S": "x-s-token",
        },
    )

    text = env_path.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=test-key" in text
    assert "XHS_HEADER_COOKIE=new-cookie" in text
    assert (
        "XHS_REQUEST_URL=https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page"
        in text
    )
    assert "XHS_HEADER_X_S=x-s-token" in text


def test_upsert_env_file_keeps_existing_secret_when_new_value_empty(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("XHS_HEADER_COOKIE=keep-me\n", encoding="utf-8")

    upsert_env_file(env_path, {"XHS_HEADER_COOKIE": ""})

    text = env_path.read_text(encoding="utf-8")
    assert "XHS_HEADER_COOKIE=keep-me" in text


def test_apply_capture_from_default_auth_source_prefers_har(tmp_path, monkeypatch) -> None:
    har_path = tmp_path / "xhs.har"
    curl_path = tmp_path / "xhs.curl"
    env_path = tmp_path / ".env"

    har_path.write_text(
        json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "request": {
                                "method": "GET",
                                "url": "https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page",
                                "headers": [{"name": "Cookie", "value": "har_cookie=1"}],
                            },
                            "response": {
                                "status": 200,
                                "content": {
                                    "text": json.dumps(
                                        {
                                            "code": 0,
                                            "data": {
                                                "notes": [
                                                    {
                                                        "note_id": "n1",
                                                        "title": "标题",
                                                        "desc": "正文",
                                                        "url": "https://www.xiaohongshu.com/explore/n1",
                                                    }
                                                ]
                                            },
                                        }
                                    )
                                },
                            },
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    curl_path.write_text(
        "curl 'https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page' "
        "-H 'Cookie: curl_cookie=1'",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "tools.xhs_capture_to_config.resolve_default_har_path",
        lambda: har_path,
    )
    monkeypatch.setattr(
        "tools.xhs_capture_to_config.resolve_default_curl_path",
        lambda: curl_path,
    )

    source, path, capture, updates = apply_capture_from_default_auth_source_to_env(
        env_path=env_path,
        require_cookie=True,
    )

    assert source == "har"
    assert path == har_path
    assert capture.request_url.startswith("https://edith.xiaohongshu.com/")
    assert updates["XHS_HEADER_COOKIE"] == "har_cookie=1"
    assert "XHS_HEADER_COOKIE=har_cookie=1" in env_path.read_text(encoding="utf-8")


def test_apply_capture_from_default_auth_source_falls_back_to_curl(
    tmp_path, monkeypatch
) -> None:
    har_path = tmp_path / "xhs.har"
    curl_path = tmp_path / "xhs.curl"
    env_path = tmp_path / ".env"

    har_path.write_text(json.dumps({"log": {"entries": []}}), encoding="utf-8")
    curl_path.write_text(
        "curl 'https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page' "
        "-H 'Cookie: curl_cookie=1' "
        "-H 'User-Agent: ua-test'",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "tools.xhs_capture_to_config.resolve_default_har_path",
        lambda: har_path,
    )
    monkeypatch.setattr(
        "tools.xhs_capture_to_config.resolve_default_curl_path",
        lambda: curl_path,
    )

    source, path, capture, updates = apply_capture_from_default_auth_source_to_env(
        env_path=env_path,
        require_cookie=True,
    )

    assert source == "curl"
    assert path == curl_path
    assert capture.request_method == "GET"
    assert updates["XHS_HEADER_COOKIE"] == "curl_cookie=1"
    assert "XHS_HEADER_COOKIE=curl_cookie=1" in env_path.read_text(encoding="utf-8")


def test_apply_capture_from_default_auth_source_raises_when_both_invalid(
    tmp_path, monkeypatch
) -> None:
    har_path = tmp_path / "xhs.har"
    curl_path = tmp_path / "xhs.curl"

    har_path.write_text(json.dumps({"log": {"entries": []}}), encoding="utf-8")
    curl_path.write_text(
        "curl 'https://edith.xiaohongshu.com/api/sns/web/v2/note/collect/page' "
        "-H 'User-Agent: ua-test'",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "tools.xhs_capture_to_config.resolve_default_har_path",
        lambda: har_path,
    )
    monkeypatch.setattr(
        "tools.xhs_capture_to_config.resolve_default_curl_path",
        lambda: curl_path,
    )

    with pytest.raises(ValueError) as exc_info:
        apply_capture_from_default_auth_source_to_env(
            env_path=tmp_path / ".env",
            require_cookie=True,
        )
    assert "HAR:" in str(exc_info.value)
    assert "cURL:" in str(exc_info.value)
