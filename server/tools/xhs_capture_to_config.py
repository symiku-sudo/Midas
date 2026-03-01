from __future__ import annotations

import argparse
import base64
import json
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.config import load_settings

_HEADER_SKIP = {
    "content-length",
    "host",
    ":authority",
    ":method",
    ":path",
    ":scheme",
}

_NOTE_ID_CANDIDATES = ["note_id", "noteid", "id", "item_id"]
_TITLE_CANDIDATES = ["title", "note_title", "name"]
_CONTENT_CANDIDATES = ["desc", "content", "note_text", "text"]
_SOURCE_URL_CANDIDATES = ["url", "source_url", "jump_url", "link"]
DEFAULT_ENV_PATH = SERVER_ROOT / ".env"


@dataclass
class FieldInference:
    items_path: str
    note_id_field: str
    title_field: str
    content_field_candidates: list[str]
    source_url_field: str


@dataclass
class RequestCapture:
    request_url: str
    request_method: str
    request_headers: dict[str, str]
    request_body: str
    inference: FieldInference | None = None


def parse_curl_text(curl_text: str) -> RequestCapture:
    normalized = _normalize_curl_text(curl_text)
    if not normalized:
        raise ValueError("curl 内容为空。")

    try:
        tokens = shlex.split(normalized, posix=True)
    except ValueError:
        # Fallback for some shell-specific escaping variants.
        tokens = shlex.split(normalized, posix=False)
    if not tokens:
        raise ValueError("无法解析 curl 内容。")
    if tokens[0].lower() in {"curl", "curl.exe"}:
        tokens = tokens[1:]

    method = ""
    url = ""
    headers: dict[str, str] = {}
    data_parts: list[str] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token in {"-X", "--request"}:
            i += 1
            method = tokens[i].strip().upper() if i < len(tokens) else ""
        elif token in {"-H", "--header"}:
            i += 1
            if i < len(tokens):
                _merge_header(headers, tokens[i])
        elif token.startswith("--header="):
            _merge_header(headers, token.split("=", 1)[1])
        elif token.startswith("-H") and token != "-H":
            _merge_header(headers, token[2:])
        elif token in {"-b", "--cookie"}:
            i += 1
            if i < len(tokens):
                _merge_header(headers, f"Cookie: {tokens[i]}")
        elif token.startswith("--cookie="):
            _merge_header(headers, f"Cookie: {token.split('=', 1)[1]}")
        elif token.startswith("-b="):
            _merge_header(headers, f"Cookie: {token.split('=', 1)[1]}")
        elif token in {"-A", "--user-agent"}:
            i += 1
            if i < len(tokens):
                _merge_header(headers, f"User-Agent: {tokens[i]}")
        elif token.startswith("--user-agent="):
            _merge_header(headers, f"User-Agent: {token.split('=', 1)[1]}")
        elif token in {"-e", "--referer", "--referrer"}:
            i += 1
            if i < len(tokens):
                _merge_header(headers, f"Referer: {tokens[i]}")
        elif token.startswith("--referer=") or token.startswith("--referrer="):
            _merge_header(headers, f"Referer: {token.split('=', 1)[1]}")
        elif token in {
            "-d",
            "--data",
            "--data-raw",
            "--data-binary",
            "--data-urlencode",
            "--data-ascii",
        }:
            i += 1
            if i < len(tokens):
                data_parts.append(tokens[i])
        elif token == "--url":
            i += 1
            if i < len(tokens):
                url = tokens[i].strip()
        elif token.startswith("--url="):
            url = token.split("=", 1)[1].strip()
        elif token.startswith("http://") or token.startswith("https://"):
            url = token.strip()
        i += 1

    if not method:
        method = "POST" if data_parts else "GET"
    if not url:
        raise ValueError("curl 中未找到请求 URL。")

    body = "&".join(data_parts).strip()
    if method != "POST":
        body = ""

    return RequestCapture(
        request_url=url,
        request_method=method,
        request_headers=headers,
        request_body=body,
    )


def _normalize_curl_text(raw: str) -> str:
    normalized = raw.replace("\r\n", "\n")
    # Handle multiline copy styles:
    # bash continuation "\" / cmd continuation "^" / powershell continuation "`".
    normalized = re.sub(r"[ \t]*(\\|\^|`)\n[ \t]*", " ", normalized)
    return normalized.strip()


