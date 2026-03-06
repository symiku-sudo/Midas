from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import feedparser
import pandas as pd
import yaml
import yfinance as yf


def load_config(config_path: Path) -> dict[str, Any]:
    """读取 YAML 配置，并记录配置目录用于解析相对输出路径。"""
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError("配置文件格式错误，根节点必须是字典。")
    config["_config_dir"] = str(config_path.parent.resolve())
    return config


def resolve_output_path(config: dict[str, Any]) -> Path:
    """将输出路径解析为绝对路径，避免运行目录变化导致写到错误位置。"""
    raw_path = str(config["output"]["status_file"]).strip()
    path = Path(raw_path)
    if path.is_absolute():
        return path
    config_dir = Path(str(config["_config_dir"]))
    return (config_dir / path).resolve()


def now_text(config: dict[str, Any]) -> str:
    """按配置格式输出当前时间字符串。"""
    time_format = str(config["output"]["time_format"])
    return datetime.now().strftime(time_format)


def format_change_pct(value: float, digits: int) -> str:
    """将涨跌幅格式化为前端可直接展示的百分比字符串。"""
    rounded = round(value, digits)
    if rounded > 0:
        return f"+{rounded}%"
    return f"{rounded}%"


def fetch_symbol_history_sync(
    symbol: str,
    period_days: int,
    interval: str,
) -> pd.DataFrame:
    """同步拉取单个标的历史行情（会在线程池中执行）。"""
    ticker = yf.Ticker(symbol)
    return ticker.history(period=f"{period_days}d", interval=interval, auto_adjust=False)


def evaluate_rule(
    *,
    rule: dict[str, Any],
    latest_price: float,
    change_pct: float,
    close_series: pd.Series,
    default_drawdown_lookback_days: int,
) -> tuple[bool, str]:
    """根据配置规则判断是否触发报警，并返回报警文案。"""
    rule_type = str(rule.get("type", "")).strip()
    threshold = float(rule.get("threshold", 0))
    description = str(rule.get("description", "")).strip()

    if rule_type == "price_gte":
        triggered = latest_price >= threshold
        detail = f"当前 {latest_price:.2f} >= 阈值 {threshold:.2f}"
        return triggered, f"{description}（{detail}）"

    if rule_type == "change_pct_lte":
        triggered = change_pct <= threshold
        detail = f"当前涨跌幅 {change_pct:.2f}% <= 阈值 {threshold:.2f}%"
        return triggered, f"{description}（{detail}）"

    if rule_type == "drawdown_pct_gte":
        lookback_days = int(rule.get("lookback_days", default_drawdown_lookback_days))
        recent = close_series.tail(lookback_days)
        if recent.empty:
            return False, f"{description}（缺少回撤计算样本）"
        recent_high = float(recent.max())
        if recent_high <= 0:
            return False, f"{description}（阶段高点无效）"
        drawdown_pct = (recent_high - latest_price) / recent_high * 100
        triggered = drawdown_pct >= threshold
        detail = f"当前回撤 {drawdown_pct:.2f}% >= 阈值 {threshold:.2f}%"
        return triggered, f"{description}（{detail}）"

    return False, f"未知规则类型：{rule_type}"


