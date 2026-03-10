#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"

mkdir -p "$UNIT_DIR"
cp "$REPO_ROOT/systemd/openclaw-watchdog-v2.service" "$UNIT_DIR/openclaw-watchdog-v2.service"
cp "$REPO_ROOT/systemd/openclaw-watchdog-v2.timer" "$UNIT_DIR/openclaw-watchdog-v2.timer"
systemctl --user daemon-reload

echo "Installed sample units to: $UNIT_DIR"
echo "Next steps:"
echo "  systemctl --user enable --now openclaw-watchdog-v2.timer"