def extract_best_har_capture(
    har_data: dict[str, Any], select_url_contains: str = ""
) -> RequestCapture:
    entries = har_data.get("log", {}).get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("HAR 格式无效：缺少 log.entries 列表。")

    best_score = -1
    best_capture: RequestCapture | None = None
    url_hint = select_url_contains.strip()

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        scored = _score_har_entry(entry, url_hint)
        if scored is None:
            continue

        score, capture = scored
        if score > best_score:
            best_score = score
            best_capture = capture

    if best_capture is None:
        raise ValueError("未在 HAR 中找到可用的小红书 JSON 列表请求。")
    return best_capture


def infer_fields_from_payload(payload: Any) -> tuple[FieldInference | None, int]:
    best_score = -1
    best_inference: FieldInference | None = None

    for path, records in _walk_lists(payload):
        dict_records = [item for item in records if isinstance(item, dict)]
        if not dict_records:
            continue

        sample = dict_records[0]
        score = _score_record(sample)
        lowered_path = path.lower()
        if "note" in lowered_path:
            score += 2
        if "collect" in lowered_path or "fav" in lowered_path:
            score += 1
        if score < 4:
            continue

        inference = FieldInference(
            items_path=path,
            note_id_field=_find_field_path(sample, _NOTE_ID_CANDIDATES) or "note_id",
            title_field=_find_field_path(sample, _TITLE_CANDIDATES) or "title",
            content_field_candidates=(
                _find_content_paths(sample) or ["desc", "content", "note_text"]
            ),
            source_url_field=(
                _find_field_path(sample, _SOURCE_URL_CANDIDATES) or "url"
            ),
        )
        if score > best_score:
            best_score = score
            best_inference = inference

    return best_inference, best_score


def apply_capture_to_config(
    config: dict[str, Any], capture: RequestCapture
) -> dict[str, Any]:
    xhs_cfg = config.setdefault("xiaohongshu", {})
    xhs_cfg["mode"] = "web_readonly"
    xhs_cfg.setdefault("min_live_sync_interval_seconds", 120)

    web_cfg = xhs_cfg.setdefault("web_readonly", {})
    web_cfg["request_url"] = capture.request_url
    web_cfg["request_method"] = capture.request_method
    web_cfg["request_headers"] = capture.request_headers
    web_cfg["request_body"] = capture.request_body if capture.request_method == "POST" else ""
    web_cfg.setdefault(
        "host_allowlist", ["www.xiaohongshu.com", "edith.xiaohongshu.com"]
    )

    if capture.inference is not None:
        web_cfg["items_path"] = capture.inference.items_path
        web_cfg["note_id_field"] = capture.inference.note_id_field
        web_cfg["title_field"] = capture.inference.title_field
        web_cfg["content_field_candidates"] = capture.inference.content_field_candidates
        web_cfg["source_url_field"] = capture.inference.source_url_field

    return config


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"配置文件不是 YAML 对象: {path}")
    return raw


def write_yaml_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    try:
        capture: RequestCapture
        if args.har is None and args.curl is None and args.curl_file is None:
            _source, _capture_path, capture = load_capture_from_default_sources(
                select_url_contains=args.select_url_contains
            )
        else:
            if args.har is not None:
                capture = extract_best_har_capture(
                    load_json_file(args.har), select_url_contains=args.select_url_contains
                )
            else:
                if args.curl is not None:
                    curl_text = args.curl
                elif args.curl_file is not None:
                    curl_text = args.curl_file.read_text(encoding="utf-8")
                else:
                    raise ValueError("请提供 --har 或 --curl/--curl-file。")

                capture = parse_curl_text(curl_text)
                if args.response_json is not None:
                    payload = load_json_file(args.response_json)
                    inference, _ = infer_fields_from_payload(payload)
                    capture.inference = inference

        if args.dry_run:
            _assert_xhs_host(capture.request_url)
            updates = build_env_updates(capture)
            _print_summary(
                capture=capture,
                output_path=args.env,
                updated_keys=updates,
                dry_run=True,
            )
            return 0

        capture, updates = apply_capture_to_env(
            capture,
            env_path=args.env,
        )
        _print_summary(capture=capture, output_path=args.env, updated_keys=updates)
        return 0
    except Exception as exc:
        print(f"[xhs_capture_to_config] 失败: {exc}")
        return 1


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把浏览器抓包（HAR 或 cURL）转换为 server/.env 的 XHS_* 变量。"
    )

    src_group = parser.add_mutually_exclusive_group(required=False)
    src_group.add_argument(
        "--har",
        type=Path,
        help=(
            "HAR 文件路径。若不传且未传 --curl/--curl-file，"
            "将优先回退到 config.yaml 的 "
            "xiaohongshu.web_readonly.har_capture_path。"
        ),
    )
    src_group.add_argument("--curl-file", type=Path, help="包含 cURL 文本的文件路径。")
    src_group.add_argument("--curl", type=str, help="直接传入 cURL 文本。")

    parser.add_argument(
        "--response-json",
        type=Path,
        default=None,
        help="可选：cURL 对应的响应 JSON 文件，用于自动推断字段路径。",
    )
    parser.add_argument(
        "--select-url-contains",
        type=str,
        default="",
        help="可选：当 HAR 里请求很多时，用 URL 子串提升匹配优先级。",
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=DEFAULT_ENV_PATH,
        help="输出 .env 文件路径（默认 server/.env）。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印将更新的变量摘要，不写文件。",
    )
    return parser


