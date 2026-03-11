#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCENARIO="${1:-bootstrap-missing-openclaw}"

cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export HOME="$REPO_ROOT/rehearsal/runtime/home"
/bin/bash rehearsal/scripts/prepare-system-bin.sh >/dev/null
export PATH="$REPO_ROOT/rehearsal/bin:$REPO_ROOT/rehearsal/runtime/bin:$REPO_ROOT/rehearsal/runtime/system-bin"

set -a
source rehearsal/env/openclaw-watchdog.rehearsal.env
source rehearsal/env/openclaw-backup.rehearsal.env
set +a

/bin/bash rehearsal/scripts/reset-runtime.sh --quiet
/bin/bash rehearsal/scripts/prepare-system-bin.sh >/dev/null
export PATH="$REPO_ROOT/rehearsal/bin:$REPO_ROOT/rehearsal/runtime/bin:$REPO_ROOT/rehearsal/runtime/system-bin"

write_state() {
  cat > rehearsal/runtime/shim-state.json
}

write_valid_config() {
  mkdir -p "$(dirname "$OPENCLAW_CONFIG")"
  cp rehearsal/fixtures/healthy-openclaw-config.json "$OPENCLAW_CONFIG"
}

write_drifted_config() {
  mkdir -p "$(dirname "$OPENCLAW_CONFIG")"
  cat > "$OPENCLAW_CONFIG" <<'EOF'
{
  "channels": {
    "feishu": {
      "accounts": {
        "main": {
          "appId": "drifted-feishu-app-id",
          "appSecret": "drifted-feishu-app-secret",
          "botName": "OpenClaw"
        }
      },
      "defaultAccount": "main",
      "enabled": false
    },
    "qqbot": {
      "appId": "drifted-qq-app-id",
      "clientSecret": "drifted-qq-client-secret",
      "enabled": true
    }
  },
  "logging": {
    "file": "rehearsal/runtime/logs/openclaw-runtime.log"
  }
}
EOF
}

write_invalid_config() {
  mkdir -p "$(dirname "$OPENCLAW_CONFIG")"
  cat > "$OPENCLAW_CONFIG" <<'EOF'
{"channels": {"qqbot": }
EOF
}

write_last_good_manifest() {
  mkdir -p "$(dirname "$WATCHDOG_LAST_GOOD_MANIFEST_FILE")"
  cat > "$WATCHDOG_LAST_GOOD_MANIFEST_FILE"
}

fingerprint_file() {
  python3 - <<'PY' "$1"
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}

write_feishu_markers() {
  cat > "$OPENCLAW_BOOTSTRAP_LOG_FILE" <<'EOF'
[plugins] feishu_doc: Registered feishu_doc, feishu_app_scopes
[plugins] feishu_chat: Registered feishu_chat tool
[plugins] feishu_wiki: Registered feishu_wiki tool
[plugins] feishu_drive: Registered feishu_drive tool
[plugins] feishu_perm: Registered feishu_perm tool
[plugins] feishu_bitable: Registered bitable tools
[plugins] [MCP] Plugin registered
EOF
}

case "$SCENARIO" in
  bootstrap-missing-openclaw)
    write_state <<'EOF'
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
    ;;
  bootstrap-openclaw-missing-plugin)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_feishu_markers
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4301"],
  "main_pid": "4301",
  "next_pid": 4302,
  "plugin_install_fails": false,
  "plugins": [],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": true
}
EOF
    ;;
  bootstrap-install-openclaw)
    write_feishu_markers
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "next_pid": 4400,
  "plugin_install_fails": false,
  "plugins": [],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": false
}
EOF
    ;;
  watchdog-recovery)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "next_pid": 4500,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": false
}
EOF
    ;;
  watchdog-failed-fallback|watchdog-incidents-open|watchdog-incidents-resolved|watchdog-metrics-open-incident|watchdog-metrics-resolved|watchdog-metrics-operator-context|watchdog-report-operator-attention|watchdog-report-operator-attention-cleared|watchdog-incident-attention-filter|watchdog-incident-queue|watchdog-incident-operator-open|watchdog-incident-operator-resolved|watchdog-incident-operator-reset|watchdog-incident-timeline-open|watchdog-incident-timeline-resolved|watchdog-incident-notes-query)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_valid_config
    printf '1' > "$WATCHDOG_FAILURE_COUNT_FILE"
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "next_pid": 4600,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "inactive",
  "service_active": false
}
EOF
    ;;
  watchdog-active-no-listener-grace|watchdog-metrics-healthy)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4800"],
  "listener_pids_sequence": [[], ["4800"], ["4800"]],
  "main_pid": "4800",
  "next_pid": 4801,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": true
}
EOF
    ;;
  watchdog-service-layer-degraded)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4900"],
  "main_pid": "4900",
  "next_pid": 4901,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": true,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-service-layer-threshold-recovery)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    printf '{\n  "service_probe_failures": 1\n}\n' > "$WATCHDOG_RUN_STATE_FILE"
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4950"],
  "main_pid": "4950",
  "next_pid": 4951,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": true,
  "service_level_reachable_sequence": [false, false, true]
    }
