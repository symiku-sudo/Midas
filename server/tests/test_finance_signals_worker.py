from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace

import pytest

from finance_signals import main as worker


def _base_config() -> dict:
    return {
        "news": {
            "sources": [{"name": "test", "url": "https://example.com/rss", "category": "finance"}],
            "poll": {
                "max_items_per_source": 20,
                "max_top_items": 5,
                "recency_max_age_hours": 24,
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
                "recency_half_life_hours": 8,
                "default_keyword_score": 10,
                "title_keyword_bonus": 6,
                "missing_timestamp_multiplier": 0.65,
                "same_topic_source_bonus": 6,
                "category_base_scores": {
                    "finance": 86,
                    "politics": 80,
                },
                "keyword_weights": {
                    "美联储": 20,
                    "降息": 18,
                    "原油": 18,
                    "白宫": 18,
                    "选举": 18,
                    "停火": 18,
                    "关税": 16,
                },
                "source_weights": {
                    "Reuters": 18,
                    "新华网": 8,
                    "BBC": 8,
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
            "topics": {
                "finance": {
                    "label": "金融",
                    "keywords": ["美联储", "降息", "原油", "黄金", "关税"],
                },
                "politics": {
                    "label": "时政",
                    "keywords": ["白宫", "选举", "停火", "会谈"],
                },
            },
            "exclude_title_if_contains": [],
            "negation_prefixes": ["未", "没有", "并非"],
        },
        "ai_insight": {
            "safe_text": "safe",
            "section_separator": " | ",
            "max_market_alerts_in_text": 0,
            "max_news_items_in_text": 5,
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
    recent_finance = now_utc - timedelta(hours=1)
    older_finance = now_utc - timedelta(hours=8)
    recent_politics = now_utc - timedelta(hours=2)
    stale_item = now_utc - timedelta(hours=72)

    entries = [
        {
            "title": "美联储官员暗示年内可能降息",
            "summary": "美元与债市同步波动",
            "link": "https://example.com/finance-recent",
            "published": format_datetime(recent_finance),
        },
        {
            "title": "原油上涨带动大宗商品走强",
            "summary": "",
            "link": "https://example.com/finance-older",
            "published": format_datetime(older_finance),
        },
        {
            "title": "白宫就停火会谈释放最新表态",
            "summary": "",
            "link": "https://example.com/politics-recent",
            "published": format_datetime(recent_politics),
        },
        {
            "title": "三天前的降息旧闻",
            "summary": "",
            "link": "https://example.com/finance-stale",
            "published": format_datetime(stale_item),
        },
        {
            "title": "地方政策解读长文",
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

    assert [item["title"] for item in result["top_news"]] == [
        "美联储官员暗示年内可能降息",
        "白宫就停火会谈释放最新表态",
        "原油上涨带动大宗商品走强",
    ]
    assert "三天前的降息旧闻" not in {item["title"] for item in result["top_news"]}
    assert result["debug"]["entries_scanned"] == 5
    assert result["debug"]["matched_entries_count"] == 3
    assert result["debug"]["top_news_count"] == 3
    assert result["debug"]["top_unmatched_titles"] == ["地方政策解读长文"]
    json.dumps(result["top_news"], ensure_ascii=False)


def test_build_ai_insight_text_returns_top_news_summary() -> None:
    config = _base_config()
    text = worker.build_ai_insight_text(
        config=config,
        top_news=[
            {"title": "美联储官员释放降息信号", "category": "finance"},
            {"title": "白宫回应停火会谈进展", "category": "politics"},
        ],
    )

    assert "finance: 美联储官员释放降息信号" in text
    assert "politics: 白宫回应停火会谈进展" in text


@pytest.mark.asyncio
async def test_run_news_job_prefers_higher_weight_source_and_dedupes_same_topic(monkeypatch) -> None:
    now_utc = datetime.now(timezone.utc)
    entries = [
        {
            "title": "新华社消息丨白宫称停火会谈仍将继续 - 新华网",
            "summary": "",
            "link": "https://example.com/xinhua",
            "published": format_datetime(now_utc - timedelta(hours=1)),
        },
        {
            "title": "中国发布丨白宫称停火会谈仍将继续 - 中国网",
            "summary": "",
            "link": "https://example.com/china",
            "published": format_datetime(now_utc - timedelta(minutes=50)),
        },
        {
            "title": "美联储降息预期推升美债表现 - Reuters",
            "summary": "Rate-cut expectations support bonds.",
            "link": "https://example.com/reuters",
            "published": format_datetime(now_utc - timedelta(hours=3)),
        },
    ]
    config = _base_config()
    config["news"]["sources"][0]["category"] = "politics"
    config["news"]["ranking"]["source_weights"]["中国网"] = 4

    monkeypatch.setattr(
        worker,
        "parse_feed_sync",
        lambda _url: SimpleNamespace(entries=entries),
    )

    result = await worker.run_news_job(config)

    titles = [item["title"] for item in result["top_news"]]
    assert titles[0] == "新华社消息丨白宫称停火会谈仍将继续 - 新华网"
    assert "新华社消息丨白宫称停火会谈仍将继续 - 新华网" in titles
    assert "美联储降息预期推升美债表现 - Reuters" in titles
    assert "中国发布丨白宫称停火会谈仍将继续 - 中国网" not in titles


@pytest.mark.asyncio
async def test_run_news_job_respects_source_blocklist_and_topic_similarity(monkeypatch) -> None:
    now_utc = datetime.now(timezone.utc)
    entries = [
        {
            "title": "中国发布丨白宫称停火会谈仍将继续 - 中国网",
            "summary": "",
            "link": "https://example.com/china",
            "published": format_datetime(now_utc - timedelta(minutes=30)),
        },
        {
            "title": "新华社消息丨白宫称停火会谈仍将继续 - 新华网",
            "summary": "",
            "link": "https://example.com/xinhua",
            "published": format_datetime(now_utc - timedelta(minutes=40)),
        },
        {
            "title": "选举结果刺激市场波动 - 新浪新闻",
            "summary": "选举与关税预期升温",
            "link": "https://mil.sina.cn/example",
            "published": format_datetime(now_utc - timedelta(minutes=20)),
        },
    ]
    config = _base_config()
    config["news"]["filters"]["source_blocklist"] = ["新浪新闻"]

    monkeypatch.setattr(
        worker,
        "parse_feed_sync",
        lambda _url: SimpleNamespace(entries=entries),
    )

    result = await worker.run_news_job(config)

    assert [item["title"] for item in result["top_news"]] == [
        "新华社消息丨白宫称停火会谈仍将继续 - 新华网"
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
    assert second["last_alert_status"] == "no_new_topics"
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
    assert second["last_alert_status"] == "no_new_topics"
    assert len(called) == 1


def test_high_risk_alert_legacy_state_does_not_resend_same_titles(tmp_path, monkeypatch) -> None:
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
    state_file = tmp_path / "finance_alert_state.json"
    state_file.write_text(
        (
            '{\n'
            '  "last_alert_time": "2026-03-08 13:52:00",\n'
            '  "last_alert_signature": "legacy-signature-with-score",\n'
            '  "last_alert_summary": "A [score=181.2]；B [score=160.4]"\n'
            '}\n'
        ),
        encoding="utf-8",
    )

    payload = worker.build_high_risk_alert_payload(
        config=config,
        news_hits={
            "crisis_up_hits": [
                {"title": "A", "topic_key": "topic-a", "score": 181.2},
                {"title": "B", "topic_key": "topic-b", "score": 160.4},
            ]
        },
    )

    assert payload is not None
    called = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check, capture_output, text: called.append(command),
    )

    result = worker.maybe_send_high_risk_notification(
        config=config,
        alert_payload=payload,
        fetch_time="2026-03-08 13:56:00",
    )

    assert result["last_alert_status"] == "no_new_titles"
    assert len(called) == 0


def test_build_market_alert_payload_and_delivery_logic(tmp_path, monkeypatch) -> None:
    config = _base_config()
    config["_config_dir"] = str(tmp_path)
    config["output"] = {"time_format": "%Y-%m-%d %H:%M:%S"}
    config["market_data"]["alerting"]["enabled"] = True
    config["market_data"]["alerting"]["state_file"] = "finance_market_alert_state.json"
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
    assert second["last_alert_status"] == "no_new_topics"
    assert len(called) == 1


def test_market_alert_price_jitter_does_not_resend(tmp_path, monkeypatch) -> None:
    config = _base_config()
    config["_config_dir"] = str(tmp_path)
    config["output"] = {"time_format": "%Y-%m-%d %H:%M:%S"}
    config["market_data"]["alerting"]["enabled"] = True
    config["market_data"]["alerting"]["state_file"] = "finance_market_alert_state.json"
    config["market_data"]["alerting"]["ntfy_config_file"] = "notify.env"
    config["market_data"]["alerting"]["notify_script"] = "notify_stub.sh"
    notify_env = tmp_path / "notify.env"
    notify_env.write_text("NTFY_TOPIC=test\n", encoding="utf-8")
    notify_script = tmp_path / "notify_stub.sh"
    notify_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    notify_script.chmod(0o755)

    first_payload = worker.build_market_alert_payload(
        config=config,
        market_alerts=["布伦特原油（BZ=F）触发：价格突破 90（当前 92.69 >= 阈值 90.00）"],
    )
    second_payload = worker.build_market_alert_payload(
        config=config,
        market_alerts=["布伦特原油（BZ=F）触发：价格突破 90（当前 92.81 >= 阈值 90.00）"],
    )

    assert first_payload is not None
    assert second_payload is not None
    assert first_payload["signature"] == second_payload["signature"]

    called = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check, capture_output, text: called.append(command),
    )

    first = worker.maybe_send_market_alert_notification(
        config=config,
        alert_payload=first_payload,
        fetch_time="2026-03-08 14:07:00",
    )
    second = worker.maybe_send_market_alert_notification(
        config=config,
        alert_payload=second_payload,
        fetch_time="2026-03-08 14:08:00",
    )

    assert first["last_alert_status"] == "sent"
    assert second["last_alert_status"] == "no_new_topics"
    assert len(called) == 1


def test_market_alert_legacy_state_does_not_resend_same_threshold(tmp_path, monkeypatch) -> None:
    config = _base_config()
    config["_config_dir"] = str(tmp_path)
    config["output"] = {"time_format": "%Y-%m-%d %H:%M:%S"}
    config["market_data"]["alerting"]["enabled"] = True
    config["market_data"]["alerting"]["state_file"] = "finance_market_alert_state.json"
    config["market_data"]["alerting"]["ntfy_config_file"] = "notify.env"
    config["market_data"]["alerting"]["notify_script"] = "notify_stub.sh"
    notify_env = tmp_path / "notify.env"
    notify_env.write_text("NTFY_TOPIC=test\n", encoding="utf-8")
    notify_script = tmp_path / "notify_stub.sh"
    notify_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    notify_script.chmod(0o755)
    state_file = tmp_path / "finance_market_alert_state.json"
    state_file.write_text(
        (
            '{\n'
            '  "last_alert_time": "2026-03-08 14:07:00",\n'
            '  "last_alert_signature": "布伦特原油（BZ=F）触发：价格突破 90（当前 92.69 >= 阈值 90.00）",\n'
            '  "last_alert_summary": "布伦特原油（BZ=F）触发：价格突破 90（当前 92.69 >= 阈值 90.00）"\n'
            '}\n'
        ),
        encoding="utf-8",
    )

    payload = worker.build_market_alert_payload(
        config=config,
        market_alerts=["布伦特原油（BZ=F）触发：价格突破 90（当前 92.81 >= 阈值 90.00）"],
    )

    assert payload is not None
    called = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check, capture_output, text: called.append(command),
    )

    result = worker.maybe_send_market_alert_notification(
        config=config,
        alert_payload=payload,
        fetch_time="2026-03-08 14:11:00",
    )

    assert result["last_alert_status"] == "no_new_titles"
    assert len(called) == 0


def test_market_alert_reentry_after_clear_resends(tmp_path, monkeypatch) -> None:
    config = _base_config()
    config["_config_dir"] = str(tmp_path)
    config["output"] = {"time_format": "%Y-%m-%d %H:%M:%S"}
    config["market_data"]["alerting"]["enabled"] = True
    config["market_data"]["alerting"]["state_file"] = "finance_market_alert_state.json"
    config["market_data"]["alerting"]["ntfy_config_file"] = "notify.env"
    config["market_data"]["alerting"]["notify_script"] = "notify_stub.sh"
    notify_env = tmp_path / "notify.env"
    notify_env.write_text("NTFY_TOPIC=test\n", encoding="utf-8")
    notify_script = tmp_path / "notify_stub.sh"
    notify_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    notify_script.chmod(0o755)

    up_payload = worker.build_market_alert_payload(
        config=config,
        market_alerts=["布伦特原油（BZ=F）触发：价格突破 90（当前 92.69 >= 阈值 90.00）"],
    )
    assert up_payload is not None

    called = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check, capture_output, text: called.append(command),
    )

    first = worker.maybe_send_market_alert_notification(
        config=config,
        alert_payload=up_payload,
        fetch_time="2026-03-08 14:07:00",
    )
    cleared = worker.maybe_send_market_alert_notification(
        config=config,
        alert_payload=None,
        fetch_time="2026-03-08 14:08:00",
    )
    second = worker.maybe_send_market_alert_notification(
        config=config,
        alert_payload=up_payload,
        fetch_time="2026-03-08 14:09:00",
    )

    assert first["last_alert_status"] == "sent"
    assert cleared["last_alert_status"] == "threshold_not_met"
    assert second["last_alert_status"] == "sent"
    assert len(called) == 2
