#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_SRC="$ROOT_DIR/launchd/com.eudonline.openclaw-watchdog.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST_PLIST="$DEST_DIR/com.eudonline.openclaw-watchdog.plist"
STATE_DIR="${WATCHDOG_STATE_DIR:-$HOME/.openclaw-backup/watchdog}"

mkdir -p "$DEST_DIR" "$STATE_DIR"

escaped_root="${ROOT_DIR//\//\\/}"
escaped_state="${STATE_DIR//\//\\/}"
tmp_plist="$(mktemp)"

sed \
  -e "s/__WATCHDOG_REPO_ROOT__/${escaped_root}/g" \
  -e "s/__WATCHDOG_STATE_DIR__/${escaped_state}/g" \
  "$PLIST_SRC" >"$tmp_plist"

launchctl bootout "gui/$UID" "$DEST_PLIST" >/dev/null 2>&1 || true
cp "$tmp_plist" "$DEST_PLIST"
rm -f "$tmp_plist"

launchctl bootstrap "gui/$UID" "$DEST_PLIST"
launchctl enable "gui/$UID/com.eudonline.openclaw-watchdog" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$UID/com.eudonline.openclaw-watchdog" >/dev/null 2>&1 || true

echo "Installed launchd agent:"
echo "  $DEST_PLIST"
echo
echo "Useful commands:"
echo "  launchctl print gui/$UID/com.eudonline.openclaw-watchdog"
echo "  launchctl kickstart -k gui/$UID/com.eudonline.openclaw-watchdog"
echo "  launchctl bootout gui/$UID $DEST_PLIST"
