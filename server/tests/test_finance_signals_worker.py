from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace

import pytest

from finance_signals import main as worker


def _base_config() -> dict:
    return {
        "news": {
            "sources": [{"name": "test", "url": "https://example.com/rss"}],
            "poll": {
                "max_items_per_source": 20,
                "max_matched_items": 8,
                "recency_max_age_hours": 48,
                "allow_missing_published": True,
                "max_unmatched_titles": 5,
                "topic_similarity_threshold": 0.55,
            },
            "filters": {
                "source_allowlist": [],
                "source_blocklist": [],
                "domain_allowlist": [],
                "domain_blocklist": [],
            },
            "ranking": {
                "recency_half_life_hours": 12,
                "default_keyword_score": 12,
                "title_keyword_bonus": 8,
                "missing_timestamp_multiplier": 0.7,
                "crisis_up_base_score": 100,
                "crisis_down_base_score": 40,
                "keyword_weights": {
                    "空袭": 24,
                    "袭击": 22,
                    "石油设施": 16,
                    "停火协议": 18,
                },
                "source_weights": {
                    "Reuters": 18,
                    "新华网": 8,
                    "观察者": 4,
                },
            },
            "alerting": {
                "enabled": False,
                "state_file": "finance_alert_state.json",
                "cooldown_seconds": 1800,
                "min_high_risk_score": 140,
                "min_high_risk_hits": 2,
                "max_items_in_notification": 3,
            },
            "keywords": {
                "crisis_up": ["空袭", "袭击", "石油设施"],
                "crisis_down": ["停火协议", "停火"],
                "exclude_title_if_contains": [],
                "negation_prefixes": ["未", "没有", "并非"],
            },
        },
        "ai_insight": {
            "safe_text": "safe",
            "section_separator": " | ",
            "max_market_alerts_in_text": 4,
            "max_news_items_in_text": 3,
        },
        "market_data": {
            "alerting": {
                "enabled": False,
                "state_file": "../.tmp/finance_market_alert_state.json",
                "cooldown_seconds": 1800,
                "min_market_alerts": 1,
                "max_items_in_notification": 3,
            }
        },
    }


@pytest.mark.asyncio
async def test_run_news_job_filters_stale_ranks_recent_hits_and_collects_debug(monkeypatch) -> None:
    now_utc = datetime.now(timezone.utc)
    recent_up = now_utc - timedelta(hours=1)
    older_up = now_utc - timedelta(hours=8)
    recent_down = now_utc - timedelta(hours=2)
    stale_up = now_utc - timedelta(hours=72)

    entries = [
        {
            "title": "伊朗遭遇空袭并波及石油设施",
            "summary": "地区风险继续升温",
            "link": "https://example.com/up-recent",
            "published": format_datetime(recent_up),
        },
        {
            "title": "早前空袭引发市场波动",
            "summary": "",
            "link": "https://example.com/up-older",
            "published": format_datetime(older_up),
        },
        {
            "title": "多方推动停火协议，局势暂时缓和",
            "summary": "",
            "link": "https://example.com/down-recent",
            "published": format_datetime(recent_down),
        },
        {
            "title": "三天前的空袭旧闻",
            "summary": "",
            "link": "https://example.com/up-stale",
            "published": format_datetime(stale_up),
        },
        {
            "title": "美国开始使用英国军事基地对伊朗开展行动",
            "summary": "",
            "link": "https://example.com/unmatched",
            "published": format_datetime(now_utc - timedelta(minutes=30)),
        },
    ]

    monkeypatch.setattr(
        worker,
        "parse_feed_sync",
        lambda _url: SimpleNamespace(entries=entries),
    )

    result = await worker.run_news_job(_base_config())

    assert [item["title"] for item in result["crisis_up_hits"]] == [
        "伊朗遭遇空袭并波及石油设施",
        "早前空袭引发市场波动",
    ]
    assert [item["title"] for item in result["crisis_down_hits"]] == [
        "多方推动停火协议，局势暂时缓和",
    ]
    assert "三天前的空袭旧闻" not in {
        item["title"] for item in result["crisis_up_hits"]
    }
    assert result["debug"]["entries_scanned"] == 5
    assert result["debug"]["up_hits_count"] == 2
    assert result["debug"]["down_hits_count"] == 1
    assert result["debug"]["top_unmatched_titles"] == [
        "美国开始使用英国军事基地对伊朗开展行动"
    ]