async def run_market_job(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """
    行情任务：
    1) 拉取 watchlist 中每个标的
    2) 计算最新价格与单日涨跌幅
    3) 按配置规则判断是否触发报警
    """
    market_cfg = config["market_data"]
    period_days = int(market_cfg["history_period_days"])
    interval = str(market_cfg["history_interval"])
    price_digits = int(market_cfg["price_round_digits"])
    change_digits = int(market_cfg["change_round_digits"])
    default_drawdown_lookback_days = int(market_cfg["default_drawdown_lookback_days"])

    watchlist_preview: list[dict[str, Any]] = []
    market_alerts: list[str] = []

    for item in market_cfg["instruments"]:
        name = str(item["name"])
        symbol = str(item["symbol"])
        rule = dict(item["rule"])

        try:
            history = await asyncio.to_thread(
                fetch_symbol_history_sync,
                symbol,
                period_days,
                interval,
            )
            if history.empty or "Close" not in history.columns:
                watchlist_preview.append(
                    {
                        "name": name,
                        "symbol": symbol,
                        "price": None,
                        "change_pct": "N/A",
                    }
                )
                market_alerts.append(f"{name}（{symbol}）行情拉取为空。")
                continue

            close_series = history["Close"].dropna()
            if close_series.empty:
                watchlist_preview.append(
                    {
                        "name": name,
                        "symbol": symbol,
                        "price": None,
                        "change_pct": "N/A",
                    }
                )
                market_alerts.append(f"{name}（{symbol}）缺少收盘价数据。")
                continue

            latest_price = float(close_series.iloc[-1])
            prev_close = (
                float(close_series.iloc[-2]) if len(close_series) >= 2 else float(close_series.iloc[-1])
            )
            change_pct = 0.0
            if prev_close != 0:
                change_pct = (latest_price - prev_close) / prev_close * 100

            watchlist_preview.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "price": round(latest_price, price_digits),
                    "change_pct": format_change_pct(change_pct, change_digits),
                }
            )

            triggered, alert_text = evaluate_rule(
                rule=rule,
                latest_price=latest_price,
                change_pct=change_pct,
                close_series=close_series,
                default_drawdown_lookback_days=default_drawdown_lookback_days,
            )
            if triggered:
                market_alerts.append(f"{name}（{symbol}）触发：{alert_text}")
        except Exception as exc:  # noqa: BLE001
            watchlist_preview.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "price": None,
                    "change_pct": "N/A",
                }
            )
            market_alerts.append(f"{name}（{symbol}）抓取异常：{exc}")

    return watchlist_preview, market_alerts


def parse_feed_sync(url: str) -> Any:
    """同步解析 RSS（会在线程池中执行）。"""
    return feedparser.parse(url)


def _is_negated_hit(text: str, key: str, negation_prefixes: list[str]) -> bool:
    for raw_neg in negation_prefixes:
        neg = str(raw_neg).strip().lower()
        if not neg:
            continue
        if f"{neg}{key}" in text:
            return True
        pattern = rf"{re.escape(neg)}[\s\"'“”‘’,，:：\-—（）()]{0,3}{re.escape(key)}"
        if re.search(pattern, text):
            return True
    return False


def collect_negated_keywords(
    text: str,
    keywords: list[str],
    *,
    negation_prefixes: list[str],
) -> set[str]:
    text_lower = text.lower()
    negated: set[str] = set()
    for word in keywords:
        key = str(word).strip()
        if not key:
            continue
        key_lower = key.lower()
        if key_lower in text_lower and _is_negated_hit(
            text_lower, key_lower, negation_prefixes
        ):
            negated.add(key)
    return negated


def match_keywords(
    text: str,
    keywords: list[str],
    *,
    negation_prefixes: list[str] | None = None,
) -> list[str]:
    """关键词匹配：命中即返回；若命中否定前缀则忽略该关键词。"""
    text_lower = text.lower()
    negation_prefixes = negation_prefixes or []
    matched: list[str] = []
    for word in keywords:
        key = str(word).strip()
        if not key:
            continue
        key_lower = key.lower()
        if key_lower in text_lower and not _is_negated_hit(
            text_lower, key_lower, negation_prefixes
        ):
            matched.append(key)
    return matched


