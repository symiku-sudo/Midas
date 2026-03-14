from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.core.errors import AppError, ErrorCode
from app.models.schemas import (
    FinanceFocusCard,
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
        watchlist_seed: list[dict[str, Any]] = []
        instrument_aliases = self._load_instrument_aliases()
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
                watchlist_seed.append(
                    {
                        "name": name,
                        "symbol": symbol,
                        "price": price_value,
                        "change_pct": change_pct,
                        "alert_hint": alert_hints.get(symbol, ""),
                        "alert_active": bool(item.get("alert_active", False)),
                        "aliases": instrument_aliases.get(symbol, []),
                    }
                )

        top_news_raw = payload.get("top_news") or []
        top_news_seed: list[dict[str, Any]] = []
        if isinstance(top_news_raw, list):
            for item in top_news_raw:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                if not title:
                    continue
                top_news_seed.append(
                    {
                        "title": title,
                        "link": str(item.get("link", "")).strip(),
                        "publisher": str(item.get("publisher", "")).strip(),
                        "published": str(item.get("published", "")).strip(),
                        "category": str(item.get("category", "")).strip(),
                        "matched_keywords": self._safe_str_list(item.get("matched_keywords")),
                    }
                )

        watchlist, top_news = self._build_watchlist_news_links(
            watchlist_seed=watchlist_seed,
            top_news_seed=top_news_seed,
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
            focus_cards=self._build_focus_cards(
                watchlist=watchlist,
                top_news=top_news,
                market_alert_debug=market_alert_debug,
            ),
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

    def _load_instrument_aliases(self) -> dict[str, list[str]]:
        cfg = self._load_config()
        market_data = cfg.get("market_data")
        if not isinstance(market_data, dict):
            return {}
        instruments = market_data.get("instruments")
        if not isinstance(instruments, list):
            return {}

        aliases_by_symbol: dict[str, list[str]] = {}
        for item in instruments:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).strip()
            if not symbol:
                continue
            aliases_by_symbol[symbol] = self._expand_aliases(
                name=str(item.get("name", "")).strip(),
                symbol=symbol,
                aliases=self._safe_str_list(item.get("aliases")),
            )
        return aliases_by_symbol

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

    def _build_watchlist_news_links(
        self,
        *,
        watchlist_seed: list[dict[str, Any]],
        top_news_seed: list[dict[str, Any]],
    ) -> tuple[list[FinanceWatchlistItem], list[FinanceNewsItem]]:
        watchlist_links: dict[str, dict[str, Any]] = {}
        for item in watchlist_seed:
            symbol = str(item.get("symbol", "")).strip()
            if not symbol:
                continue
            watchlist_links[symbol] = {
                "item": item,
                "aliases": self._expand_aliases(
                    name=str(item.get("name", "")).strip(),
                    symbol=symbol,
                    aliases=self._safe_str_list(item.get("aliases")),
                ),
                "related_titles": [],
                "related_keywords": set(),
            }

        top_news: list[FinanceNewsItem] = []
        for news in top_news_seed:
            title = str(news.get("title", "")).strip()
            matched_keywords = self._safe_str_list(news.get("matched_keywords"))
            related_symbols: list[str] = []
            related_names: list[str] = []
            for symbol, link_data in watchlist_links.items():
                aliases = list(link_data["aliases"])
                if not self._news_matches_watchlist(
                    title=title,
                    matched_keywords=matched_keywords,
                    aliases=aliases,
                ):
                    continue
                related_symbols.append(symbol)
                display_name = str(link_data["item"].get("name", "")).strip() or symbol
                related_names.append(display_name)
                link_data["related_titles"].append(title)
                for keyword in matched_keywords:
                    if self._keyword_matches_aliases(keyword, aliases):
                        link_data["related_keywords"].add(keyword)
            top_news.append(
                FinanceNewsItem(
                    title=title,
                    link=str(news.get("link", "")).strip(),
                    publisher=str(news.get("publisher", "")).strip(),
                    published=str(news.get("published", "")).strip(),
                    category=str(news.get("category", "")).strip(),
                    matched_keywords=matched_keywords,
                    related_symbols=related_symbols,
                    related_watchlist_names=related_names,
                )
            )

        watchlist: list[FinanceWatchlistItem] = []
        for symbol, link_data in watchlist_links.items():
            item = dict(link_data["item"])
            watchlist.append(
                FinanceWatchlistItem(
                    name=str(item.get("name", "")).strip(),
                    symbol=symbol,
                    price=item.get("price"),
                    change_pct=str(item.get("change_pct", "N/A")).strip() or "N/A",
                    alert_hint=str(item.get("alert_hint", "")).strip(),
                    alert_active=bool(item.get("alert_active", False)),
                    related_news_count=len(link_data["related_titles"]),
                    related_keywords=sorted(link_data["related_keywords"]),
                )
            )
        return watchlist, top_news

    def _build_focus_cards(
        self,
        *,
        watchlist: list[FinanceWatchlistItem],
        top_news: list[FinanceNewsItem],
        market_alert_debug: FinanceMarketAlertDebugData,
    ) -> list[FinanceFocusCard]:
        cards: list[FinanceFocusCard] = []
        seen: set[tuple[str, tuple[str, ...], str]] = set()
        watchlist_by_symbol = {item.symbol: item for item in watchlist}

        for item in watchlist:
            if not item.alert_active:
                continue
            related_names = [item.name.strip() or item.symbol]
            related_symbols = [item.symbol]
            title = f"{related_names[0]} 已触发监控阈值"
            summary_parts = [f"阈值条件：{item.alert_hint or '已触发关注条件'}"]
            reasons = ["threshold_triggered"]
            if item.related_news_count > 0:
                summary_parts.append(f"最近关联新闻 {item.related_news_count} 条")
                reasons.append("related_news_present")
            if item.related_keywords:
                summary_parts.append(f"关键词：{' / '.join(item.related_keywords[:3])}")
                reasons.append("keyword_overlap")
            if market_alert_debug.last_alert_time:
                summary_parts.append(f"最近告警：{market_alert_debug.last_alert_time}")
                reasons.append("recent_alert_sent")
            key = ("ALERT", tuple(related_symbols), title)
            if key in seen:
                continue
            seen.add(key)
            cards.append(
                FinanceFocusCard(
                    title=title,
                    summary="；".join(summary_parts),
                    priority="HIGH",
                    kind="ALERT",
                    action_type="REVIEW_NOW",
                    action_label="立即复核",
                    action_hint="先看价格异动和关联新闻，再决定是否提升观察频率。",
                    reasons=reasons,
                    related_symbols=related_symbols,
                    related_watchlist_names=related_names,
                )
            )

        for item in top_news:
            if not item.related_watchlist_names:
                continue
            related_names = item.related_watchlist_names[:3]
            related_symbols = item.related_symbols[:3]
            has_active_alert = any(
                watchlist_by_symbol.get(symbol) is not None
                and bool(watchlist_by_symbol[symbol].alert_active)
                for symbol in related_symbols
            )
            summary_parts = [f"影响标的：{' / '.join(related_names)}"]
            reasons = ["news_impacts_watchlist"]
            if item.matched_keywords:
                summary_parts.append(f"关键词：{' / '.join(item.matched_keywords[:4])}")
                reasons.append("keyword_overlap")
            if item.publisher or item.published:
                meta = " · ".join(value for value in [item.publisher, item.published] if value)
                if meta:
                    summary_parts.append(meta)
            key = ("NEWS", tuple(related_symbols), item.title)
            if key in seen:
                continue
            seen.add(key)
            action_label = "优先跟踪" if len(related_symbols) >= 2 or has_active_alert else "持续跟踪"
            action_hint = (
                "先复核已触发阈值的标的，再看同主题新闻是否继续发酵。"
                if has_active_alert
                else "关注后续同主题新闻和相关标的波动是否继续扩散。"
            )
            if has_active_alert:
                reasons.append("linked_alert_active")
            if len(related_symbols) >= 2:
                reasons.append("multi_asset_impact")
            cards.append(
                FinanceFocusCard(
                    title=item.title,
                    summary="；".join(summary_parts),
                    priority="HIGH" if has_active_alert else "MEDIUM",
                    kind="NEWS",
                    action_type="FOLLOW_UP" if has_active_alert or len(related_symbols) >= 2 else "MONITOR",
                    action_label=action_label,
                    action_hint=action_hint,
                    reasons=reasons,
                    related_symbols=related_symbols,
                    related_watchlist_names=related_names,
                )
            )

        cards.sort(
            key=lambda item: (
                {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(item.priority, 9),
                {"ALERT": 0, "NEWS": 1}.get(item.kind, 9),
                item.title,
            )
        )
        return cards[:4]

    def _expand_aliases(
        self,
        *,
        name: str,
        symbol: str,
        aliases: list[str],
    ) -> list[str]:
        values = [name, symbol, *aliases]
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            candidate = value.strip()
            if not candidate:
                continue
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(candidate)
        return normalized

    def _news_matches_watchlist(
        self,
        *,
        title: str,
        matched_keywords: list[str],
        aliases: list[str],
    ) -> bool:
        for alias in aliases:
            if self._text_matches_alias(alias, title):
                return True
        for keyword in matched_keywords:
            if self._keyword_matches_aliases(keyword, aliases):
                return True
        return False

    def _keyword_matches_aliases(self, keyword: str, aliases: list[str]) -> bool:
        for alias in aliases:
            if self._text_matches_alias(alias, keyword) or self._text_matches_alias(keyword, alias):
                return True
        return False

    def _text_matches_alias(self, alias: str, text: str) -> bool:
        normalized_alias = self._normalize_match_text(alias)
        normalized_text = self._normalize_match_text(text)
        if not normalized_alias or not normalized_text:
            return False
        if len(normalized_alias) <= 2 and self._is_ascii_token(normalized_alias):
            return False
        return normalized_alias in normalized_text

    def _normalize_match_text(self, value: str) -> str:
        return re.sub(r"[\s\-_()/（）·,.，。:：]+", "", value.strip().lower())

    def _is_ascii_token(self, value: str) -> bool:
        return value.isascii()

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