def resolve_default_har_path() -> Path | None:
    raw_path = load_settings().xiaohongshu.web_readonly.har_capture_path.strip()
    if not raw_path:
        return None

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (SERVER_ROOT / candidate).resolve()


def resolve_default_curl_path() -> Path | None:
    raw_path = load_settings().xiaohongshu.web_readonly.curl_capture_path.strip()
    if not raw_path:
        return None

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (SERVER_ROOT / candidate).resolve()


def load_capture_from_default_sources(
    *,
    select_url_contains: str = "",
) -> tuple[str, Path, RequestCapture]:
    failures: list[str] = []

    try:
        har_path = resolve_default_har_path()
        if har_path is None:
            raise ValueError(
                "config.yaml 未配置 xiaohongshu.web_readonly.har_capture_path。"
            )
        if not har_path.exists():
            raise ValueError(f"HAR 文件不存在: {har_path}")
        capture = extract_best_har_capture(
            load_json_file(har_path),
            select_url_contains=select_url_contains,
        )
        return "har", har_path, capture
    except Exception as exc:
        failures.append(f"HAR: {exc}")

    try:
        curl_path = resolve_default_curl_path()
        if curl_path is None:
            raise ValueError(
                "config.yaml 未配置 xiaohongshu.web_readonly.curl_capture_path。"
            )
        if not curl_path.exists():
            raise ValueError(f"cURL 文件不存在: {curl_path}")
        capture = parse_curl_text(curl_path.read_text(encoding="utf-8"))
        return "curl", curl_path, capture
    except Exception as exc:
        failures.append(f"cURL: {exc}")

    raise ValueError(
        "请提供 --har/--curl/--curl-file，或在 config.yaml 配置并准备默认抓包文件。"
        + "；".join(failures)
    )


def apply_capture_to_env(
    capture: RequestCapture,
    *,
    env_path: Path,
    require_cookie: bool = False,
) -> tuple[RequestCapture, dict[str, str]]:
    _assert_xhs_host(capture.request_url)
    if require_cookie:
        _assert_capture_has_cookie(capture)
    updates = build_env_updates(capture)
    upsert_env_file(env_path, updates)
    return capture, updates


def apply_capture_from_default_har_to_env(
    *,
    env_path: Path = DEFAULT_ENV_PATH,
    select_url_contains: str = "",
    require_cookie: bool = False,
) -> tuple[Path, RequestCapture, dict[str, str]]:
    har_path = resolve_default_har_path()
    if har_path is None:
        raise ValueError(
            "config.yaml 未配置 xiaohongshu.web_readonly.har_capture_path。"
        )
    if not har_path.exists():
        raise ValueError(f"HAR 文件不存在: {har_path}")

    capture = extract_best_har_capture(
        load_json_file(har_path),
        select_url_contains=select_url_contains,
    )
    capture, updates = apply_capture_to_env(
        capture,
        env_path=env_path,
        require_cookie=require_cookie,
    )
    return har_path, capture, updates


def apply_capture_from_default_curl_to_env(
    *,
    env_path: Path = DEFAULT_ENV_PATH,
    require_cookie: bool = False,
) -> tuple[Path, RequestCapture, dict[str, str]]:
    curl_path = resolve_default_curl_path()
    if curl_path is None:
        raise ValueError(
            "config.yaml 未配置 xiaohongshu.web_readonly.curl_capture_path。"
        )
    if not curl_path.exists():
        raise ValueError(f"cURL 文件不存在: {curl_path}")

    capture = parse_curl_text(curl_path.read_text(encoding="utf-8"))
    capture, updates = apply_capture_to_env(
        capture,
        env_path=env_path,
        require_cookie=require_cookie,
    )
    return curl_path, capture, updates


