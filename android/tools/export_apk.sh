#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_SCRIPT="$SCRIPT_DIR/wsl_android_build.sh"
SDK_ROOT_DEFAULT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Android/Sdk}}"
BUILD_TOOLS_DEFAULT="$SDK_ROOT_DEFAULT/build-tools/34.0.0"
APKSIGNER_BIN="${APKSIGNER_BIN:-$BUILD_TOOLS_DEFAULT/apksigner}"
ZIPALIGN_BIN="${ZIPALIGN_BIN:-$BUILD_TOOLS_DEFAULT/zipalign}"
DEBUG_KEYSTORE_PATH="${DEBUG_KEYSTORE_PATH:-$HOME/.android/debug.keystore}"
DEBUG_KEY_ALIAS="${DEBUG_KEY_ALIAS:-androiddebugkey}"
DEBUG_STORE_PASS="${DEBUG_STORE_PASS:-android}"
DEBUG_KEY_PASS="${DEBUG_KEY_PASS:-android}"

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
  - if release build is unsigned, script will try local debug-keystore signing automatically.
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
SRC_MTIME=0
for candidate in "${candidate_apks[@]}"; do
  if [[ ! -f "$candidate" ]]; then
    continue
  fi
  candidate_mtime="$(stat -c %Y "$candidate" 2>/dev/null || echo 0)"
  if [[ -z "$SRC_APK" || "$candidate_mtime" -gt "$SRC_MTIME" ]]; then
    SRC_APK="$candidate"
    SRC_MTIME="$candidate_mtime"
  fi
done

if [[ -z "$SRC_APK" ]]; then
  echo "[export_apk] APK not found. Checked:"
  for candidate in "${candidate_apks[@]}"; do
    echo "  - $candidate"
  done
  exit 1
fi

if [[ "$SKIP_BUILD" == "1" && "$SRC_MTIME" -gt 0 ]]; then
  now_ts="$(date +%s)"
  age_seconds="$((now_ts - SRC_MTIME))"
  if [[ "$age_seconds" -gt 3600 ]]; then
    echo "[export_apk] warning: selected APK is older than 1 hour (age=${age_seconds}s)."
    echo "[export_apk] warning: consider removing --skip-build to force a fresh build."
  fi
fi

SIGNED_TMP_APK=""
if [[ "$BUILD_TYPE" == "release" && "$SRC_APK" == *"-unsigned.apk" ]]; then
  if [[ -x "$APKSIGNER_BIN" && -x "$ZIPALIGN_BIN" && -f "$DEBUG_KEYSTORE_PATH" ]]; then
    signed_dir="$ANDROID_DIR/.tmp/apk/.signed_tmp"
    mkdir -p "$signed_dir"
    signed_base="$(basename "$SRC_APK" .apk)"
    aligned_apk="$signed_dir/${signed_base}-aligned.apk"
    SIGNED_TMP_APK="$signed_dir/${signed_base}-signed-local.apk"
    "$ZIPALIGN_BIN" -f -p 4 "$SRC_APK" "$aligned_apk"
    "$APKSIGNER_BIN" sign \
      --ks "$DEBUG_KEYSTORE_PATH" \
      --ks-key-alias "$DEBUG_KEY_ALIAS" \
      --ks-pass "pass:$DEBUG_STORE_PASS" \
      --key-pass "pass:$DEBUG_KEY_PASS" \
      --out "$SIGNED_TMP_APK" \
      "$aligned_apk"
    rm -f "$aligned_apk"
    SRC_APK="$SIGNED_TMP_APK"
    echo "[export_apk] auto-signed unsigned release APK with local debug keystore."
  else
    echo "[export_apk] warning: unsigned release APK detected, but local debug signing tools/keystore unavailable."
    echo "[export_apk] apksigner=$APKSIGNER_BIN zipalign=$ZIPALIGN_BIN keystore=$DEBUG_KEYSTORE_PATH"
  fi
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
