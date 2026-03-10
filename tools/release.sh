#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_DIR="$ROOT_DIR/server"

BUILD_TYPE="debug"
OUTPUT_ARGS=()
OUTPUT_DIR=""
SKIP_BUILD="0"
SHARE_TAILNET="0"
SHARE_PORT="8765"
NOTIFY_NTFY="${MIDAS_RELEASE_NOTIFY_NTFY:-0}"

usage() {
  cat <<'EOF'
Usage:
  tools/release.sh [options]

Options:
  --debug                 Export debug APK (default)
  --release               Export release APK
  --output <dir>          Output directory for exported APK
  --name <filename.apk>   Output APK file name
  --skip-build            Skip Gradle assemble and export existing APK only
  --share-tailnet         Share latest APK over Tailscale URL (best effort)
  --share-port <port>     Share HTTP port for APK file (default: 8765)
  --notify-ntfy           Send ntfy notification when flow completes (best effort)
  -h, --help              Show help

Flow:
  1) strict selfcheck (fail => stop)
  2) restart mobile server
  3) export APK
  4) (optional) share APK via tailnet URL
  5) (optional) send ntfy notification
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
      BUILD_TYPE="debug"
      shift
      ;;
    --release)
      BUILD_TYPE="release"
      shift
      ;;
    --output)
      if [[ $# -lt 2 ]]; then
        echo "[release] missing value for --output"
        exit 1
      fi
      OUTPUT_ARGS+=("--output" "$2")
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --name)
      if [[ $# -lt 2 ]]; then
        echo "[release] missing value for --name"
        exit 1
      fi
      OUTPUT_ARGS+=("--name" "$2")
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD="1"
      shift
      ;;
    --share-tailnet)
      SHARE_TAILNET="1"
      shift
      ;;
    --share-port)
      if [[ $# -lt 2 ]]; then
        echo "[release] missing value for --share-port"
        exit 1
      fi
      SHARE_PORT="$2"
      shift 2
      ;;
    --notify-ntfy)
      NOTIFY_NTFY="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[release] unsupported argument: $1"
      usage
      exit 1
      ;;
  esac
done

echo "[release] 1/3 strict selfcheck..."
(
  cd "$SERVER_DIR"
  if [[ ! -x ".venv/bin/python" ]]; then
    echo "[release] missing python venv: $SERVER_DIR/.venv/bin/python"
    exit 1
  fi
  ./.venv/bin/python tools/selfcheck.py
)

echo "[release] 2/3 restart mobile server..."
(
  cd "$ROOT_DIR"
  server/tools/dev_server.sh restart web_guard --mobile
)

echo "[release] 3/3 export APK..."
cmd=("android/tools/export_apk.sh")
if [[ "$BUILD_TYPE" == "release" ]]; then
  cmd+=("--release")
else
  cmd+=("--debug")
fi
if [[ "$SKIP_BUILD" == "1" ]]; then
  cmd+=("--skip-build")
fi
cmd+=("${OUTPUT_ARGS[@]}")
(
  cd "$ROOT_DIR"
  "${cmd[@]}"
)

APK_OUTPUT_DIR="$OUTPUT_DIR"
if [[ -z "$APK_OUTPUT_DIR" ]]; then
  APK_OUTPUT_DIR="$ROOT_DIR/android/.tmp/apk"
elif [[ "$APK_OUTPUT_DIR" != /* ]]; then
  APK_OUTPUT_DIR="$ROOT_DIR/$APK_OUTPUT_DIR"
fi
LATEST_APK_PATH="$APK_OUTPUT_DIR/midas-${BUILD_TYPE}-latest.apk"
if [[ -f "$LATEST_APK_PATH" ]]; then
  APK_SHA256="$(sha256sum "$LATEST_APK_PATH" | awk '{print $1}')"
  APK_MTIME="$(stat -c '%y' "$LATEST_APK_PATH")"
  echo "[release] apk_path=$LATEST_APK_PATH"
  echo "[release] apk_mtime=$APK_MTIME"
  echo "[release] apk_sha256=$APK_SHA256"
fi

if [[ "$SHARE_TAILNET" == "1" ]]; then
  SHARE_APK_PATH="$LATEST_APK_PATH"

  echo "[release] 4/4 share APK over tailnet..."
  if [[ ! -f "$SHARE_APK_PATH" ]]; then
    echo "[release] warning: share target APK not found: $SHARE_APK_PATH"
  elif ! "$ROOT_DIR/android/tools/share_apk_tailnet.sh" \
    --apk "$SHARE_APK_PATH" \
    --port "$SHARE_PORT"; then
    echo "[release] warning: tailnet APK share failed (release artifact still exported)."
  fi
fi

if [[ "$NOTIFY_NTFY" == "1" ]]; then
  echo "[release] notify via ntfy..."
  notify_cmd=("$ROOT_DIR/tools/ntfy_notify.sh")
  if [[ -z "${NTFY_CONFIG_FILE:-}" ]] && [[ -f "$ROOT_DIR/.tmp/ntfy/notify.env" ]]; then
    notify_cmd+=(--config "$ROOT_DIR/.tmp/ntfy/notify.env")
  fi
  if ! "${notify_cmd[@]}"; then
    echo "[release] warning: ntfy notify failed."
  fi
fi

echo "[release] done"
