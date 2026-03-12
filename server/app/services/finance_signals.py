from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.core.errors import AppError, ErrorCode
from app.models.schemas import (
    FinanceMarketAlertDebugData,
    FinanceNewsItem,
    FinanceNewsDebugData,
    FinanceSignalsData,
    FinanceWatchlistItem,
)
from finance_signals import main as worker_main

_CONFIG_WRITE_LOCK = threading.RLock()


class FinanceSignalsService:
    def __init__(self) -> None:
        self._server_root = Path(__file__).resolve().parents[2]
        self._config_path = self._server_root / "finance_signals" / "financial_config.yaml"

    def get_dashboard_state(self) -> FinanceSignalsData:
        status_path = self._resolve_status_path()
        alert_hints = self._load_alert_hints()
        if not status_path.exists():
            return FinanceSignalsData(
                update_time="",
                news_last_fetch_time="",
                news_stale=False,
                watchlist_preview=[],
                top_news=[],
                watchlist_ntfy_enabled=self.get_watchlist_ntfy_enabled(),
                ai_insight_text="财经信号尚未初始化，请先启动 finance_signals 任务。",
                news_debug=FinanceNewsDebugData(),
                market_alert_debug=FinanceMarketAlertDebugData(),
            )

        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="Finance Signals 状态文件解析失败。",
                status_code=502,
                details={"error": str(exc), "path": str(status_path)},
            ) from exc
        if not isinstance(payload, dict):
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="Finance Signals 状态文件格式非法。",
                status_code=502,
                details={"path": str(status_path), "type": type(payload).__name__},
            )

        watchlist_raw = payload.get("watchlist_preview") or []
        watchlist: list[FinanceWatchlistItem] = []
        if isinstance(watchlist_raw, list):
            for item in watchlist_raw:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol", "")).strip()
                if not symbol:
                    continue
                name = str(item.get("name", "")).strip()
                change_pct = str(item.get("change_pct", "N/A")).strip() or "N/A"
                raw_price = item.get("price")
                price_value: float | None
                if raw_price is None:
                    price_value = None
                else:
                    try:
                        price_value = float(raw_price)
                    except (TypeError, ValueError):
                        price_value = None
                watchlist.append(
                    FinanceWatchlistItem(
                        name=name,
                        symbol=symbol,
                        price=price_value,
                        change_pct=change_pct,
                        alert_hint=alert_hints.get(symbol, ""),
                        alert_active=bool(item.get("alert_active", False)),
                    )
                )

        top_news_raw = payload.get("top_news") or []
        top_news: list[FinanceNewsItem] = []
        if isinstance(top_news_raw, list):
            for item in top_news_raw:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                if not title:
                    continue
                top_news.append(
                    FinanceNewsItem(
                        title=title,
                        link=str(item.get("link", "")).strip(),
                        publisher=str(item.get("publisher", "")).strip(),
                        published=str(item.get("published", "")).strip(),
                        category=str(item.get("category", "")).strip(),
                        matched_keywords=self._safe_str_list(item.get("matched_keywords")),
                    )
                )

        ai_insight_text = str(payload.get("ai_insight_text", "")).strip()

        news_last_fetch_time = str(payload.get("news_last_fetch_time", "")).strip()
        news_debug_raw = payload.get("news_debug")
        news_debug = FinanceNewsDebugData()
        if isinstance(news_debug_raw, dict):
            news_debug = FinanceNewsDebugData(
                entries_scanned=self._safe_int(news_debug_raw.get("entries_scanned")),
                entries_filtered_by_source=self._safe_int(
                    news_debug_raw.get("entries_filtered_by_source")
                ),
                matched_entries_count=self._safe_int(
                    news_debug_raw.get("matched_entries_count")
                ),
                top_news_count=self._safe_int(news_debug_raw.get("top_news_count")),
                digest_item_count=self._safe_int(news_debug_raw.get("digest_item_count")),
                digest_prompt_chars=self._safe_int(
                    news_debug_raw.get("digest_prompt_chars")
                ),
                digest_status=str(news_debug_raw.get("digest_status", "")).strip(),
                digest_last_generated_at=str(
                    news_debug_raw.get("digest_last_generated_at", "")
                ).strip(),
                top_unmatched_titles=self._safe_str_list(
                    news_debug_raw.get("top_unmatched_titles")
                ),
            )
        market_alert_debug_raw = payload.get("market_alert_debug")
        market_alert_debug = FinanceMarketAlertDebugData()
        if isinstance(market_alert_debug_raw, dict):
            market_alert_debug = FinanceMarketAlertDebugData(
                alert_enabled=bool(market_alert_debug_raw.get("enabled", False)),
                alert_sent=bool(market_alert_debug_raw.get("sent", False)),
                last_alert_time=str(
                    market_alert_debug_raw.get("last_alert_time", "")
                ).strip(),
                last_alert_signature=str(
                    market_alert_debug_raw.get("last_alert_signature", "")
                ).strip(),
                last_alert_summary=str(
                    market_alert_debug_raw.get("last_alert_summary", "")
                ).strip(),
                last_alert_status=str(
                    market_alert_debug_raw.get("last_alert_status", "")
                ).strip(),
            )

        return FinanceSignalsData(
            update_time=str(payload.get("update_time", "")).strip(),
            news_last_fetch_time=news_last_fetch_time,
            news_stale=self._compute_news_stale(news_last_fetch_time),
            watchlist_preview=watchlist,
            top_news=top_news,
            watchlist_ntfy_enabled=bool(
                payload.get("watchlist_ntfy_enabled", self.get_watchlist_ntfy_enabled())
            ),
            ai_insight_text=ai_insight_text,
            news_debug=news_debug,
            market_alert_debug=market_alert_debug,
        )

    async def trigger_news_digest(self) -> FinanceSignalsData:
        config = worker_main.load_config(self._config_path)
        news_result = await worker_main.run_news_job(config)
        fetch_time = worker_main.now_text(config)
        digest_state = await worker_main.generate_news_digest(
            config=config,
            digest_items=list(news_result.get("digest_candidates", [])),
        )

        status_path = self._resolve_status_path()
        existing_payload = self._load_status_payload(status_path)
        news_debug = dict(
            news_result.get(
                "debug",
                {
                    "entries_scanned": 0,
                    "entries_filtered_by_source": 0,
                    "matched_entries_count": 0,
                    "top_news_count": 0,
                    "digest_item_count": 0,
                    "digest_prompt_chars": 0,
                    "digest_status": "",
                    "digest_last_generated_at": "",
                    "top_unmatched_titles": [],
                },
            )
        )
        news_debug["digest_prompt_chars"] = int(digest_state.get("prompt_chars", 0))
        news_debug["digest_item_count"] = int(digest_state.get("item_count", 0))
        news_debug["digest_status"] = str(digest_state.get("status", "")).strip()
        news_debug["digest_last_generated_at"] = str(
            digest_state.get("generated_at", "")
        ).strip()

        payload = {
            "update_time": fetch_time,
            "news_last_fetch_time": fetch_time,
            "watchlist_preview": existing_payload.get("watchlist_preview", []),
            "top_news": news_result.get("top_news", []),
            "watchlist_ntfy_enabled": bool(
                existing_payload.get("watchlist_ntfy_enabled", self.get_watchlist_ntfy_enabled())
            ),
            "ai_insight_text": str(digest_state.get("text", "")).strip(),
            "news_debug": news_debug,
            "market_alert_debug": existing_payload.get(
                "market_alert_debug",
                {
                    "enabled": False,
                    "sent": False,
                    "last_alert_time": "",
                    "last_alert_signature": "",
                    "last_alert_summary": "",
                    "last_alert_status": "",
                },
            ),
        }
        output_cfg = config.get("output", {})
        indent = int(output_cfg.get("json_indent", 2))
        ensure_ascii = bool(output_cfg.get("ensure_ascii", False))
        worker_main.write_json_atomic_sync(
            target_path=status_path,
            payload=payload,
            indent=indent,
            ensure_ascii=ensure_ascii,
        )
        return self.get_dashboard_state()

    def get_watchlist_ntfy_enabled(self) -> bool:
        cfg = self._load_config()
        market_data = cfg.get("market_data")
        if not isinstance(market_data, dict):
            return False
        alerting = market_data.get("alerting")
        if not isinstance(alerting, dict):
            return False
        return bool(alerting.get("enabled", False))

    def set_watchlist_ntfy_enabled(self, enabled: bool) -> bool:
        with _CONFIG_WRITE_LOCK:
            raw = self._load_config()
            market_data = raw.get("market_data")
            if not isinstance(market_data, dict):
                market_data = {}
                raw["market_data"] = market_data
            alerting = market_data.get("alerting")
            if not isinstance(alerting, dict):
                alerting = {}
                market_data["alerting"] = alerting
            alerting["enabled"] = bool(enabled)
            self._write_yaml(self._config_path, raw)
        return bool(enabled)

    def _resolve_status_path(self) -> Path:
        status_file = "finance_status.json"
        config_dir = self._config_path.parent

        if self._config_path.exists():
            try:
                cfg = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
                output_cfg = cfg.get("output")
                if isinstance(output_cfg, dict):
                    configured = str(output_cfg.get("status_file", "")).strip()
                    if configured:
                        status_file = configured
            except Exception:
                pass

        raw_path = Path(status_file)
        if raw_path.is_absolute():
            return raw_path
        return (config_dir / raw_path).resolve()

    def _load_status_payload(self, status_path: Path) -> dict[str, Any]:
        if not status_path.exists():
            return {}
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="Finance Signals 状态文件解析失败。",
                status_code=502,
                details={"error": str(exc), "path": str(status_path)},
            ) from exc
        if not isinstance(payload, dict):
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="Finance Signals 状态文件格式非法。",
                status_code=502,
                details={"path": str(status_path), "type": type(payload).__name__},
            )
        return payload

    def _load_alert_hints(self) -> dict[str, str]:
        cfg = self._load_config()
        market_data = cfg.get("market_data")
        if not isinstance(market_data, dict):
            return {}
        instruments = market_data.get("instruments")
        if not isinstance(instruments, list):
            return {}

        hints: dict[str, str] = {}
        for item in instruments:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).strip()
            if not symbol:
                continue
            rule = item.get("rule")
            if not isinstance(rule, dict):
                continue
            hint = self._rule_to_hint(rule)
            if hint:
                hints[symbol] = hint
        return hints

    def _compute_news_stale(self, news_last_fetch_time: str) -> bool:
        if not news_last_fetch_time:
            return True

        stale_after_seconds = 900
        time_format = "%Y-%m-%d %H:%M:%S"
        if self._config_path.exists():
            try:
                cfg = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
                output_cfg = cfg.get("output")
                if isinstance(output_cfg, dict):
                    configured_format = str(output_cfg.get("time_format", "")).strip()
                    if configured_format:
                        time_format = configured_format
                news_cfg = cfg.get("news")
                if isinstance(news_cfg, dict):
                    poll_cfg = news_cfg.get("poll")
                    if isinstance(poll_cfg, dict):
                        configured_stale = poll_cfg.get("stale_after_seconds")
                        if configured_stale is not None:
                            stale_after_seconds = max(int(configured_stale), 1)
            except Exception:
                pass

        try:
            last_dt = datetime.strptime(news_last_fetch_time, time_format)
        except Exception:
            return True
        age_seconds = (datetime.now() - last_dt).total_seconds()
        return age_seconds > stale_after_seconds

    def _safe_int(self, value: Any) -> int:
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 0

    def _safe_str_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        return items

    def _rule_to_hint(self, rule: dict[str, Any]) -> str:
        rule_type = str(rule.get("type", "")).strip()
        threshold_raw = rule.get("threshold")
        if threshold_raw is None:
            return ""
        try:
            threshold = float(threshold_raw)
        except (TypeError, ValueError):
            return ""

        threshold_text = self._format_threshold(threshold)
        if rule_type == "price_gte":
            return f">{threshold_text}"
        if rule_type == "price_lte":
            return f"<={threshold_text}"
        if rule_type == "change_pct_gte":
            return f">={threshold_text}%"
        if rule_type == "change_pct_lte":
            return f"<={threshold_text}%"
        if rule_type == "drawdown_pct_gte":
            return f"回撤>{threshold_text}%"
        if rule_type == "drawdown_pct_lte":
            return f"回撤<={threshold_text}%"
        return ""

    def _format_threshold(self, value: float) -> str:
        rounded = round(value, 4)
        if rounded.is_integer():
            return str(int(rounded))
        return str(rounded)

    def _load_config(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            cfg = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        if not isinstance(cfg, dict):
            return {}
        return cfg

    def _write_yaml(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as fp:
                yaml.safe_dump(payload, fp, allow_unicode=True, sort_keys=False)
                temp_path = Path(fp.name)
            os.replace(str(temp_path), str(path))
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