EOF
    ;;
  watchdog-service-layer-transient-retry)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4920"],
  "main_pid": "4920",
  "next_pid": 4921,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": true,
  "service_level_reachable_sequence": [false, true]
}
EOF
    ;;
  watchdog-conversation-probe-ready)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": true,
  "conversation_summary": "gateway reachable and channels configured",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4960"],
  "main_pid": "4960",
  "minimal_usable_ready": true,
  "next_pid": 4961,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": true,
  "service_level_reachable": true
}
EOF
    ;;
  watchdog-conversation-probe-minimal)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: degraded"],
  "conversation_ready": false,
  "conversation_summary": "gateway reachable but only a minimal conversation path is usable",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4965"],
  "main_pid": "4965",
  "minimal_usable_ready": true,
  "next_pid": 4966,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": true,
  "service_level_reachable": true
}
EOF
    ;;
  watchdog-conversation-probe-down)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": false,
  "conversation_summary": "gateway process is up but there is no usable conversation path",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4970"],
  "main_pid": "4970",
  "minimal_usable_ready": false,
  "next_pid": 4971,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": true,
  "service_level_reachable": true
}
EOF
    ;;
  watchdog-restart-priority-recovery|watchdog-recovery-notify-normal)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": true,
  "conversation_summary": "restart should restore the primary conversation path",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": true,
  "next_pid": 4975,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "healthy",
  "service_active": false,
  "service_level_reachable": true
}
EOF
    ;;
  watchdog-rollback-priority-before-doctor)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_invalid_config
    mkdir -p "$(dirname "$WATCHDOG_LAST_GOOD_CONFIG")"
    cp rehearsal/fixtures/healthy-openclaw-config.json "$WATCHDOG_LAST_GOOD_CONFIG"
    write_last_good_manifest <<'EOF'
{
  "current_file": "rehearsal/runtime/watchdog/openclaw.last-good.json",
  "current_generation": "generation-rollback-1",
  "generations": [
    {
      "conversation_ready": true,
      "fingerprint": "fixture-healthy-openclaw",
      "generation_id": "generation-rollback-1",
      "health_level": "healthy",
      "minimal_usable_ready": true,
      "path": "rehearsal/runtime/watchdog/openclaw.last-good.json",
      "summary": "validated healthy fixture",
      "validated_at": "2026-03-09T13:00:00+08:00"
    }
  ],
  "validated_at": "2026-03-09T13:00:00+08:00"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": true,
  "conversation_summary": "rollback should restore the validated conversation path",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": true,
  "next_pid": 4980,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "healthy",
  "service_active": false,
  "service_level_reachable": true
}
EOF
    ;;
  watchdog-doctor-deferred-until-survival-fails)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_invalid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": true,
  "conversation_summary": "doctor repair should run only after restart and rollback are unavailable",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": true,
  "next_pid": 4985,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": true,
  "repair_message": "Doctor repair rebuilt the config",
  "restart_mode": "healthy",
  "service_active": false,
  "service_level_reachable": true
}
EOF
    ;;
  watchdog-survival-mode-recovery)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": false,
  "conversation_summary": "survival mode should restore a minimal QQ-only conversation path",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 4988,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "inactive",
  "service_active": false,
  "service_level_reachable": false,
  "survival_recovery_mode": "minimal"
}
EOF
    ;;
  watchdog-survival-mode-sticky-until-stable)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": false,
  "conversation_summary": "survival mode should stay sticky until the recovered full path is stable",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 4994,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "inactive",
  "service_active": false,
  "service_level_reachable": false,
  "survival_recovery_mode": "minimal"
}
EOF
    ;;
  watchdog-survival-mode-exit)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": false,
  "conversation_summary": "survival mode should wait for operator reconfig before clearing",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 4996,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "inactive",
  "service_active": false,
  "service_level_reachable": false,
  "survival_recovery_mode": "full"
}
EOF
    ;;
  watchdog-config-drift-guard)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_drifted_config
    mkdir -p "$(dirname "$WATCHDOG_LAST_GOOD_CONFIG")"
    cp rehearsal/fixtures/healthy-openclaw-config.json "$WATCHDOG_LAST_GOOD_CONFIG"
    HEALTHY_FINGERPRINT="$(fingerprint_file "$WATCHDOG_LAST_GOOD_CONFIG")"
    ENV_FINGERPRINT="$(fingerprint_file rehearsal/env/openclaw-watchdog.rehearsal.env)"
    write_last_good_manifest <<EOF
{
  "current_file": "$WATCHDOG_LAST_GOOD_CONFIG",
  "current_generation": "generation-drift-1",
  "generations": [
    {
      "conversation_ready": true,
      "fingerprint": "$HEALTHY_FINGERPRINT",
      "generation_id": "generation-drift-1",
      "health_level": "healthy",
      "minimal_usable_ready": true,
      "path": "$WATCHDOG_LAST_GOOD_CONFIG",
      "protected_paths": [
        {
          "exists": true,
          "fingerprint": "$HEALTHY_FINGERPRINT",
          "kind": "file",
          "label": "openclaw_config",
          "path": "$OPENCLAW_CONFIG"
        },
        {
          "exists": true,
          "fingerprint": "$ENV_FINGERPRINT",
          "kind": "file",
          "label": "env_file",
          "path": "rehearsal/env/openclaw-watchdog.rehearsal.env"
        }
      ],
      "summary": "validated healthy fixture",
      "validated_at": "2026-03-09T15:30:00+08:00"
    }
  ],
  "validated_at": "2026-03-09T15:30:00+08:00"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": false,
  "conversation_summary": "rollback should restore the last-good config after drift is detected",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 4992,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "healthy"],
  "restart_profile_sequence": ["down", "ready"],
  "service_active": false,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-last-good-generation-selection)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_invalid_config
    mkdir -p rehearsal/runtime/watchdog/rollback-archives
    cp rehearsal/fixtures/healthy-openclaw-config.json rehearsal/runtime/watchdog/rollback-archives/last-good.generation-older.json
    write_last_good_manifest <<'EOF'
{
  "current_file": "rehearsal/runtime/watchdog/openclaw.last-good.json",
  "current_generation": "generation-latest-missing",
  "generations": [
    {
      "conversation_ready": true,
      "fingerprint": "missing-fixture",
      "generation_id": "generation-latest-missing",
      "health_level": "healthy",
      "minimal_usable_ready": true,
      "path": "rehearsal/runtime/watchdog/rollback-archives/last-good.generation-latest-missing.json",
      "summary": "latest validated candidate missing on disk",
      "validated_at": "2026-03-09T13:10:00+08:00"
    },
    {
      "conversation_ready": true,
      "fingerprint": "older-fixture",
      "generation_id": "generation-older",
      "health_level": "healthy",
      "minimal_usable_ready": true,
      "path": "rehearsal/runtime/watchdog/rollback-archives/last-good.generation-older.json",
      "summary": "older validated candidate",
      "validated_at": "2026-03-09T12:50:00+08:00"
    }
  ],
  "validated_at": "2026-03-09T13:10:00+08:00"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": true,
  "conversation_summary": "rollback should skip the missing latest generation and use the older validated one",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": true,
  "next_pid": 4990,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "healthy",
  "service_active": false,
  "service_level_reachable": true
}
EOF
    ;;
  watchdog-config-invalid-rollback)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_invalid_config
    mkdir -p "$(dirname "$WATCHDOG_LAST_GOOD_CONFIG")"
    cp rehearsal/fixtures/healthy-openclaw-config.json "$WATCHDOG_LAST_GOOD_CONFIG"
    write_state <<'EOF'
{
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "next_pid": 4700,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "Applied simulated repair steps",
  "restart_mode": "healthy",
  "service_active": false
}
EOF
    ;;
  watchdog-env-drift-rollback|watchdog-plugin-drift-rollback)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_valid_config
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": true,
  "conversation_summary": "healthy baseline should be archived before protected-path drift is introduced",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": ["4998"],
  "main_pid": "4998",
  "minimal_usable_ready": true,
  "next_pid": 4999,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "healthy",
  "service_active": true,
  "service_level_reachable": true
}
EOF
    ;;
  *)
    echo "Unknown scenario: $SCENARIO" >&2
    exit 1
    ;;
esac

echo "Applied scenario: $SCENARIO"
