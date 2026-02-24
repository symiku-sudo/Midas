#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="$SERVER_DIR/.tmp"
PID_FILE="$TMP_DIR/local_server.pid"
LOG_FILE="$TMP_DIR/local_server.log"

usage() {
  cat <<'EOF'
Usage:
  tools/dev_server.sh start [web_guard|mock]
  tools/dev_server.sh stop
  tools/dev_server.sh restart [web_guard|mock]
  tools/dev_server.sh status
  tools/dev_server.sh logs [lines]

Examples:
  tools/dev_server.sh start
  tools/dev_server.sh start mock
  tools/dev_server.sh restart web_guard
  tools/dev_server.sh logs 120
EOF
}

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    rm -f "$PID_FILE"
    return 1
  fi
  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi
  rm -f "$PID_FILE"
  return 1
}

show_status() {
  if is_running; then
    local pid
    pid="$(cat "$PID_FILE")"
    echo "[dev_server] RUNNING pid=$pid"
    echo "[dev_server] log=$LOG_FILE"
  else
    echo "[dev_server] STOPPED"
  fi
}

start_server() {
  local profile="${1:-web_guard}"
  if [[ "$profile" != "mock" && "$profile" != "web_guard" ]]; then
    echo "[dev_server] Unsupported profile: $profile"
    usage
    exit 1
  fi
  if is_running; then
    echo "[dev_server] already running."
    show_status
    return 0
  fi
  "$SCRIPT_DIR/run_local_stack.sh" --profile "$profile"
}

stop_server() {
  "$SCRIPT_DIR/stop_local_stack.sh"
}

restart_server() {
  local profile="${1:-web_guard}"
  stop_server
  start_server "$profile"
}

show_logs() {
  local lines="${1:-80}"
  if [[ ! -f "$LOG_FILE" ]]; then
    echo "[dev_server] log file not found: $LOG_FILE"
    return 0
  fi
  tail -n "$lines" "$LOG_FILE"
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    start)
      start_server "${2:-web_guard}"
      ;;
    stop)
      stop_server
      ;;
    restart)
      restart_server "${2:-web_guard}"
      ;;
    status)
      show_status
      ;;
    logs)
      show_logs "${2:-80}"
      ;;
    -h|--help|help|"")
      usage
      ;;
    *)
      echo "[dev_server] Unknown command: $cmd"
      usage
      exit 1
      ;;
  esac
}

main "$@"
