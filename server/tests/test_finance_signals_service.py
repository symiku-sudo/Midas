from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from app.services.finance_signals import FinanceSignalsService


def test_finance_signals_service_reads_news_fields_and_stale_flag(tmp_path: Path) -> None:
    config_path = tmp_path / "financial_config.yaml"
    status_path = tmp_path / "finance_status.json"
    config_path.write_text(
        """
output:
  status_file: "finance_status.json"
  time_format: "%Y-%m-%d %H:%M:%S"
news:
  poll:
    stale_after_seconds: 900
market_data:
  instruments:
    - name: "布伦特原油"
      symbol: "BZ=F"
      aliases: ["原油", "油价"]
      rule:
        type: "price_gte"
        threshold: 90
""".strip(),
        encoding="utf-8",
    )

    payload = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "news_last_fetch_time": (datetime.now() - timedelta(minutes=5)).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "watchlist_preview": [
            {
                "name": "布伦特原油",
                "symbol": "BZ=F",
                "price": 91.23,
                "change_pct": "+1.2%",
                "alert_active": True,
            }
        ],
        "top_news": [
            {
                "title": "美联储官员释放降息信号",
                "link": "https://example.com/news-1",
                "publisher": "Reuters",
                "published": "2026-03-08 11:30:00",
                "category": "finance",
                "matched_keywords": ["美联储", "降息"],
            }
        ],
        "watchlist_ntfy_enabled": True,
        "ai_insight_text": "finance: 美联储官员释放降息信号",
        "news_debug": {
            "entries_scanned": 12,
            "entries_filtered_by_source": 2,
            "matched_entries_count": 7,
            "top_news_count": 5,
            "digest_item_count": 11,
            "digest_prompt_chars": 5241,
            "digest_status": "generated",
            "digest_last_generated_at": "2026-03-10 12:00:00",
            "top_unmatched_titles": ["地方政策解读长文"],
        },
        "market_alert_debug": {
            "enabled": True,
            "sent": True,
            "last_alert_time": "2026-03-08 12:01:00",
            "last_alert_signature": "sig-market-1",
            "last_alert_summary": "行情阈值触发",
            "last_alert_status": "sent",
        },
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    service = FinanceSignalsService()
    service._config_path = config_path

    data = service.get_dashboard_state()

    assert data.news_last_fetch_time == payload["news_last_fetch_time"]
    assert data.news_stale is False
    assert data.watchlist_preview[0].alert_active is True
    assert data.watchlist_preview[0].related_news_count == 0
    assert data.top_news[0].title == "美联储官员释放降息信号"
    assert data.top_news[0].related_symbols == []
    assert data.focus_cards[0].kind == "ALERT"
    assert data.focus_cards[0].priority == "HIGH"
    assert data.focus_cards[0].action_type == "REVIEW_NOW"
    assert data.focus_cards[0].action_label == "立即复核"
    assert "threshold_triggered" in data.focus_cards[0].reasons
    assert data.watchlist_ntfy_enabled is True
    assert data.news_debug.entries_scanned == 12
    assert data.news_debug.entries_filtered_by_source == 2
    assert data.news_debug.matched_entries_count == 7
    assert data.news_debug.top_news_count == 5
    assert data.news_debug.digest_item_count == 11
    assert data.news_debug.digest_prompt_chars == 5241
    assert data.news_debug.digest_status == "generated"
    assert data.news_debug.digest_last_generated_at == "2026-03-10 12:00:00"
    assert data.news_debug.top_unmatched_titles == ["地方政策解读长文"]
    assert data.market_alert_debug.alert_sent is True
    assert data.market_alert_debug.last_alert_status == "sent"


