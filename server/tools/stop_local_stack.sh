#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$SERVER_DIR/.tmp/local_server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "[stop_local_stack] PID file not found: $PID_FILE"
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -z "$PID" ]]; then
  rm -f "$PID_FILE"
  echo "[stop_local_stack] PID file was empty, cleaned."
  exit 0
fi

if kill -0 "$PID" >/dev/null 2>&1; then
  kill "$PID" >/dev/null 2>&1 || true
  echo "[stop_local_stack] Stopped PID=$PID"
else
  echo "[stop_local_stack] Process not running: PID=$PID"
fi

rm -f "$PID_FILE"
