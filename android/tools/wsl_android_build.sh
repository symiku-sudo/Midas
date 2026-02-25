#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DEFAULT_JAVA_HOME="$HOME/.local/jdk/jdk-17"
DEFAULT_ANDROID_SDK_ROOT="$HOME/Android/Sdk"
DEFAULT_GRADLE_BIN="$ANDROID_DIR/gradle_package/gradle-8.7/bin/gradle"

JAVA_HOME="${JAVA_HOME:-$DEFAULT_JAVA_HOME}"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$DEFAULT_ANDROID_SDK_ROOT}}"
GRADLE_BIN="${GRADLE_BIN:-$DEFAULT_GRADLE_BIN}"

usage() {
  cat <<'EOF'
Usage:
  tools/wsl_android_build.sh [task...]

Examples:
  tools/wsl_android_build.sh
  tools/wsl_android_build.sh :app:assembleDebug
  tools/wsl_android_build.sh :app:assembleDebug :app:testDebugUnitTest

Environment overrides:
  JAVA_HOME
  ANDROID_SDK_ROOT (or ANDROID_HOME)
  GRADLE_BIN
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -x "$GRADLE_BIN" ]]; then
  echo "[wsl_android_build] gradle binary not found: $GRADLE_BIN"
  exit 1
fi

if [[ ! -d "$JAVA_HOME" ]]; then
  echo "[wsl_android_build] JAVA_HOME not found: $JAVA_HOME"
  exit 1
fi

if [[ ! -d "$ANDROID_SDK_ROOT" ]]; then
  echo "[wsl_android_build] ANDROID_SDK_ROOT not found: $ANDROID_SDK_ROOT"
  exit 1
fi

export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_SDK_ROOT
export ANDROID_HOME="$ANDROID_SDK_ROOT"

if ! command -v java >/dev/null 2>&1; then
  echo "[wsl_android_build] java is not available in PATH after JAVA_HOME setup."
  exit 1
fi

LOCAL_PROPERTIES="$ANDROID_DIR/local.properties"
LOCAL_PROPERTIES_BACKUP=""
LOCAL_PROPERTIES_MISSING="0"

restore_local_properties() {
  if [[ "$LOCAL_PROPERTIES_MISSING" == "1" ]]; then
    rm -f "$LOCAL_PROPERTIES"
    return
  fi
  if [[ -n "$LOCAL_PROPERTIES_BACKUP" && -f "$LOCAL_PROPERTIES_BACKUP" ]]; then
    mv -f "$LOCAL_PROPERTIES_BACKUP" "$LOCAL_PROPERTIES"
  fi
}

if [[ -f "$LOCAL_PROPERTIES" ]]; then
  LOCAL_PROPERTIES_BACKUP="$(mktemp)"
  cp "$LOCAL_PROPERTIES" "$LOCAL_PROPERTIES_BACKUP"
else
  LOCAL_PROPERTIES_MISSING="1"
fi
trap restore_local_properties EXIT

printf 'sdk.dir=%s\n' "$ANDROID_SDK_ROOT" > "$LOCAL_PROPERTIES"

TASKS=("$@")
if [[ ${#TASKS[@]} -eq 0 ]]; then
  TASKS=(":app:assembleDebug")
fi

echo "[wsl_android_build] JAVA_HOME=$JAVA_HOME"
echo "[wsl_android_build] ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT"
echo "[wsl_android_build] GRADLE_BIN=$GRADLE_BIN"
echo "[wsl_android_build] tasks=${TASKS[*]}"

cd "$ANDROID_DIR"
"$GRADLE_BIN" "${TASKS[@]}"