async def run_news_job(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """
    舆情任务：
    1) 拉取配置中的 RSS 源
    2) 用危机升级/降温关键词进行匹配
    3) 返回命中结果供 AI Insight 组装
    """
    news_cfg = config["news"]
    sources = news_cfg["sources"]
    poll_cfg = news_cfg["poll"]
    max_items_per_source = int(poll_cfg["max_items_per_source"])
    max_matched_items = int(poll_cfg["max_matched_items"])

    keywords_cfg = news_cfg["keywords"]
    crisis_up_words = list(keywords_cfg["crisis_up"])
    crisis_down_words = list(keywords_cfg["crisis_down"])
    exclude_title_words = list(keywords_cfg.get("exclude_title_if_contains", []))
    negation_prefixes = list(keywords_cfg.get("negation_prefixes", []))

    result: dict[str, list[dict[str, Any]]] = {
        "crisis_up_hits": [],
        "crisis_down_hits": [],
    }

    for source in sources:
        source_name = str(source["name"])
        source_url = str(source["url"])
        try:
            feed = await asyncio.to_thread(parse_feed_sync, source_url)
            entries = list(feed.entries)[:max_items_per_source]
            for entry in entries:
                title = str(entry.get("title", "")).strip()
                summary = str(entry.get("summary", "")).strip()
                link = str(entry.get("link", "")).strip()
                published = str(entry.get("published", "")).strip()
                if match_keywords(title, exclude_title_words):
                    continue
                text = f"{title} {summary}".strip()

                up_matched = match_keywords(
                    text,
                    crisis_up_words,
                    negation_prefixes=negation_prefixes,
                )
                down_matched = match_keywords(
                    text,
                    crisis_down_words,
                    negation_prefixes=negation_prefixes,
                )
                title_negated_up = collect_negated_keywords(
                    title,
                    crisis_up_words,
                    negation_prefixes=negation_prefixes,
                )
                if title_negated_up:
                    up_matched = [key for key in up_matched if key not in title_negated_up]
                title_negated_down = collect_negated_keywords(
                    title,
                    crisis_down_words,
                    negation_prefixes=negation_prefixes,
                )
                if title_negated_down:
                    down_matched = [
                        key for key in down_matched if key not in title_negated_down
                    ]

                if up_matched:
                    result["crisis_up_hits"].append(
                        {
                            "source": source_name,
                            "title": title,
                            "link": link,
                            "published": published,
                            "matched_keywords": up_matched,
                        }
                    )
                elif down_matched:
                    result["crisis_down_hits"].append(
                        {
                            "source": source_name,
                            "title": title,
                            "link": link,
                            "published": published,
                            "matched_keywords": down_matched,
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            result["crisis_up_hits"].append(
                {
                    "source": source_name,
                    "title": f"RSS 拉取异常：{exc}",
                    "link": source_url,
                    "published": "",
                    "matched_keywords": [],
                }
            )

    result["crisis_up_hits"] = result["crisis_up_hits"][:max_matched_items]
    result["crisis_down_hits"] = result["crisis_down_hits"][:max_matched_items]
    return result


def build_ai_insight_text(
    *,
    config: dict[str, Any],
    market_alerts: list[str],
    news_hits: dict[str, list[dict[str, Any]]],
) -> str:
    """将行情报警与舆情命中组装成前端可直接展示的摘要文本。"""
    ai_cfg = config["ai_insight"]
    safe_text = str(ai_cfg["safe_text"])
    sep = str(ai_cfg["section_separator"])
    max_market_alerts = int(ai_cfg["max_market_alerts_in_text"])
    max_news_items = int(ai_cfg["max_news_items_in_text"])

    sections: list[str] = []

    if market_alerts:
        market_text = "；".join(market_alerts[:max_market_alerts])
        sections.append(f"行情警报：{market_text}")

    crisis_up_hits = news_hits.get("crisis_up_hits", [])
    crisis_down_hits = news_hits.get("crisis_down_hits", [])

    if crisis_up_hits:
        picked = crisis_up_hits[:max_news_items]
        news_text = "；".join(
            f"《{item['title']}》命中[{','.join(item['matched_keywords'])}]"
            for item in picked
        )
        sections.append(f"舆情高危：{news_text}")
    elif crisis_down_hits:
        picked = crisis_down_hits[:max_news_items]
        news_text = "；".join(
            f"《{item['title']}》命中[{','.join(item['matched_keywords'])}]"
            for item in picked
        )
        sections.append(f"舆情降温：{news_text}")

    if not sections:
        return safe_text
    return sep.join(sections)


def write_json_atomic_sync(
    *,
    target_path: Path,
    payload: dict[str, Any],
    indent: int,
    ensure_ascii: bool,
) -> None:
    """原子写入 JSON，避免并发覆盖导致半文件。"""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=ensure_ascii, indent=indent)
    os.replace(temp_path, target_path)


async def update_dashboard_state(
    *,
    config: dict[str, Any],
    shared_state: dict[str, Any],
    file_lock: asyncio.Lock,
) -> None:
    """
    统一输出前端绑定 JSON。
    Key 必须与前端占位卡片严格对应：
    - update_time
    - watchlist_preview
    - ai_insight_text
    """
    payload = {
        "update_time": now_text(config),
        "watchlist_preview": shared_state.get("watchlist_preview", []),
        "ai_insight_text": build_ai_insight_text(
            config=config,
            market_alerts=shared_state.get("market_alerts", []),
            news_hits=shared_state.get(
                "news_hits",
                {"crisis_up_hits": [], "crisis_down_hits": []},
            ),
        ),
    }

    output_path = resolve_output_path(config)
    indent = int(config["output"]["json_indent"])
    ensure_ascii = bool(config["output"]["ensure_ascii"])

    async with file_lock:
        await asyncio.to_thread(
            write_json_atomic_sync,
            target_path=output_path,
            payload=payload,
            indent=indent,
            ensure_ascii=ensure_ascii,
        )


async def market_loop(
    *,
    config: dict[str, Any],
    shared_state: dict[str, Any],
    state_lock: asyncio.Lock,
    file_lock: asyncio.Lock,
) -> None:
    """行情定时任务主循环。"""
    interval = int(config["scheduler"]["market_interval_seconds"])
    while True:
        try:
            watchlist_preview, market_alerts = await run_market_job(config)
            async with state_lock:
                shared_state["watchlist_preview"] = watchlist_preview
                shared_state["market_alerts"] = market_alerts
            await update_dashboard_state(config=config, shared_state=shared_state, file_lock=file_lock)
        except Exception as exc:  # noqa: BLE001
            async with state_lock:
                shared_state["market_alerts"] = [f"行情任务异常：{exc}"]
            await update_dashboard_state(config=config, shared_state=shared_state, file_lock=file_lock)
        await asyncio.sleep(interval)


async def news_loop(
    *,
    config: dict[str, Any],
    shared_state: dict[str, Any],
    state_lock: asyncio.Lock,
    file_lock: asyncio.Lock,
) -> None:
    """新闻定时任务主循环。"""
    interval = int(config["scheduler"]["news_interval_seconds"])
    while True:
        try:
            news_hits = await run_news_job(config)
            async with state_lock:
                shared_state["news_hits"] = news_hits
            await update_dashboard_state(config=config, shared_state=shared_state, file_lock=file_lock)
        except Exception as exc:  # noqa: BLE001
            async with state_lock:
                shared_state["news_hits"] = {
                    "crisis_up_hits": [
                        {
                            "source": "news_loop",
                            "title": f"新闻任务异常：{exc}",
                            "link": "",
                            "published": "",
                            "matched_keywords": [],
                        }
                    ],
                    "crisis_down_hits": [],
                }
            await update_dashboard_state(config=config, shared_state=shared_state, file_lock=file_lock)
        await asyncio.sleep(interval)


async def main() -> None:
    """程序入口：并发启动行情与舆情任务。"""
    config_path = Path(__file__).with_name("financial_config.yaml")
    config = load_config(config_path)

    shared_state: dict[str, Any] = {
        "watchlist_preview": [],
        "market_alerts": [],
        "news_hits": {"crisis_up_hits": [], "crisis_down_hits": []},
    }
    state_lock = asyncio.Lock()
    file_lock = asyncio.Lock()

    # 启动时先输出一次默认状态，避免前端首次读取文件为空。
    await update_dashboard_state(config=config, shared_state=shared_state, file_lock=file_lock)

    await asyncio.gather(
        market_loop(
            config=config,
            shared_state=shared_state,
            state_lock=state_lock,
            file_lock=file_lock,
        ),
        news_loop(
            config=config,
            shared_state=shared_state,
            state_lock=state_lock,
            file_lock=file_lock,
        ),
    )


if __name__ == "__main__":
    asyncio.run(main())