def apply_capture_from_default_auth_source_to_env(
    *,
    env_path: Path = DEFAULT_ENV_PATH,
    select_url_contains: str = "",
    require_cookie: bool = False,
) -> tuple[str, Path, RequestCapture, dict[str, str]]:
    failures: list[str] = []

    try:
        capture_path, capture, updates = apply_capture_from_default_har_to_env(
            env_path=env_path,
            select_url_contains=select_url_contains,
            require_cookie=require_cookie,
        )
        return "har", capture_path, capture, updates
    except Exception as exc:
        failures.append(f"HAR: {exc}")

    try:
        capture_path, capture, updates = apply_capture_from_default_curl_to_env(
            env_path=env_path,
            require_cookie=require_cookie,
        )
        return "curl", capture_path, capture, updates
    except Exception as exc:
        failures.append(f"cURL: {exc}")

    raise ValueError(
        "默认抓包配置不可用。"
        + "；".join(failures)
    )


def _assert_capture_has_cookie(capture: RequestCapture) -> None:
    cookie = _get_header(capture.request_headers, "Cookie")
    if cookie:
        return
    raise ValueError(
        "HAR/cURL 未包含 Cookie，请使用包含敏感数据的抓包导出，"
        "或用浏览器“Copy as cURL”重新导入。"
    )


def build_env_updates(capture: RequestCapture) -> dict[str, str]:
    return {
        "XHS_REQUEST_URL": _single_line(capture.request_url),
        "XHS_HEADER_ACCEPT": _single_line(_get_header(capture.request_headers, "Accept")),
        "XHS_HEADER_COOKIE": _single_line(_get_header(capture.request_headers, "Cookie")),
        "XHS_HEADER_ORIGIN": _single_line(_get_header(capture.request_headers, "Origin")),
        "XHS_HEADER_REFERER": _single_line(_get_header(capture.request_headers, "Referer")),
        "XHS_HEADER_USER_AGENT": _single_line(
            _get_header(capture.request_headers, "User-Agent")
        ),
        "XHS_HEADER_X_S": _single_line(_get_header(capture.request_headers, "X-S")),
        "XHS_HEADER_X_S_COMMON": _single_line(
            _get_header(capture.request_headers, "X-S-Common")
        ),
        "XHS_HEADER_X_T": _single_line(_get_header(capture.request_headers, "X-T")),
    }


