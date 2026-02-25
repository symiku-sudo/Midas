#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="$SERVER_DIR/.tmp"
PID_FILE="$TMP_DIR/local_server.pid"

FORCE="0"
KEEP_DB="0"
DRY_RUN="0"

usage() {
  cat <<'EOF'
Usage:
  tools/clean_tmp.sh [--keep-db] [--force] [--dry-run]

Options:
  --keep-db   Keep .tmp/midas.db (preserve Xiaohongshu dedupe/runtime state)
  --force     Clean even if local server PID is running
  --dry-run   Show what would be removed without deleting
  -h, --help  Show this help

Examples:
  tools/clean_tmp.sh
  tools/clean_tmp.sh --keep-db
  tools/clean_tmp.sh --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-db)
      KEEP_DB="1"
      shift
      ;;
    --force)
      FORCE="1"
      shift
      ;;
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[clean_tmp] Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

is_server_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

mkdir -p "$TMP_DIR"

if [[ "$FORCE" != "1" ]] && is_server_running; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  echo "[clean_tmp] Refuse to clean while server is running (PID=$pid)."
  echo "[clean_tmp] Stop first: tools/dev_server.sh stop"
  echo "[clean_tmp] Or bypass check: tools/clean_tmp.sh --force"
  exit 1
fi

removed=0
while IFS= read -r -d '' path; do
  name="$(basename "$path")"
  if [[ "$KEEP_DB" == "1" && "$name" == "midas.db" ]]; then
    continue
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[clean_tmp] would remove: $path"
  else
    rm -rf -- "$path"
    echo "[clean_tmp] removed: $path"
  fi
  removed=$((removed + 1))
done < <(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -print0 | sort -z)

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[clean_tmp] dry-run complete, matched $removed entries."
else
  echo "[clean_tmp] clean complete, removed $removed entries."
  if [[ "$KEEP_DB" == "1" && -f "$TMP_DIR/midas.db" ]]; then
    echo "[clean_tmp] kept: $TMP_DIR/midas.db"
  fi
fi
