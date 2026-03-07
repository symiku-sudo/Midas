#!/usr/bin/env bash
set -euo pipefail

TOPIC_URL="${NTFY_TOPIC_URL:-}"
SERVER_URL="${NTFY_SERVER_URL:-https://ntfy.sh}"
TOPIC="${NTFY_TOPIC:-}"
AUTH_TOKEN="${NTFY_TOKEN:-}"

usage() {
  cat <<'EOF'
Usage:
  tools/ntfy_notify.sh [--topic-url <url>] [--server-url <url> --topic <topic>] [--token <token>]

Behavior:
  - This script always sends the fixed body: 任务完成
  - It does not include task name, path, links, or any sensitive content.

Config (optional env):
  NTFY_TOPIC_URL   Full topic URL, e.g. https://ntfy.sh/my-topic
  NTFY_SERVER_URL  Server URL, default https://ntfy.sh
  NTFY_TOPIC       Topic name, used with NTFY_SERVER_URL
  NTFY_TOKEN       Bearer token (if server requires auth)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic-url)
      if [[ $# -lt 2 ]]; then
        echo "[ntfy] missing value for --topic-url"
        exit 1
      fi
      TOPIC_URL="$2"
      shift 2
      ;;
    --server-url)
      if [[ $# -lt 2 ]]; then
        echo "[ntfy] missing value for --server-url"
        exit 1
      fi
      SERVER_URL="$2"
      shift 2
      ;;
    --topic)
      if [[ $# -lt 2 ]]; then
        echo "[ntfy] missing value for --topic"
        exit 1
      fi
      TOPIC="$2"
      shift 2
      ;;
    --token)
      if [[ $# -lt 2 ]]; then
        echo "[ntfy] missing value for --token"
        exit 1
      fi
      AUTH_TOKEN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ntfy] unsupported argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$TOPIC_URL" ]]; then
  if [[ -z "$TOPIC" ]]; then
    echo "[ntfy] missing target: provide --topic-url or --topic"
    exit 1
  fi
  SERVER_URL="${SERVER_URL%/}"
  TOPIC_URL="${SERVER_URL}/${TOPIC}"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[ntfy] curl not found"
  exit 1
fi

curl_args=(
  --fail
  --silent
  --show-error
  --max-time 15
  -H "Content-Type: text/plain; charset=utf-8"
  --data-binary "任务完成"
)

if [[ -n "$AUTH_TOKEN" ]]; then
  curl_args+=(-H "Authorization: Bearer ${AUTH_TOKEN}")
fi

curl "${curl_args[@]}" "$TOPIC_URL" >/dev/null
echo "[ntfy] sent: 任务完成 -> $TOPIC_URL"