def upsert_env_file(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    key_to_line: dict[str, int] = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            key_to_line[key] = i

    for key, value in updates.items():
        normalized = _single_line(value)
        if not normalized and key in key_to_line:
            # Keep existing secret/header value when current capture misses this field.
            continue
        rendered = f"{key}={normalized}"
        if key in key_to_line:
            lines[key_to_line[key]] = rendered
        else:
            lines.append(rendered)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _get_header(headers: dict[str, str], key: str) -> str:
    wanted = key.strip().lower()
    for k, v in headers.items():
        if str(k).strip().lower() == wanted:
            return str(v).strip()
    return ""


def _single_line(value: str) -> str:
    return " ".join(str(value).splitlines()).strip()


def _score_har_entry(
    entry: dict[str, Any], url_hint: str
) -> tuple[int, RequestCapture] | None:
    request = entry.get("request")
    response = entry.get("response")
    if not isinstance(request, dict) or not isinstance(response, dict):
        return None

    method = str(request.get("method", "GET")).strip().upper()
    if method not in {"GET", "POST"}:
        return None

    url = str(request.get("url", "")).strip()
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.netloc.endswith("xiaohongshu.com"):
        return None

    status = int(response.get("status", 0))
    if status < 200 or status >= 300:
        return None

    payload = _extract_har_response_json(response)
    if payload is None:
        return None

    inference, score = infer_fields_from_payload(payload)
    if inference is None:
        return None

    headers: dict[str, str] = {}
    for item in request.get("headers", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        value = str(item.get("value", ""))
        _merge_header(headers, f"{name}:{value}")

    post_data = request.get("postData")
    body = ""
    if method == "POST" and isinstance(post_data, dict):
        body = str(post_data.get("text", "")).strip()

    if "note" in url.lower() or "collect" in url.lower() or "fav" in url.lower():
        score += 2
    if url_hint and url_hint in url:
        score += 3

    capture = RequestCapture(
        request_url=url,
        request_method=method,
        request_headers=headers,
        request_body=body,
        inference=inference,
    )
    return score, capture


def _extract_har_response_json(response: dict[str, Any]) -> Any | None:
    content = response.get("content")
    if not isinstance(content, dict):
        return None
    text = content.get("text")
    if not isinstance(text, str) or not text.strip():
        return None

    if content.get("encoding") == "base64":
        try:
            text = base64.b64decode(text).decode("utf-8", errors="replace")
        except ValueError:
            return None

    cleaned = text.lstrip()
    if cleaned.startswith(")]}',"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
    if not cleaned:
        return None

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _walk_lists(payload: Any, prefix: str = "") -> list[tuple[str, list[Any]]]:
    found: list[tuple[str, list[Any]]] = []
    if isinstance(payload, list):
        found.append((prefix, payload))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            next_prefix = f"{prefix}.{key_text}" if prefix else key_text
            found.extend(_walk_lists(value, next_prefix))
    return found


def _score_record(record: dict[str, Any]) -> int:
    keys = _collect_keys(record)
    score = 0
    if any(key in keys for key in _NOTE_ID_CANDIDATES):
        score += 4
    if any(key in keys for key in _TITLE_CANDIDATES):
        score += 3
    if any(key in keys for key in _CONTENT_CANDIDATES):
        score += 2
    if any(key in keys for key in _SOURCE_URL_CANDIDATES):
        score += 1
    if any("note" in key for key in keys):
        score += 1
    return score


def _collect_keys(payload: Any, depth: int = 0, max_depth: int = 5) -> set[str]:
    if depth > max_depth:
        return set()
    if isinstance(payload, dict):
        keys: set[str] = set()
        for key, value in payload.items():
            keys.add(str(key).strip().lower())
            keys |= _collect_keys(value, depth + 1, max_depth=max_depth)
        return keys
    if isinstance(payload, list):
        keys: set[str] = set()
        for item in payload[:5]:
            keys |= _collect_keys(item, depth + 1, max_depth=max_depth)
        return keys
    return set()


def _find_content_paths(record: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for candidate in _CONTENT_CANDIDATES:
        path = _find_field_path(record, [candidate])
        if path and path not in found:
            found.append(path)
    return found


def _find_field_path(
    payload: Any,
    candidates: list[str],
    *,
    prefix: str = "",
    depth: int = 0,
    max_depth: int = 5,
) -> str:
    if depth > max_depth:
        return ""

    if isinstance(payload, dict):
        lower_map = {str(key).strip().lower(): str(key) for key in payload.keys()}
        for candidate in candidates:
            key = lower_map.get(candidate.lower())
            if key is not None:
                return f"{prefix}.{key}" if prefix else key

        for key, value in payload.items():
            key_text = str(key)
            next_prefix = f"{prefix}.{key_text}" if prefix else key_text
            result = _find_field_path(
                value,
                candidates,
                prefix=next_prefix,
                depth=depth + 1,
                max_depth=max_depth,
            )
            if result:
                return result
    elif isinstance(payload, list):
        for item in payload[:3]:
            result = _find_field_path(
                item,
                candidates,
                prefix=prefix,
                depth=depth + 1,
                max_depth=max_depth,
            )
            if result:
                return result

    return ""


def _merge_header(headers: dict[str, str], raw_header: str) -> None:
    if ":" not in raw_header:
        return
    name, value = raw_header.split(":", 1)
    key = name.strip()
    val = value.strip()
    if not key or not val:
        return
    if key.lower() in _HEADER_SKIP:
        return
    headers[key] = val


def _assert_xhs_host(url: str) -> None:
    host = urlparse(url).netloc
    if not host.endswith("xiaohongshu.com"):
        raise ValueError(f"请求域名不是小红书：{host}")


def _print_summary(
    capture: RequestCapture,
    output_path: Path,
    updated_keys: dict[str, str],
    dry_run: bool = False,
) -> None:
    action = "预览将更新" if dry_run else "已更新"
    print(f"[xhs_capture_to_config] {action} .env 变量。")
    print(f"- request_url_host: {urlparse(capture.request_url).netloc}")
    print(f"- request_method: {capture.request_method}")
    print(f"- headers: {len(capture.request_headers)} keys")
    if capture.inference is not None:
        print(f"- items_path: {capture.inference.items_path}")
        print(f"- note_id_field: {capture.inference.note_id_field}")
        print(f"- title_field: {capture.inference.title_field}")
    print(f"- env: {output_path}")

    non_empty = sorted([k for k, v in updated_keys.items() if v])
    empty = sorted([k for k, v in updated_keys.items() if not v])
    print(f"- non_empty_keys: {len(non_empty)}")
    if empty:
        print(f"- empty_keys: {', '.join(empty)}")


if __name__ == "__main__":
    raise SystemExit(main())
