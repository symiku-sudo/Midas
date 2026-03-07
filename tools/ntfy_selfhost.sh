#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PARENT_DIR="$(cd "$ROOT_DIR/.." && pwd)"
SUBMODULE_REPO_DIR="$SCRIPT_DIR/ntfy-notify"
LEGACY_REPO_DIR="$PARENT_DIR/ntfy-notify"

if [[ -n "${NTFY_NOTIFY_REPO_DIR:-}" ]]; then
  REPO_DIR="$NTFY_NOTIFY_REPO_DIR"
elif [[ -f "$SUBMODULE_REPO_DIR/ntfy_selfhost.sh" ]]; then
  REPO_DIR="$SUBMODULE_REPO_DIR"
else
  REPO_DIR="$LEGACY_REPO_DIR"
fi

TARGET="$REPO_DIR/ntfy_selfhost.sh"

if [[ ! -f "$TARGET" ]]; then
  echo "[midas ntfy] external selfhost tool not found: $TARGET"
  echo "[midas ntfy] run: git submodule update --init --recursive"
  echo "[midas ntfy] or set NTFY_NOTIFY_REPO_DIR=<path-to-ntfy-notify>"
  exit 1
fi

if [[ ! -x "$TARGET" ]]; then
  chmod +x "$TARGET" 2>/dev/null || true
fi

exec "$TARGET" "$@"
