#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="$SERVER_DIR/.tmp"
PID_FILE="$TMP_DIR/finance_signals.pid"
LOG_FILE="$TMP_DIR/finance_signals.log"
APP_FILE="$SERVER_DIR/finance_signals/main.py"
CONFIG_FILE="$SERVER_DIR/finance_signals/financial_config.yaml"

usage() {
  cat <<'EOF'
Usage:
  tools/finance_signals.sh start
  tools/finance_signals.sh stop
  tools/finance_signals.sh restart
  tools/finance_signals.sh status
  tools/finance_signals.sh logs [lines]
  tools/finance_signals.sh check
EOF
}

resolve_python() {
  if [[ -x "$SERVER_DIR/.venv/bin/python" ]]; then
    echo "$SERVER_DIR/.venv/bin/python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi
  echo ""
}

PYTHON_BIN="$(resolve_python)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[finance_signals] python not found"
  exit 1
fi

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    if sync_pid_file_from_process_table; then
      return 0
    fi
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    rm -f "$PID_FILE"
    if sync_pid_file_from_process_table; then
      return 0
    fi
    return 1
  fi
  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi
  rm -f "$PID_FILE"
  if sync_pid_file_from_process_table; then
    return 0
  fi
  return 1
}

list_running_pids() {
  ps -eo pid=,args= 2>/dev/null | awk -v app="$APP_FILE" '
    index($0, app) > 0 && index($0, "finance_signals.sh") == 0 {print $1}
  ' | sort -n
}

