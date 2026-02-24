#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="$SERVER_DIR/.tmp"
PID_FILE="$TMP_DIR/local_server.pid"
LOG_FILE="$TMP_DIR/local_server.log"

HOST="127.0.0.1"
PORT="8000"
PROFILE="mock"
WAIT_SECONDS="20"
STRICT_SELFCHECK="0"

usage() {
  cat <<'EOF'
Usage:
  tools/run_local_stack.sh [options]

Options:
  --host <host>                Bind host (default: 127.0.0.1)
  --port <port>                Bind port (default: 8000)
  --profile <mock|web_guard>   Smoke profile (default: mock)
  --wait-seconds <n>           Wait seconds for server ready (default: 20)
  --strict-selfcheck           Stop immediately if selfcheck has fail
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --wait-seconds)
      WAIT_SECONDS="$2"
      shift 2
      ;;
    --strict-selfcheck)
      STRICT_SELFCHECK="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[run_local_stack] Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

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

resolve_uvicorn() {
  if [[ -x "$SERVER_DIR/.venv/bin/uvicorn" ]]; then
    echo "$SERVER_DIR/.venv/bin/uvicorn"
    return
  fi
  if command -v uvicorn >/dev/null 2>&1; then
    command -v uvicorn
    return
  fi
  echo ""
}

ensure_venv_bin_on_path() {
  local venv_bin="$SERVER_DIR/.venv/bin"
  if [[ -d "$venv_bin" && ":$PATH:" != *":$venv_bin:"* ]]; then
    export PATH="$venv_bin:$PATH"
  fi
}

ensure_venv_bin_on_path

PYTHON_BIN="$(resolve_python)"
UVICORN_BIN="$(resolve_uvicorn)"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[run_local_stack] Python not found."
  exit 1
fi
if [[ -z "$UVICORN_BIN" ]]; then
  echo "[run_local_stack] Uvicorn not found. Please install server deps first."
  exit 1
fi

mkdir -p "$TMP_DIR"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" >/dev/null 2>&1; then
    echo "[run_local_stack] Existing server is running with PID=$OLD_PID. Stop it first."
    echo "Tip: tools/stop_local_stack.sh"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

echo "[1/3] Running selfcheck..."
set +e
"$PYTHON_BIN" "$SERVER_DIR/tools/selfcheck.py"
SELFCHECK_CODE=$?
set -e

if [[ "$SELFCHECK_CODE" -ne 0 ]]; then
  if [[ "$STRICT_SELFCHECK" == "1" ]]; then
    echo "[run_local_stack] selfcheck failed and strict mode is enabled. Exit."
    exit 1
  fi
  echo "[run_local_stack] selfcheck has failures; continue anyway (non-strict mode)."
fi

echo "[2/3] Starting uvicorn on $HOST:$PORT ..."
nohup "$UVICORN_BIN" app.main:app --app-dir "$SERVER_DIR" --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

cleanup_on_fail() {
  if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  rm -f "$PID_FILE"
}

READY=0
for ((i=1; i<=WAIT_SECONDS; i++)); do
  if "$PYTHON_BIN" - "http://127.0.0.1:$PORT/health" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
try:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=1.0) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
  then
    READY=1
    break
  fi
  sleep 1
done

if [[ "$READY" -ne 1 ]]; then
  echo "[run_local_stack] Server failed to become ready in ${WAIT_SECONDS}s."
  echo "[run_local_stack] Last logs:"
  tail -n 40 "$LOG_FILE" || true
  cleanup_on_fail
  exit 1
fi

echo "[3/3] Running smoke test profile=$PROFILE ..."
if ! "$PYTHON_BIN" "$SERVER_DIR/tools/smoke_test.py" \
  --base-url "http://127.0.0.1:$PORT" \
  --profile "$PROFILE"; then
  echo "[run_local_stack] Smoke test failed."
  echo "[run_local_stack] Last logs:"
  tail -n 40 "$LOG_FILE" || true
  cleanup_on_fail
  exit 1
fi

echo
echo "[run_local_stack] Server is up and smoke passed."
echo "- PID: $SERVER_PID"
echo "- Log: $LOG_FILE"
echo "- Stop: $SERVER_DIR/tools/stop_local_stack.sh"
