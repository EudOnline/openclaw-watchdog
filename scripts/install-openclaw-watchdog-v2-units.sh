#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "[deprecated] scripts/install-openclaw-watchdog-v2-units.sh is deprecated; use scripts/install-openclaw-watchdog-units.sh instead." >&2
exec "$REPO_ROOT/scripts/install-openclaw-watchdog-units.sh" "$@"