def test_build_ai_insight_text_can_show_up_and_down_sections() -> None:
    config = _base_config()
    text = worker.build_ai_insight_text(
        config=config,
        market_alerts=["布伦特原油（BZ=F）触发价格突破 90"],
        news_hits={
            "crisis_up_hits": [
                {"title": "伊朗遭遇空袭并波及石油设施", "matched_keywords": ["空袭", "石油设施"]}
            ],
            "crisis_down_hits": [
                {"title": "多方推动停火协议，局势暂时缓和", "matched_keywords": ["停火协议"]}
            ],
        },
    )

    assert "行情警报：" in text
    assert "舆情高危：" in text
    assert "舆情降温：" in text


@pytest.mark.asyncio
async def test_run_news_job_prefers_higher_weight_source_and_dedupes_same_topic(monkeypatch) -> None:
    now_utc = datetime.now(timezone.utc)
    entries = [
        {
            "title": "新华社消息丨王毅谈伊朗局势：停止军事行动 避免升级蔓延 - 新华网",
            "summary": "",
            "link": "https://example.com/xinhua",
            "published": format_datetime(now_utc - timedelta(hours=1)),
        },
        {
            "title": "中国发布丨王毅谈伊朗局势：停止军事行动 避免升级蔓延 - 中国网",
            "summary": "",
            "link": "https://example.com/china",
            "published": format_datetime(now_utc - timedelta(minutes=50)),
        },
        {
            "title": "霍尔木兹航运面临供应中断风险 - Reuters",
            "summary": "Supply disruption risk rises after latest clash.",
            "link": "https://example.com/reuters",
            "published": format_datetime(now_utc - timedelta(hours=3)),
        },
    ]
    config = _base_config()
    config["news"]["keywords"]["crisis_up"].extend(["军事行动", "供应中断"])
    config["news"]["keywords"]["crisis_down"].append("避免升级")
    config["news"]["ranking"]["keyword_weights"]["军事行动"] = 18
    config["news"]["ranking"]["keyword_weights"]["供应中断"] = 36

    monkeypatch.setattr(
        worker,
        "parse_feed_sync",
        lambda _url: SimpleNamespace(entries=entries),
    )

    result = await worker.run_news_job(config)

    down_titles = [item["title"] for item in result["crisis_down_hits"]]
    up_titles = [item["title"] for item in result["crisis_up_hits"]]

    assert down_titles == [
        "新华社消息丨王毅谈伊朗局势：停止军事行动 避免升级蔓延 - 新华网"
    ]
    assert up_titles[0] == "霍尔木兹航运面临供应中断风险 - Reuters"


@pytest.mark.asyncio
async def test_run_news_job_respects_source_blocklist_and_topic_similarity(monkeypatch) -> None:
    now_utc = datetime.now(timezone.utc)
    entries = [
        {
            "title": "中国发布丨王毅：伊朗局势应停止军事行动 避免升级蔓延 - 中国网",
            "summary": "",
            "link": "https://example.com/china",
            "published": format_datetime(now_utc - timedelta(minutes=30)),
        },
        {
            "title": "新华社消息丨王毅谈伊朗局势：停止军事行动 避免升级蔓延 - 新华网",
            "summary": "",
            "link": "https://example.com/xinhua",
            "published": format_datetime(now_utc - timedelta(minutes=40)),
        },
        {
            "title": "伊朗、以色列最新发声 - 新浪军事_手机新浪网",
            "summary": "冲突升级",
            "link": "https://mil.sina.cn/example",
            "published": format_datetime(now_utc - timedelta(minutes=20)),
        },
    ]
    config = _base_config()
    config["news"]["filters"]["source_blocklist"] = ["新浪军事_手机新浪网"]
    config["news"]["keywords"]["crisis_down"].append("避免升级")
    config["news"]["ranking"]["keyword_weights"]["避免升级"] = 12

    monkeypatch.setattr(
        worker,
        "parse_feed_sync",
        lambda _url: SimpleNamespace(entries=entries),
    )

    result = await worker.run_news_job(config)

    assert [item["title"] for item in result["crisis_down_hits"]] == [
        "新华社消息丨王毅谈伊朗局势：停止军事行动 避免升级蔓延 - 新华网"
    ]
    assert result["debug"]["entries_filtered_by_source"] == 1


