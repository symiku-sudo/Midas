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
            }
        ],
        "ai_insight_text": "行情警报：布伦特原油触发阈值。",
        "news_debug": {
            "entries_scanned": 12,
            "entries_filtered_by_source": 2,
            "up_hits_count": 2,
            "down_hits_count": 1,
            "top_unmatched_titles": ["以色列袭击伊朗石油储存设施"],
            "enabled": True,
            "sent": True,
            "last_alert_time": "2026-03-08 12:00:00",
            "last_alert_signature": "sig-1",
            "last_alert_summary": "高危舆情触发",
            "last_alert_status": "sent",
        },
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    service = FinanceSignalsService()
    service._config_path = config_path

    data = service.get_dashboard_state()

    assert data.news_last_fetch_time == payload["news_last_fetch_time"]
    assert data.news_stale is False
    assert data.news_debug.entries_scanned == 12
    assert data.news_debug.entries_filtered_by_source == 2
    assert data.news_debug.top_unmatched_titles == ["以色列袭击伊朗石油储存设施"]
    assert data.news_debug.last_alert_status == "sent"


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