def test_finance_signals_service_marks_missing_news_time_as_stale(tmp_path: Path) -> None:
    config_path = tmp_path / "financial_config.yaml"
    status_path = tmp_path / "finance_status.json"
    config_path.write_text(
        """
output:
  status_file: "finance_status.json"
  time_format: "%Y-%m-%d %H:%M:%S"
news:
  poll:
    stale_after_seconds: 900
market_data:
  instruments: []
""".strip(),
        encoding="utf-8",
    )
    status_path.write_text(
        json.dumps(
            {
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "watchlist_preview": [],
                "ai_insight_text": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = FinanceSignalsService()
    service._config_path = config_path

    data = service.get_dashboard_state()

    assert data.news_last_fetch_time == ""
    assert data.news_stale is True
    assert data.ai_insight_text == ""


def test_finance_signals_service_updates_watchlist_ntfy_toggle(tmp_path: Path) -> None:
    config_path = tmp_path / "financial_config.yaml"
    status_path = tmp_path / "finance_status.json"
    config_path.write_text(
        """
output:
  status_file: "finance_status.json"
market_data:
  alerting:
    enabled: true
""".strip(),
        encoding="utf-8",
    )

    service = FinanceSignalsService()
    service._config_path = config_path

    assert service.get_watchlist_ntfy_enabled() is True
    assert service.set_watchlist_ntfy_enabled(False) is False
    assert service.get_watchlist_ntfy_enabled() is False
    config_payload = config_path.read_text(encoding="utf-8")
    assert "enabled: true" in config_payload
    status_payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert status_payload["watchlist_ntfy_enabled"] is False


def test_finance_signals_service_links_news_with_watchlist_aliases(tmp_path: Path) -> None:
    config_path = tmp_path / "financial_config.yaml"
    status_path = tmp_path / "finance_status.json"
    config_path.write_text(
        """
output:
  status_file: "finance_status.json"
  time_format: "%Y-%m-%d %H:%M:%S"
news:
  poll:
    stale_after_seconds: 900
market_data:
  instruments:
    - name: "布伦特原油"
      symbol: "BZ=F"
      aliases: ["原油", "油价"]
      rule:
        type: "price_gte"
        threshold: 90
    - name: "现货黄金"
      symbol: "GC=F"
      aliases: ["黄金", "金价"]
      rule:
        type: "change_pct_lte"
        threshold: -1.5
""".strip(),
        encoding="utf-8",
    )
    status_path.write_text(
        json.dumps(
            {
                "update_time": "2026-03-12 12:00:00",
                "news_last_fetch_time": "2026-03-12 11:58:00",
                "watchlist_preview": [
                    {
                        "name": "布伦特原油",
                        "symbol": "BZ=F",
                        "price": 91.23,
                        "change_pct": "+1.2%",
                        "alert_active": True,
                    },
                    {
                        "name": "现货黄金",
                        "symbol": "GC=F",
                        "price": 2310.0,
                        "change_pct": "-0.8%",
                        "alert_active": False,
                    },
                ],
                "top_news": [
                    {
                        "title": "原油与黄金同步走高，市场关注通胀预期",
                        "publisher": "Reuters",
                        "published": "2026-03-12 11:30:00",
                        "category": "finance",
                        "matched_keywords": ["原油", "黄金", "通胀"],
                    }
                ],
                "watchlist_ntfy_enabled": True,
                "ai_insight_text": "finance: 原油与黄金同步走高。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = FinanceSignalsService()
    service._config_path = config_path

    data = service.get_dashboard_state()

    assert data.top_news[0].related_symbols == ["BZ=F", "GC=F"]
    assert data.top_news[0].related_watchlist_names == ["布伦特原油", "现货黄金"]
    assert data.watchlist_preview[0].related_news_count == 1
    assert data.watchlist_preview[0].related_keywords == ["原油"]
    assert data.watchlist_preview[1].related_news_count == 1
    assert data.watchlist_preview[1].related_keywords == ["黄金"]
    assert len(data.focus_cards) == 2
    assert data.focus_cards[0].kind == "ALERT"
    assert data.focus_cards[0].related_symbols == ["BZ=F"]
    assert data.focus_cards[0].action_type == "REVIEW_NOW"
    assert data.focus_cards[0].action_label == "立即复核"
    assert data.focus_cards[1].kind == "NEWS"
    assert data.focus_cards[1].related_watchlist_names == ["布伦特原油", "现货黄金"]
    assert data.focus_cards[1].priority == "HIGH"
    assert data.focus_cards[1].action_type == "FOLLOW_UP"
    assert data.focus_cards[1].action_label == "优先跟踪"
    assert "multi_asset_impact" in data.focus_cards[1].reasons
