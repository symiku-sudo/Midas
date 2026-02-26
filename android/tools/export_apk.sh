#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_SCRIPT="$SCRIPT_DIR/wsl_android_build.sh"

BUILD_TYPE="debug"
OUTPUT_DIR="$ANDROID_DIR/.tmp/apk"
OUTPUT_NAME=""
SKIP_BUILD="0"

usage() {
  cat <<'EOF'
Usage:
  tools/export_apk.sh [options]

Options:
  --debug                 Export debug APK (default)
  --release               Export release APK
  --output <dir>          Output directory (default: android/.tmp/apk)
  --name <filename.apk>   Custom output file name
  --skip-build            Do not run Gradle build, export existing APK only
  -h, --help              Show help

Examples:
  tools/export_apk.sh
  tools/export_apk.sh --release
  tools/export_apk.sh --output /mnt/d/Exports --name midas-debug.apk
  tools/export_apk.sh --skip-build

Notes:
  - release build may output unsigned APK if no signing config is set.
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
        echo "[export_apk] missing value for --output"
        exit 1
      fi
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --name)
      if [[ $# -lt 2 ]]; then
        echo "[export_apk] missing value for --name"
        exit 1
      fi
      OUTPUT_NAME="$2"
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
      echo "[export_apk] unsupported argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$OUTPUT_NAME" ]]; then
  timestamp="$(date +%Y%m%d_%H%M%S)"
  OUTPUT_NAME="midas-${BUILD_TYPE}-${timestamp}.apk"
fi
if [[ "$OUTPUT_NAME" != *.apk ]]; then
  OUTPUT_NAME="${OUTPUT_NAME}.apk"
fi

if [[ "$SKIP_BUILD" != "1" ]]; then
  if [[ ! -x "$BUILD_SCRIPT" ]]; then
    echo "[export_apk] build script not executable: $BUILD_SCRIPT"
    exit 1
  fi
  if [[ "$BUILD_TYPE" == "debug" ]]; then
    "$BUILD_SCRIPT" ":app:assembleDebug"
  else
    "$BUILD_SCRIPT" ":app:assembleRelease"
  fi
fi

candidate_apks=()
if [[ "$BUILD_TYPE" == "debug" ]]; then
  candidate_apks+=(
    "$ANDROID_DIR/.build-wsl/app/outputs/apk/debug/app-debug.apk"
    "$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
  )
else
  candidate_apks+=(
    "$ANDROID_DIR/.build-wsl/app/outputs/apk/release/app-release.apk"
    "$ANDROID_DIR/.build-wsl/app/outputs/apk/release/app-release-unsigned.apk"
    "$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk"
    "$ANDROID_DIR/app/build/outputs/apk/release/app-release-unsigned.apk"
  )
fi

SRC_APK=""
for candidate in "${candidate_apks[@]}"; do
  if [[ -f "$candidate" ]]; then
    SRC_APK="$candidate"
    break
  fi
done

if [[ -z "$SRC_APK" ]]; then
  echo "[export_apk] APK not found. Checked:"
  for candidate in "${candidate_apks[@]}"; do
    echo "  - $candidate"
  done
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_NAME"
LATEST_PATH="$OUTPUT_DIR/midas-${BUILD_TYPE}-latest.apk"

cp -f "$SRC_APK" "$OUTPUT_PATH"
cp -f "$SRC_APK" "$LATEST_PATH"

echo "[export_apk] build_type=$BUILD_TYPE"
echo "[export_apk] source=$SRC_APK"
echo "[export_apk] output=$OUTPUT_PATH"
echo "[export_apk] latest=$LATEST_PATH"
