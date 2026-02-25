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
  tools/dev_server.sh start [web_guard|mock] [--mobile|--host <host>] [--port <port>]
  tools/dev_server.sh stop
  tools/dev_server.sh restart [web_guard|mock] [--mobile|--host <host>] [--port <port>]
  tools/dev_server.sh status
  tools/dev_server.sh logs [lines]

Examples:
  tools/dev_server.sh start
  tools/dev_server.sh start mock
  tools/dev_server.sh start web_guard --mobile
  tools/dev_server.sh start --host 0.0.0.0 --port 8000
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
    show_bind_status "$pid"
  else
    echo "[dev_server] STOPPED"
  fi
}

get_bind_from_pid() {
  local pid="$1"
  local cmdline host port
  cmdline="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  host="$(sed -n 's/.*--host[[:space:]]\([^[:space:]]\+\).*/\1/p' <<<"$cmdline")"
  port="$(sed -n 's/.*--port[[:space:]]\([^[:space:]]\+\).*/\1/p' <<<"$cmdline")"
  if [[ -z "$host" ]]; then
    host="127.0.0.1"
  fi
  if [[ -z "$port" ]]; then
    port="8000"
  fi
  echo "$host $port"
}

show_bind_status() {
  local pid="$1"
  local host port
  read -r host port <<<"$(get_bind_from_pid "$pid")"

  echo "[dev_server] bind=$host:$port"

  local listen_addrs
  listen_addrs="$(ss -ltnp 2>/dev/null | awk -v pid="$pid" '$0 ~ ("pid="pid",") {print $4}' | sort -u)"
  if [[ -n "$listen_addrs" ]]; then
    while IFS= read -r addr; do
      [[ -z "$addr" ]] && continue
      echo "[dev_server] listen=$addr"
    done <<<"$listen_addrs"
  fi

  case "$host" in
    127.0.0.1|localhost)
      echo "[dev_server] access=local-only"
      echo "[dev_server] url=http://127.0.0.1:$port/"
      ;;
    0.0.0.0)
      echo "[dev_server] access=lan+local"
      local lan_ip
      lan_ip="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i !~ /^127\./) {print $i; exit}}')"
      echo "[dev_server] url(local)=http://127.0.0.1:$port/"
      if [[ -n "$lan_ip" ]]; then
        echo "[dev_server] url(lan)=http://$lan_ip:$port/"
      else
        echo "[dev_server] url(lan)=http://<your-lan-ip>:$port/"
      fi
      ;;
    *)
      echo "[dev_server] access=custom-bind"
      echo "[dev_server] url=http://$host:$port/"
      ;;
  esac
}

parse_start_args() {
  local profile="web_guard"
  local host="127.0.0.1"
  local port="8000"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      mock|web_guard)
        profile="$1"
        shift
        ;;
      --mobile|--lan)
        host="0.0.0.0"
        shift
        ;;
      --host)
        if [[ $# -lt 2 ]]; then
          echo "[dev_server] Missing value for --host"
          usage
          exit 1
        fi
        host="$2"
        shift 2
        ;;
      --port)
        if [[ $# -lt 2 ]]; then
          echo "[dev_server] Missing value for --port"
          usage
          exit 1
        fi
        port="$2"
        shift 2
        ;;
      *)
        echo "[dev_server] Unsupported start argument: $1"
        usage
        exit 1
        ;;
    esac
  done

  if [[ "$profile" != "mock" && "$profile" != "web_guard" ]]; then
    echo "[dev_server] Unsupported profile: $profile"
    usage
    exit 1
  fi

  START_PROFILE="$profile"
  START_HOST="$host"
  START_PORT="$port"
}

show_mobile_tip() {
  local host="$1"
  local port="$2"
  if [[ "$host" != "0.0.0.0" ]]; then
    return 0
  fi
  local lan_ip
  lan_ip="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i !~ /^127\./) {print $i; exit}}')"
  if [[ -n "$lan_ip" ]]; then
    echo "[dev_server] Mobile endpoint: http://$lan_ip:$port/"
  else
    echo "[dev_server] Mobile endpoint: http://<your-lan-ip>:$port/"
  fi
}

start_server() {
  parse_start_args "$@"
  if is_running; then
    local pid current_host current_port
    pid="$(cat "$PID_FILE")"
    read -r current_host current_port <<<"$(get_bind_from_pid "$pid")"
    if [[ "$current_host" == "$START_HOST" && "$current_port" == "$START_PORT" ]]; then
      echo "[dev_server] already running with requested bind."
      show_status
      return 0
    fi
    echo "[dev_server] running bind=$current_host:$current_port, switch to $START_HOST:$START_PORT ..."
    stop_server
  fi
  "$SCRIPT_DIR/run_local_stack.sh" \
    --profile "$START_PROFILE" \
    --host "$START_HOST" \
    --port "$START_PORT"
  show_mobile_tip "$START_HOST" "$START_PORT"
}

stop_server() {
  "$SCRIPT_DIR/stop_local_stack.sh"
}

restart_server() {
  parse_start_args "$@"
  stop_server
  start_server "$START_PROFILE" --host "$START_HOST" --port "$START_PORT"
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
      shift
      start_server "$@"
      ;;
    stop)
      stop_server
      ;;
    restart)
      shift
      restart_server "$@"
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