sync_pid_file_from_process_table() {
  local pids=()
  mapfile -t pids < <(list_running_pids)
  if (( ${#pids[@]} == 0 )); then
    return 1
  fi
  echo "${pids[0]}" > "$PID_FILE"
  return 0
}

dedupe_running_processes() {
  local pids=()
  mapfile -t pids < <(list_running_pids)
  if (( ${#pids[@]} <= 1 )); then
    if (( ${#pids[@]} == 1 )); then
      echo "${pids[0]}" > "$PID_FILE"
    fi
    return 0
  fi

  local primary_pid extra_pid
  primary_pid="${pids[0]}"
  for extra_pid in "${pids[@]:1}"; do
    kill "$extra_pid" >/dev/null 2>&1 || true
    sleep 0.2
    if kill -0 "$extra_pid" >/dev/null 2>&1; then
      kill -9 "$extra_pid" >/dev/null 2>&1 || true
    fi
  done
  echo "$primary_pid" > "$PID_FILE"
  echo "[finance_signals] dedup done: keep pid=$primary_pid, removed=$(( ${#pids[@]} - 1 ))"
}

run_check() {
  local running_pid=""
  if is_running; then
    running_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  fi

  FINANCE_SIGNALS_PID="$running_pid" "$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

config_path = Path(sys.argv[1]).resolve()
with config_path.open("r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

output_cfg = cfg.get("output", {})
runtime_cfg = cfg.get("runtime", {})
status_file = str(output_cfg.get("status_file", "finance_status.json")).strip()
time_format = str(output_cfg.get("time_format", "%Y-%m-%d %H:%M:%S"))
max_staleness = int(runtime_cfg.get("health_max_staleness_seconds", 420))
startup_grace = int(runtime_cfg.get("health_startup_grace_seconds", 120))
running_pid = str(os.environ.get("FINANCE_SIGNALS_PID", "")).strip()

status_path = Path(status_file)
if not status_path.is_absolute():
    status_path = (config_path.parent / status_path).resolve()

if not status_path.exists():
    print(f"[finance_signals] check=fail reason=status_file_not_found path={status_path}")
    raise SystemExit(1)

try:
    payload = json.loads(status_path.read_text(encoding="utf-8"))
except Exception as exc:  # noqa: BLE001
    print(f"[finance_signals] check=fail reason=invalid_json error={exc}")
    raise SystemExit(1)

update_time = str(payload.get("update_time", "")).strip()
if not update_time:
    print("[finance_signals] check=fail reason=missing_update_time")
    raise SystemExit(1)

try:
    last_dt = datetime.strptime(update_time, time_format)
except Exception as exc:  # noqa: BLE001
    print(f"[finance_signals] check=fail reason=bad_time_format error={exc}")
    raise SystemExit(1)

age_seconds = int((datetime.now() - last_dt).total_seconds())
if age_seconds > max_staleness:
    if running_pid:
        try:
            etimes_raw = subprocess.check_output(
                ["ps", "-p", running_pid, "-o", "etimes="],
                text=True,
            ).strip()
            process_uptime_seconds = int(etimes_raw or "0")
        except Exception:  # noqa: BLE001
            process_uptime_seconds = -1
        if 0 <= process_uptime_seconds <= startup_grace:
            print(
                "[finance_signals] check=ok "
                "status=starting "
                f"age_seconds={age_seconds} max_allowed={max_staleness} "
                f"process_uptime_seconds={process_uptime_seconds} startup_grace={startup_grace}"
            )
            raise SystemExit(0)
    print(
        "[finance_signals] check=fail "
        f"reason=stale_status age_seconds={age_seconds} max_allowed={max_staleness}"
    )
    raise SystemExit(1)

watchlist_len = len(payload.get("watchlist_preview", []) or [])
insight = str(payload.get("ai_insight_text", "")).strip()
print(
    "[finance_signals] check=ok "
    f"age_seconds={age_seconds} watchlist_items={watchlist_len} "
    f"insight_non_empty={bool(insight)}"
)
PY
}

start_job() {
  if is_running; then
    dedupe_running_processes
    local pid
    pid="$(cat "$PID_FILE")"
    echo "[finance_signals] already running pid=$pid"
    return 0
  fi

  if [[ ! -f "$APP_FILE" ]]; then
    echo "[finance_signals] app not found: $APP_FILE"
    exit 1
  fi
  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "[finance_signals] config not found: $CONFIG_FILE"
    exit 1
  fi

  mkdir -p "$TMP_DIR"
  local pythonpath_value="$SERVER_DIR"
  if [[ -n "${PYTHONPATH:-}" ]]; then
    pythonpath_value="$SERVER_DIR:$PYTHONPATH"
  fi
  if command -v setsid >/dev/null 2>&1; then
    env PYTHONPATH="$pythonpath_value" setsid "$PYTHON_BIN" "$APP_FILE" > "$LOG_FILE" 2>&1 < /dev/null &
  else
    env PYTHONPATH="$pythonpath_value" nohup "$PYTHON_BIN" "$APP_FILE" > "$LOG_FILE" 2>&1 < /dev/null &
  fi

  local pid
  pid=$!
  echo "$pid" > "$PID_FILE"
  sleep 1
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    echo "[finance_signals] failed to start"
    tail -n 80 "$LOG_FILE" 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
  fi
  echo "[finance_signals] started pid=$pid"
  echo "[finance_signals] log=$LOG_FILE"
}

stop_job() {
  if ! is_running; then
    echo "[finance_signals] not running"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid" >/dev/null 2>&1 || true
  sleep 1
  if kill -0 "$pid" >/dev/null 2>&1; then
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$PID_FILE"
  echo "[finance_signals] stopped pid=$pid"
}

show_status() {
  if is_running; then
    local pid
    pid="$(cat "$PID_FILE")"
    echo "[finance_signals] RUNNING pid=$pid"
    echo "[finance_signals] log=$LOG_FILE"
  else
    echo "[finance_signals] STOPPED"
  fi
}

show_logs() {
  local lines="${1:-120}"
  if [[ ! -f "$LOG_FILE" ]]; then
    echo "[finance_signals] log not found: $LOG_FILE"
    return 0
  fi
  tail -n "$lines" "$LOG_FILE"
}

cmd="${1:-}"
case "$cmd" in
  start)
    start_job
    ;;
  stop)
    stop_job
    ;;
  restart)
    stop_job
    start_job
    ;;
  status)
    show_status
    ;;
  logs)
    shift || true
    show_logs "${1:-120}"
    ;;
  check)
    run_check
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
