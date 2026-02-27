#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_DIR="$ROOT_DIR/server"

BUILD_TYPE="debug"
OUTPUT_ARGS=()
SKIP_BUILD="0"

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
  -h, --help              Show help

Flow:
  1) strict selfcheck (fail => stop)
  2) restart mobile server
  3) export APK
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

echo "[release] done"
