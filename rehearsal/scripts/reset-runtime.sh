#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QUIET="false"

if [[ "${1:-}" == "--quiet" ]]; then
  QUIET="true"
fi

/bin/rm -rf "$REPO_ROOT/rehearsal/runtime"
/bin/mkdir -p \
  "$REPO_ROOT/rehearsal/runtime/bin" \
  "$REPO_ROOT/rehearsal/runtime/system-bin" \
  "$REPO_ROOT/rehearsal/runtime/home/.openclaw" \
  "$REPO_ROOT/rehearsal/runtime/home/.config/opencode" \
  "$REPO_ROOT/rehearsal/runtime/logs" \
  "$REPO_ROOT/rehearsal/runtime/backups" \
  "$REPO_ROOT/rehearsal/runtime/watchdog/rollback-archives" \
  "$REPO_ROOT/rehearsal/runtime/watchdog/incidents" \
  "$REPO_ROOT/rehearsal/runtime/scenario-output"

/bin/cat > "$REPO_ROOT/rehearsal/runtime/shim-state.json" <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "next_pid": 4200,
  "plugin_install_fails": false,
  "plugins": [],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": false
}
EOF

: > "$REPO_ROOT/rehearsal/runtime/logs/journal.log"
: > "$REPO_ROOT/rehearsal/runtime/logs/openclaw-runtime.log"
: > "$REPO_ROOT/rehearsal/runtime/logs/messages.log"
: > "$REPO_ROOT/rehearsal/runtime/logs/opencode.log"
: > "$REPO_ROOT/rehearsal/runtime/logs/codex.log"

if [[ "$QUIET" != "true" ]]; then
  echo "Reset rehearsal runtime under rehearsal/runtime"
fi
