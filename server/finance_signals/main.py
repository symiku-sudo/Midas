from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import pow
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


def parse_published_datetime(value: str) -> datetime | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        published_dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if published_dt.tzinfo is None:
        return published_dt.replace(tzinfo=timezone.utc)
    return published_dt.astimezone(timezone.utc)


def normalize_title_key(title: str) -> str:
    text = str(title).strip().lower()
    if not text:
        return ""
    text = re.sub(r"\s+-\s+[^-]+$", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
    return text


def normalize_source_label(value: str) -> str:
    return str(value).strip().lower()


def extract_link_domain(link: str) -> str:
    match = re.search(r"https?://([^/]+)", str(link).strip(), re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).lower()


def extract_publisher_label(*, source_name: str, title: str, link: str) -> str:
    title_text = str(title).strip()
    parts = [part.strip() for part in re.split(r"\s+-\s+", title_text) if part.strip()]
    if len(parts) >= 2:
        return parts[-1]

    source_text = str(source_name).strip()
    if source_text:
        return source_text

    match = re.search(r"https?://([^/]+)", str(link).strip(), re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return ""


def strip_topic_prefix(title: str) -> str:
    text = str(title).strip()
    text = re.sub(r"\s+-\s+[^-]+$", "", text)
    prefix_patterns = [
        r"^[^:：|丨]{0,18}[|丨:：]\s*",
        r"^(两会|新华社消息|中国发布|国际观察|观察者网|新华社快讯)[·•]?",
    ]
    for pattern in prefix_patterns:
        text = re.sub(pattern, "", text)
    return text.strip("“”\"' ")


def build_topic_key(title: str, matched_keywords: list[str]) -> str:
    topic_text = strip_topic_prefix(title).lower()
    topic_text = re.sub(r"[^\w\u4e00-\u9fff]+", "", topic_text)
    topic_text = re.sub(r"(最新|快讯|消息|局势|报道|观察)$", "", topic_text)
    if len(topic_text) > 28:
        topic_text = topic_text[:28]
    keywords_key = ",".join(sorted({str(keyword).strip().lower() for keyword in matched_keywords if str(keyword).strip()}))
    return f"{topic_text}|{keywords_key}".strip("|")


TOPIC_STOPWORDS = {
    "最新",
    "快讯",
    "消息",
    "局势",
    "报道",
    "观察",
    "记者会",
    "记者",
    "外长",
    "两会",
    "新华社",
    "新华网",
    "中国网",
    "观察者",
    "观察者网",
    "人民网",
    "国际",
    "美国",
    "伊朗",
    "以色列",
}


def build_topic_tokens(title: str, matched_keywords: list[str]) -> set[str]:
    raw = strip_topic_prefix(title).lower()
    raw = re.sub(r"\s+-\s+[^-]+$", "", raw)
    chunks = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{3,}", raw)
    tokens: set[str] = set()
    for chunk in chunks:
        value = chunk.strip()
        if not value or value in TOPIC_STOPWORDS:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", value):
            if len(value) <= 4:
                tokens.add(value)
            else:
                for size in (2, 3, 4):
                    for index in range(0, len(value) - size + 1):
                        part = value[index : index + size]
                        if part not in TOPIC_STOPWORDS:
                            tokens.add(part)
        else:
            tokens.add(value)
    for keyword in matched_keywords:
        value = str(keyword).strip().lower()
        if value:
            tokens.add(value)
    return tokens


def topic_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    if union == 0:
        return 0.0
    return intersection / union


def should_keep_source(
    *,
    publisher: str,
    domain: str,
    filters_cfg: dict[str, Any],
) -> bool:
    allowlist = {
        normalize_source_label(item)
        for item in filters_cfg.get("source_allowlist", [])
        if str(item).strip()
    }
    blocklist = {
        normalize_source_label(item)
        for item in filters_cfg.get("source_blocklist", [])
        if str(item).strip()
    }
    domain_allowlist = {
        normalize_source_label(item)
        for item in filters_cfg.get("domain_allowlist", [])
        if str(item).strip()
    }
    domain_blocklist = {
        normalize_source_label(item)
        for item in filters_cfg.get("domain_blocklist", [])
        if str(item).strip()
    }

    publisher_norm = normalize_source_label(publisher)
    domain_norm = normalize_source_label(domain)

    if publisher_norm in blocklist or domain_norm in domain_blocklist:
        return False
    if allowlist and publisher_norm not in allowlist:
        return False
    if domain_allowlist and domain_norm not in domain_allowlist:
        return False
    return True


def should_keep_recent_item(
    *,
    published_dt: datetime | None,
    now_utc: datetime,
    max_age_hours: int,
    allow_missing_published: bool,
) -> bool:
    if published_dt is None:
        return allow_missing_published
    age_seconds = max((now_utc - published_dt).total_seconds(), 0.0)
    return age_seconds <= max_age_hours * 3600


def compute_news_hit_score(
    *,
    title: str,
    matched_keywords: list[str],
    hit_kind: str,
    published_dt: datetime | None,
    now_utc: datetime,
    ranking_cfg: dict[str, Any],
    source_name: str,
    link: str,
) -> tuple[float, float | None]:
    half_life_hours = max(float(ranking_cfg.get("recency_half_life_hours", 12)), 1.0)
    default_keyword_score = float(ranking_cfg.get("default_keyword_score", 12))
    title_keyword_bonus = float(ranking_cfg.get("title_keyword_bonus", 8))
    missing_timestamp_multiplier = float(
        ranking_cfg.get("missing_timestamp_multiplier", 0.7)
    )
    keyword_weights = ranking_cfg.get("keyword_weights")
    if not isinstance(keyword_weights, dict):
        keyword_weights = {}
    source_weights = ranking_cfg.get("source_weights")
    if not isinstance(source_weights, dict):
        source_weights = {}
    publisher = extract_publisher_label(source_name=source_name, title=title, link=link)

    if hit_kind == "crisis_up":
        base_score = float(ranking_cfg.get("crisis_up_base_score", 100))
    else:
        base_score = float(ranking_cfg.get("crisis_down_base_score", 40))

    title_lower = title.lower()
    keyword_score = 0.0
    for keyword in matched_keywords:
        keyword_score += float(keyword_weights.get(keyword, default_keyword_score))
        if keyword.lower() in title_lower:
            keyword_score += title_keyword_bonus

    source_score = float(source_weights.get(publisher, 0.0))
    raw_score = base_score + keyword_score + source_score
    if published_dt is None:
        return raw_score * missing_timestamp_multiplier, None

    age_hours = max((now_utc - published_dt).total_seconds(), 0.0) / 3600
    recency_multiplier = pow(0.5, age_hours / half_life_hours)
    return raw_score * recency_multiplier, age_hours


def dedupe_and_sort_news_hits(
    hits: list[dict[str, Any]],
    *,
    max_items: int,
    similarity_threshold: float,
) -> list[dict[str, Any]]:
    sorted_hits = sorted(
        hits,
        key=lambda item: (
            -float(item.get("score", 0.0)),
            -float(item.get("published_ts", 0.0)),
            str(item.get("title", "")),
        ),
    )
    picked: list[dict[str, Any]] = []
    for item in sorted_hits:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        current_tokens = item.get("topic_tokens")
        if not isinstance(current_tokens, set):
            current_tokens = set()
        topic_key = str(item.get("topic_key", "")).strip() or normalize_title_key(title) or title
        duplicate = False
        for chosen in picked:
            chosen_key = str(chosen.get("topic_key", "")).strip()
            chosen_tokens = chosen.get("topic_tokens")
            if not isinstance(chosen_tokens, set):
                chosen_tokens = set()
            if topic_key and chosen_key and topic_key == chosen_key:
                duplicate = True
                break
            if current_tokens and chosen_tokens:
                if topic_similarity(current_tokens, chosen_tokens) >= similarity_threshold:
                    duplicate = True
                    break
        if duplicate:
            continue
        picked.append(item)
        if len(picked) >= max_items:
            break
    return picked


def dedupe_titles(titles: list[dict[str, Any]], *, max_items: int) -> list[str]:
    picked: list[tuple[float, str]] = []
    seen: set[str] = set()
    for item in sorted(
        titles,
        key=lambda current: (
            -float(current.get("published_ts", 0.0)),
            str(current.get("title", "")),
        ),
    ):
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        key = normalize_title_key(title) or title
        if key in seen:
            continue
        seen.add(key)
        picked.append((float(item.get("published_ts", 0.0)), title))
        if len(picked) >= max_items:
            break
    return [title for _, title in picked]


def resolve_config_relative_path(config: dict[str, Any], raw_path: str) -> Path:
    path = Path(str(raw_path).strip())
    if path.is_absolute():
        return path
    config_dir = Path(str(config["_config_dir"]))
    return (config_dir / path).resolve()


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def build_high_risk_alert_payload(
    *,
    config: dict[str, Any],
    news_hits: dict[str, Any],
) -> dict[str, Any] | None:
    alerting_cfg = config.get("news", {}).get("alerting")
    if not isinstance(alerting_cfg, dict) or not bool(alerting_cfg.get("enabled", False)):
        return None

    up_hits = list(news_hits.get("crisis_up_hits", []))
    if not up_hits:
        return None

    min_high_risk_score = float(alerting_cfg.get("min_high_risk_score", 140))
    min_high_risk_hits = max(int(alerting_cfg.get("min_high_risk_hits", 2)), 1)
    max_items = max(int(alerting_cfg.get("max_items_in_notification", 3)), 1)

    qualifying_hits = [
        item for item in up_hits if float(item.get("score", 0.0)) >= min_high_risk_score
    ]
    if len(qualifying_hits) < min_high_risk_hits:
        return None

    picked = qualifying_hits[:max_items]
    # Use a stable topic-only signature so score jitter or ordering changes
    # within the same news cycle do not trigger duplicate notifications.
    signature_topics = sorted(
        {
            str(item.get("topic_key", "")).strip() or str(item.get("title", "")).strip()
            for item in picked
            if str(item.get("topic_key", "")).strip() or str(item.get("title", "")).strip()
        }
    )
    signature = "|".join(signature_topics)
    summary = "；".join(
        f"{item['title']} [score={round(float(item.get('score', 0.0)), 1)}]"
        for item in picked
    )
    return {
        "signature": signature,
        "summary": summary,
        "notification_summary": f"高危舆情触发：score={round(float(picked[0].get('score', 0.0)), 2)} hits={len(qualifying_hits)}",
        "picked_hits": picked,
        "top_score": round(float(picked[0].get("score", 0.0)), 2),
        "hit_count": len(qualifying_hits),
    }


def build_market_alert_payload(
    *,
    config: dict[str, Any],
    market_alerts: list[str],
) -> dict[str, Any] | None:
    alerting_cfg = config.get("market_data", {}).get("alerting")
    if not isinstance(alerting_cfg, dict) or not bool(alerting_cfg.get("enabled", False)):
        return None

    min_market_alerts = max(int(alerting_cfg.get("min_market_alerts", 1)), 1)
    if len(market_alerts) < min_market_alerts:
        return None

    max_items = max(int(alerting_cfg.get("max_items_in_notification", 3)), 1)
    picked = market_alerts[:max_items]
    signature = "|".join(picked)
    summary = "；".join(picked)
    return {
        "signature": signature,
        "summary": summary,
        "notification_summary": f"Watchlist 行情阈值触发：alerts={len(market_alerts)}",
        "alert_count": len(market_alerts),
    }


def deliver_alert_notification(
    *,
    config: dict[str, Any],
    alerting_cfg: dict[str, Any] | None,
    alert_payload: dict[str, Any] | None,
    fetch_time: str,
    default_state_file: str,
    default_task_name: str,
) -> dict[str, Any]:
    base_status = {
        "enabled": False,
        "sent": False,
        "last_alert_time": "",
        "last_alert_signature": "",
        "last_alert_summary": "",
        "last_alert_status": "disabled",
    }
    if not isinstance(alerting_cfg, dict) or not bool(alerting_cfg.get("enabled", False)):
        return base_status
    base_status["enabled"] = True

    if alert_payload is None:
        base_status["last_alert_status"] = "threshold_not_met"
        return base_status

    state_path = resolve_config_relative_path(
        config,
        str(alerting_cfg.get("state_file", default_state_file)),
    )
    state = load_json_file(state_path)
    cooldown_seconds = max(int(alerting_cfg.get("cooldown_seconds", 1800)), 0)
    last_signature = str(state.get("last_alert_signature", "")).strip()
    last_alert_time = str(state.get("last_alert_time", "")).strip()
    base_status["last_alert_signature"] = last_signature
    base_status["last_alert_time"] = last_alert_time
    base_status["last_alert_summary"] = str(state.get("last_alert_summary", "")).strip()

    if last_signature == alert_payload["signature"] and last_alert_time:
        time_format = str(config["output"]["time_format"])
        try:
            last_dt = datetime.strptime(last_alert_time, time_format)
        except Exception:
            last_dt = None
        if last_dt is not None:
            age_seconds = max((datetime.now() - last_dt).total_seconds(), 0.0)
            if age_seconds < cooldown_seconds:
                base_status["last_alert_status"] = "cooldown_skip"
                return base_status

    notify_script = alerting_cfg.get("notify_script")
    if notify_script:
        notify_script_path = resolve_config_relative_path(config, str(notify_script))
    else:
        notify_script_path = Path(__file__).resolve().parents[2] / "tools" / "ntfy_notify.sh"
    ntfy_config_file = resolve_config_relative_path(
        config,
        str(alerting_cfg.get("ntfy_config_file", "../../.tmp/ntfy/notify.env")),
    )

    if not notify_script_path.exists() or not ntfy_config_file.exists():
        base_status["last_alert_status"] = "notify_not_configured"
        return base_status

    task_name = str(alerting_cfg.get("task_name", default_task_name)).strip()
    command = [
        str(notify_script_path),
        "--config",
        str(ntfy_config_file),
        "--task",
        task_name,
        "--status",
        "WARN",
        "--summary",
        str(alert_payload.get("notification_summary", "")).strip() or task_name,
        "--extra",
        f"signature={alert_payload['signature']}",
        "--extra",
        f"summary={alert_payload['summary']}",
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except Exception as exc:
        base_status["last_alert_status"] = f"notify_failed:{exc}"
        return base_status

    next_state = {
        "last_alert_time": fetch_time,
        "last_alert_signature": alert_payload["signature"],
        "last_alert_summary": alert_payload["summary"],
    }
    write_json_file(state_path, next_state)
    return {
        "enabled": True,
        "sent": True,
        "last_alert_time": fetch_time,
        "last_alert_signature": alert_payload["signature"],
        "last_alert_summary": alert_payload["summary"],
        "last_alert_status": "sent",
    }


def maybe_send_high_risk_notification(
    *,
    config: dict[str, Any],
    alert_payload: dict[str, Any] | None,
    fetch_time: str,
) -> dict[str, Any]:
    return deliver_alert_notification(
        config=config,
        alerting_cfg=config.get("news", {}).get("alerting"),
        alert_payload=alert_payload,
        fetch_time=fetch_time,
        default_state_file="finance_alert_state.json",
        default_task_name="finance-signals-high-risk",
    )


def maybe_send_market_alert_notification(
    *,
    config: dict[str, Any],
    alert_payload: dict[str, Any] | None,
    fetch_time: str,
) -> dict[str, Any]:
    return deliver_alert_notification(
        config=config,
        alerting_cfg=config.get("market_data", {}).get("alerting"),
        alert_payload=alert_payload,
        fetch_time=fetch_time,
        default_state_file="../.tmp/finance_market_alert_state.json",
        default_task_name="finance-signals-market-alert",
    )


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
    max_age_hours = int(poll_cfg.get("recency_max_age_hours", 48))
    allow_missing_published = bool(poll_cfg.get("allow_missing_published", True))
    max_unmatched_titles = int(poll_cfg.get("max_unmatched_titles", 5))
    topic_similarity_threshold = float(poll_cfg.get("topic_similarity_threshold", 0.55))
    ranking_cfg = news_cfg.get("ranking")
    if not isinstance(ranking_cfg, dict):
        ranking_cfg = {}
    filters_cfg = news_cfg.get("filters")
    if not isinstance(filters_cfg, dict):
        filters_cfg = {}

    keywords_cfg = news_cfg["keywords"]
    crisis_up_words = list(keywords_cfg["crisis_up"])
    crisis_down_words = list(keywords_cfg["crisis_down"])
    exclude_title_words = list(keywords_cfg.get("exclude_title_if_contains", []))
    negation_prefixes = list(keywords_cfg.get("negation_prefixes", []))
    now_utc = datetime.now(timezone.utc)

    result: dict[str, Any] = {
        "crisis_up_hits": [],
        "crisis_down_hits": [],
        "debug": {
            "entries_scanned": 0,
            "entries_filtered_by_source": 0,
            "up_hits_count": 0,
            "down_hits_count": 0,
            "top_unmatched_titles": [],
            "last_alert_time": "",
            "last_alert_signature": "",
            "last_alert_summary": "",
            "last_alert_status": "",
        },
    }
    unmatched_titles: list[dict[str, Any]] = []

    for source in sources:
        source_name = str(source["name"])
        source_url = str(source["url"])
        try:
            feed = await asyncio.to_thread(parse_feed_sync, source_url)
            entries = list(feed.entries)[:max_items_per_source]
            for entry in entries:
                result["debug"]["entries_scanned"] += 1
                title = str(entry.get("title", "")).strip()
                summary = str(entry.get("summary", "")).strip()
                link = str(entry.get("link", "")).strip()
                published = str(entry.get("published", "")).strip()
                published_dt = parse_published_datetime(published)
                if not should_keep_recent_item(
                    published_dt=published_dt,
                    now_utc=now_utc,
                    max_age_hours=max_age_hours,
                    allow_missing_published=allow_missing_published,
                ):
                    continue
                publisher = extract_publisher_label(
                    source_name=source_name,
                    title=title,
                    link=link,
                )
                domain = extract_link_domain(link)
                if not should_keep_source(
                    publisher=publisher,
                    domain=domain,
                    filters_cfg=filters_cfg,
                ):
                    result["debug"]["entries_filtered_by_source"] += 1
                    continue
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
                    score, age_hours = compute_news_hit_score(
                        title=title,
                        matched_keywords=up_matched,
                        hit_kind="crisis_up",
                        published_dt=published_dt,
                        now_utc=now_utc,
                        ranking_cfg=ranking_cfg,
                        source_name=source_name,
                        link=link,
                    )
                    result["crisis_up_hits"].append(
                        {
                            "source": source_name,
                            "publisher": publisher,
                            "domain": domain,
                            "title": title,
                            "link": link,
                            "published": published,
                            "matched_keywords": up_matched,
                            "score": round(score, 4),
                            "age_hours": round(age_hours, 2) if age_hours is not None else None,
                            "published_ts": published_dt.timestamp() if published_dt else 0.0,
                            "topic_key": build_topic_key(title, up_matched),
                            "topic_tokens": build_topic_tokens(title, up_matched),
                        }
                    )
                if down_matched:
                    score, age_hours = compute_news_hit_score(
                        title=title,
                        matched_keywords=down_matched,
                        hit_kind="crisis_down",
                        published_dt=published_dt,
                        now_utc=now_utc,
                        ranking_cfg=ranking_cfg,
                        source_name=source_name,
                        link=link,
                    )
                    result["crisis_down_hits"].append(
                        {
                            "source": source_name,
                            "publisher": publisher,
                            "domain": domain,
                            "title": title,
                            "link": link,
                            "published": published,
                            "matched_keywords": down_matched,
                            "score": round(score, 4),
                            "age_hours": round(age_hours, 2) if age_hours is not None else None,
                            "published_ts": published_dt.timestamp() if published_dt else 0.0,
                            "topic_key": build_topic_key(title, down_matched),
                            "topic_tokens": build_topic_tokens(title, down_matched),
                        }
                    )
                if not up_matched and not down_matched and title:
                    unmatched_titles.append(
                        {
                            "title": title,
                            "published_ts": published_dt.timestamp() if published_dt else 0.0,
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
                    "score": 9999.0,
                    "age_hours": None,
                    "published_ts": now_utc.timestamp(),
                }
            )

    result["crisis_up_hits"] = dedupe_and_sort_news_hits(
        result["crisis_up_hits"],
        max_items=max_matched_items,
        similarity_threshold=topic_similarity_threshold,
    )
    result["crisis_down_hits"] = dedupe_and_sort_news_hits(
        result["crisis_down_hits"],
        max_items=max_matched_items,
        similarity_threshold=topic_similarity_threshold,
    )
    result["debug"]["up_hits_count"] = len(result["crisis_up_hits"])
    result["debug"]["down_hits_count"] = len(result["crisis_down_hits"])
    result["debug"]["top_unmatched_titles"] = dedupe_titles(
        unmatched_titles,
        max_items=max_unmatched_titles,
    )
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
    if crisis_down_hits:
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
        "news_last_fetch_time": str(shared_state.get("news_last_fetch_time", "")).strip(),
        "watchlist_preview": shared_state.get("watchlist_preview", []),
        "ai_insight_text": build_ai_insight_text(
            config=config,
            market_alerts=shared_state.get("market_alerts", []),
            news_hits=shared_state.get(
                "news_hits",
                {"crisis_up_hits": [], "crisis_down_hits": [], "debug": {}},
            ),
        ),
        "news_debug": shared_state.get(
            "news_debug",
            {
                "entries_scanned": 0,
                "entries_filtered_by_source": 0,
                "up_hits_count": 0,
                "down_hits_count": 0,
                "top_unmatched_titles": [],
                "enabled": False,
                "sent": False,
                "last_alert_time": "",
                "last_alert_signature": "",
                "last_alert_summary": "",
                "last_alert_status": "",
            },
        ),
        "market_alert_debug": shared_state.get(
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
            fetch_time = now_text(config)
            market_alert_debug = await asyncio.to_thread(
                maybe_send_market_alert_notification,
                config=config,
                alert_payload=build_market_alert_payload(
                    config=config,
                    market_alerts=market_alerts,
                ),
                fetch_time=fetch_time,
            )
            async with state_lock:
                shared_state["watchlist_preview"] = watchlist_preview
                shared_state["market_alerts"] = market_alerts
                shared_state["market_alert_debug"] = market_alert_debug
            await update_dashboard_state(config=config, shared_state=shared_state, file_lock=file_lock)
        except Exception as exc:  # noqa: BLE001
            async with state_lock:
                shared_state["market_alerts"] = [f"行情任务异常：{exc}"]
                shared_state["market_alert_debug"] = {
                    "enabled": False,
                    "sent": False,
                    "last_alert_time": "",
                    "last_alert_signature": "",
                    "last_alert_summary": "",
                    "last_alert_status": "error",
                }
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
            fetch_time = now_text(config)
            alert_status = await asyncio.to_thread(
                maybe_send_high_risk_notification,
                config=config,
                alert_payload=build_high_risk_alert_payload(config=config, news_hits=news_hits),
                fetch_time=fetch_time,
            )
            news_debug = dict(
                news_hits.get(
                    "debug",
                    {
                        "entries_scanned": 0,
                        "entries_filtered_by_source": 0,
                        "up_hits_count": 0,
                        "down_hits_count": 0,
                        "top_unmatched_titles": [],
                    },
                )
            )
            news_debug.update(alert_status)
            async with state_lock:
                shared_state["news_hits"] = news_hits
                shared_state["news_last_fetch_time"] = fetch_time
                shared_state["news_debug"] = news_debug
            await update_dashboard_state(config=config, shared_state=shared_state, file_lock=file_lock)
        except Exception as exc:  # noqa: BLE001
            fetch_time = now_text(config)
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
                shared_state["news_last_fetch_time"] = fetch_time
                shared_state["news_debug"] = {
                    "entries_scanned": 0,
                    "entries_filtered_by_source": 0,
                    "up_hits_count": 1,
                    "down_hits_count": 0,
                    "top_unmatched_titles": [],
                    "enabled": False,
                    "sent": False,
                    "last_alert_time": "",
                    "last_alert_signature": "",
                    "last_alert_summary": "",
                    "last_alert_status": "error",
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
        "market_alert_debug": {
            "enabled": False,
            "sent": False,
            "last_alert_time": "",
            "last_alert_signature": "",
            "last_alert_summary": "",
            "last_alert_status": "",
        },
        "news_hits": {"crisis_up_hits": [], "crisis_down_hits": [], "debug": {}},
        "news_last_fetch_time": "",
        "news_debug": {
            "entries_scanned": 0,
            "entries_filtered_by_source": 0,
            "up_hits_count": 0,
            "down_hits_count": 0,
            "top_unmatched_titles": [],
            "enabled": False,
            "sent": False,
            "last_alert_time": "",
            "last_alert_signature": "",
            "last_alert_summary": "",
            "last_alert_status": "",
        },
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
