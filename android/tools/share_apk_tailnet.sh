#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TMP_DIR="$ROOT_DIR/.tmp"
PID_FILE="$TMP_DIR/apk_share_http.pid"
LOG_FILE="$TMP_DIR/apk_share_http.log"

APK_PATH=""
PORT="8765"

usage() {
  cat <<'EOF'
Usage:
  android/tools/share_apk_tailnet.sh --apk <path> [--port <port>]

Options:
  --apk <path>            APK file path to expose
  --port <port>           HTTP port for temporary file server (default: 8765)
  -h, --help              Show help

Behavior:
  1) Start background HTTP server at APK directory
  2) Configure Windows portproxy for current Tailscale IPv4 -> WSL port
  3) Print LAN/Tailscale download URLs
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apk)
      if [[ $# -lt 2 ]]; then
        echo "[share_apk] missing value for --apk"
        exit 1
      fi
      APK_PATH="$2"
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        echo "[share_apk] missing value for --port"
        exit 1
      fi
      PORT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[share_apk] unsupported argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$APK_PATH" ]]; then
  echo "[share_apk] --apk is required"
  usage
  exit 1
fi

if [[ ! -f "$APK_PATH" ]]; then
  echo "[share_apk] apk not found: $APK_PATH"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[share_apk] python3 not found"
  exit 1
fi

if ! command -v setsid >/dev/null 2>&1; then
  echo "[share_apk] setsid not found"
  exit 1
fi

if ! command -v powershell.exe >/dev/null 2>&1 || ! command -v cmd.exe >/dev/null 2>&1; then
  echo "[share_apk] windows command bridge not available in current shell"
  exit 1
fi

APK_ABS="$(cd "$(dirname "$APK_PATH")" && pwd -P)/$(basename "$APK_PATH")"
APK_DIR="$(dirname "$APK_ABS")"
APK_NAME="$(basename "$APK_ABS")"

mkdir -p "$TMP_DIR"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" >/dev/null 2>&1; then
    kill "$old_pid" >/dev/null 2>&1 || true
    sleep 1
  fi
fi

(
  cd "$APK_DIR"
  nohup setsid python3 -m http.server "$PORT" --bind 0.0.0.0 </dev/null >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
)

server_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -z "$server_pid" ]] || ! kill -0 "$server_pid" >/dev/null 2>&1; then
  echo "[share_apk] failed to start local HTTP server"
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 30 "$LOG_FILE" || true
  fi
  exit 1
fi

local_check_ok="0"
for _ in $(seq 1 12); do
  if curl --noproxy '*' -I -s --max-time 5 "http://127.0.0.1:${PORT}/${APK_NAME}" >/dev/null 2>&1; then
    local_check_ok="1"
    break
  fi
  sleep 0.5
done
if [[ "$local_check_ok" != "1" ]]; then
  echo "[share_apk] local HTTP check failed on port $PORT"
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 30 "$LOG_FILE" || true
  fi
  exit 1
fi

wsl_ip="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i !~ /^127\./) {print $i; exit}}')"
if [[ -z "$wsl_ip" ]]; then
  echo "[share_apk] failed to detect WSL LAN IP"
  exit 1
fi

ts_ip="$(powershell.exe -NoProfile -Command "tailscale status" 2>/dev/null | tr -d '\r' | awk 'NR==1{print $1}')"
if [[ ! "$ts_ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "[share_apk] failed to detect Tailscale IPv4 from Windows"
  echo "[share_apk] lan_url=http://${wsl_ip}:${PORT}/${APK_NAME}"
  exit 1
fi

rule_name="midas-ts-${PORT}"
cmd.exe /c "netsh interface portproxy delete v4tov4 listenaddress=${ts_ip} listenport=${PORT}" >/dev/null 2>&1 || true
if ! cmd.exe /c "netsh interface portproxy add v4tov4 listenaddress=${ts_ip} listenport=${PORT} connectaddress=${wsl_ip} connectport=${PORT}" >/dev/null 2>&1; then
  echo "[share_apk] failed to configure netsh portproxy (try elevated terminal)"
  echo "[share_apk] lan_url=http://${wsl_ip}:${PORT}/${APK_NAME}"
  exit 1
fi

cmd.exe /c "netsh advfirewall firewall delete rule name=\"${rule_name}\"" >/dev/null 2>&1 || true
cmd.exe /c "netsh advfirewall firewall add rule name=\"${rule_name}\" dir=in action=allow protocol=TCP localip=${ts_ip} localport=${PORT}" >/dev/null 2>&1 || true

tailscale_url="http://${ts_ip}:${PORT}/${APK_NAME}"
if ! curl --noproxy '*' -I -s --max-time 8 "$tailscale_url" >/dev/null 2>&1; then
  echo "[share_apk] warning: tailscale URL probe failed, but share service is running."
fi

echo "[share_apk] apk=$APK_ABS"
echo "[share_apk] pid=$server_pid"
echo "[share_apk] log=$LOG_FILE"
echo "[share_apk] lan_url=http://${wsl_ip}:${PORT}/${APK_NAME}"
echo "[share_apk] tailscale_url=$tailscale_url"
