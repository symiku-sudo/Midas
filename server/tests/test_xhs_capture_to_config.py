from __future__ import annotations

import json

from tools.xhs_capture_to_config import (
    FieldInference,
    RequestCapture,
    apply_capture_to_config,
    extract_best_har_capture,
    infer_fields_from_payload,
    parse_curl_text,
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