def test_build_high_risk_alert_payload_and_cooldown_logic(tmp_path, monkeypatch) -> None:
    config = _base_config()
    config["_config_dir"] = str(tmp_path)
    config["output"] = {"time_format": "%Y-%m-%d %H:%M:%S"}
    config["news"]["alerting"]["enabled"] = True
    config["news"]["alerting"]["state_file"] = "finance_alert_state.json"
    config["news"]["alerting"]["ntfy_config_file"] = "notify.env"
    config["news"]["alerting"]["notify_script"] = "notify_stub.sh"
    notify_env = tmp_path / "notify.env"
    notify_env.write_text("NTFY_TOPIC=test\n", encoding="utf-8")
    notify_script = tmp_path / "notify_stub.sh"
    notify_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    notify_script.chmod(0o755)
    news_hits = {
        "crisis_up_hits": [
            {"title": "A", "topic_key": "a", "score": 180.0},
            {"title": "B", "topic_key": "b", "score": 160.0},
        ]
    }

    payload = worker.build_high_risk_alert_payload(config=config, news_hits=news_hits)
    assert payload is not None
    assert payload["hit_count"] == 2
    called = []

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check, capture_output, text: called.append(command),
    )

    first = worker.maybe_send_high_risk_notification(
        config=config,
        alert_payload=payload,
        fetch_time="2026-03-08 13:30:00",
    )
    second = worker.maybe_send_high_risk_notification(
        config=config,
        alert_payload=payload,
        fetch_time="2026-03-08 13:35:00",
    )

    assert first["last_alert_status"] == "sent"
    assert first["sent"] is True
    assert second["last_alert_status"] == "cooldown_skip"
    assert len(called) == 1


def test_high_risk_alert_signature_is_stable_across_score_jitter(tmp_path, monkeypatch) -> None:
    config = _base_config()
    config["_config_dir"] = str(tmp_path)
    config["output"] = {"time_format": "%Y-%m-%d %H:%M:%S"}
    config["news"]["alerting"]["enabled"] = True
    config["news"]["alerting"]["state_file"] = "finance_alert_state.json"
    config["news"]["alerting"]["ntfy_config_file"] = "notify.env"
    config["news"]["alerting"]["notify_script"] = "notify_stub.sh"
    notify_env = tmp_path / "notify.env"
    notify_env.write_text("NTFY_TOPIC=test\n", encoding="utf-8")
    notify_script = tmp_path / "notify_stub.sh"
    notify_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    notify_script.chmod(0o755)

    first_payload = worker.build_high_risk_alert_payload(
        config=config,
        news_hits={
            "crisis_up_hits": [
                {"title": "A", "topic_key": "topic-a", "score": 181.2},
                {"title": "B", "topic_key": "topic-b", "score": 160.4},
            ]
        },
    )
    second_payload = worker.build_high_risk_alert_payload(
        config=config,
        news_hits={
            "crisis_up_hits": [
                {"title": "B updated", "topic_key": "topic-b", "score": 165.9},
                {"title": "A updated", "topic_key": "topic-a", "score": 179.8},
            ]
        },
    )

    assert first_payload is not None
    assert second_payload is not None
    assert first_payload["signature"] == "topic-a|topic-b"
    assert second_payload["signature"] == "topic-a|topic-b"

    called = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check, capture_output, text: called.append(command),
    )

    first = worker.maybe_send_high_risk_notification(
        config=config,
        alert_payload=first_payload,
        fetch_time="2026-03-08 13:36:00",
    )
    second = worker.maybe_send_high_risk_notification(
        config=config,
        alert_payload=second_payload,
        fetch_time="2026-03-08 13:42:00",
    )

    assert first["last_alert_status"] == "sent"
    assert second["last_alert_status"] == "cooldown_skip"
    assert len(called) == 1


def test_build_market_alert_payload_and_delivery_logic(tmp_path, monkeypatch) -> None:
    config = _base_config()
    config["_config_dir"] = str(tmp_path)
    config["output"] = {"time_format": "%Y-%m-%d %H:%M:%S"}
    config["market_data"]["alerting"]["enabled"] = True
    config["market_data"]["alerting"]["ntfy_config_file"] = "notify.env"
    config["market_data"]["alerting"]["notify_script"] = "notify_stub.sh"
    notify_env = tmp_path / "notify.env"
    notify_env.write_text("NTFY_TOPIC=test\n", encoding="utf-8")
    notify_script = tmp_path / "notify_stub.sh"
    notify_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    notify_script.chmod(0o755)

    payload = worker.build_market_alert_payload(
        config=config,
        market_alerts=["布伦特原油（BZ=F）触发：价格突破 90", "VIX（^VIX）触发：指数突破 30"],
    )
    assert payload is not None
    assert payload["alert_count"] == 2

    called = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check, capture_output, text: called.append(command),
    )
    first = worker.maybe_send_market_alert_notification(
        config=config,
        alert_payload=payload,
        fetch_time="2026-03-08 13:40:00",
    )
    second = worker.maybe_send_market_alert_notification(
        config=config,
        alert_payload=payload,
        fetch_time="2026-03-08 13:41:00",
    )

    assert first["last_alert_status"] == "sent"
    assert second["last_alert_status"] == "cooldown_skip"
    assert len(called) == 1
