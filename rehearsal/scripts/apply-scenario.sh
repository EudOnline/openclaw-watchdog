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

seed_model_http_error_failover_fixture() {
  python3 - <<'PY' "$OPENCLAW_CONFIG"
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

config_path = Path(sys.argv[1])
config = json.loads(config_path.read_text(encoding="utf-8"))
model = (
    config.setdefault("agents", {})
    .setdefault("defaults", {})
    .setdefault("model", {})
)
model["primary"] = "openai/gpt-4.1"
model["fallbacks"] = ["anthropic/claude-sonnet-4", "openai/gpt-4o"]
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

log_path = Path("rehearsal/runtime/logs/openclaw-runtime.log")
log_path.parent.mkdir(parents=True, exist_ok=True)
now = datetime.now().astimezone()
events = [
    {
        "timestamp": (now - timedelta(minutes=3)).isoformat(timespec="seconds"),
        "status": 503,
        "model": "openai/gpt-4.1",
        "provider": "openai",
        "message": "upstream model returned HTTP 503 during chat/completions",
    },
    {
        "timestamp": (now - timedelta(minutes=2)).isoformat(timespec="seconds"),
        "status": 502,
        "model": "openai/gpt-4.1",
        "provider": "openai",
        "message": "provider gateway reported status=502 for model request",
    },
    {
        "timestamp": (now - timedelta(minutes=1)).isoformat(timespec="seconds"),
        "status": 429,
        "model": "openai/gpt-4.1",
        "provider": "openai",
        "message": "model upstream rate limited request with HTTP 429",
    },
]
log_path.write_text(
    "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in events) + "\n",
    encoding="utf-8",
)
PY
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

write_litellm_response() {
  mkdir -p "$HOME"
  cat > "$HOME/litellm-response.json"
}

write_cli_response() {
  local cli_name="$1"
  mkdir -p "$HOME"
  cat > "$HOME/${cli_name}-response.json"
}

rescue_root() {
  printf '%s' "$HOME/.openclaw-backup/watchdog/rescue"
}

write_rescue_rule() {
  local rule_id="$1"
  mkdir -p "$(rescue_root)/rules"
  cat > "$(rescue_root)/rules/${rule_id}.json"
}

write_rescue_case() {
  local case_id="$1"
  mkdir -p "$(rescue_root)/cases"
  cat > "$(rescue_root)/cases/${case_id}.json"
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
  watchdog-rescue-chain-codex)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-codex-shim.sh >/dev/null
    write_valid_config
    write_cli_response codex <<'EOF'
{
  "plan_id": "plan-codex-rescue",
  "diagnosis": "codex generated restart plan",
  "actions": [{"kind": "restart_service", "params": {}}],
  "validations": ["minimal_usable_ready"],
  "rollback_strategy": "auto",
  "risk_level": "medium",
  "rationale": "codex rehearsal rescue"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured"],
  "conversation_ready": false,
  "conversation_summary": "codex should restore the minimal path after deterministic rescue is exhausted",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 5500,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "doctor could not restore service",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "inactive", "healthy"],
  "restart_profile_sequence": ["down", "down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-rescue-chain-claude-code)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-claude-shim.sh >/dev/null
    write_valid_config
    write_cli_response claude <<'EOF'
{
  "response": "{\"plan_id\":\"plan-claude-rescue\",\"diagnosis\":\"claude generated restart plan\",\"actions\":[{\"kind\":\"restart_service\",\"params\":{}}],\"validations\":[\"minimal_usable_ready\"],\"rollback_strategy\":\"auto\",\"risk_level\":\"medium\",\"rationale\":\"claude rehearsal rescue\"}"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured"],
  "conversation_ready": false,
  "conversation_summary": "claude code should restore the minimal path after deterministic rescue is exhausted",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 5510,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "doctor could not restore service",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "inactive", "healthy"],
  "restart_profile_sequence": ["down", "down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-rescue-chain-gemini-cli)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-gemini-shim.sh >/dev/null
    write_valid_config
    write_cli_response gemini <<'EOF'
{
  "result": {
    "plan_id": "plan-gemini-rescue",
    "diagnosis": "gemini generated restart plan",
    "actions": [{"kind": "restart_service", "params": {}}],
    "validations": ["minimal_usable_ready"],
    "rollback_strategy": "auto",
    "risk_level": "medium",
    "rationale": "gemini rehearsal rescue"
  }
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured"],
  "conversation_ready": false,
  "conversation_summary": "gemini should restore the minimal path after deterministic rescue is exhausted",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 5520,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "doctor could not restore service",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "inactive", "healthy"],
  "restart_profile_sequence": ["down", "down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-rescue-chain-opencode)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    bash rehearsal/scripts/install-opencode-shim.sh >/dev/null
    write_valid_config
    write_cli_response opencode <<'EOF'
{
  "plan_id": "plan-opencode-rescue",
  "diagnosis": "opencode generated restart plan",
  "actions": [{"kind": "restart_service", "params": {}}],
  "validations": ["minimal_usable_ready"],
  "rollback_strategy": "auto",
  "risk_level": "medium",
  "rationale": "opencode rehearsal rescue"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured"],
  "conversation_ready": false,
  "conversation_summary": "opencode should restore the minimal path after deterministic rescue is exhausted",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 5530,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "doctor could not restore service",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "inactive", "healthy"],
  "restart_profile_sequence": ["down", "down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-rescue-chain-litellm)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_litellm_response <<'EOF'
{
  "plan_id": "plan-litellm-rescue",
  "diagnosis": "model-backed restart after deterministic rescue exhausted",
  "actions": [{"kind": "restart_service", "params": {}}],
  "validations": ["minimal_usable_ready"],
  "rollback_strategy": "auto",
  "risk_level": "medium",
  "rationale": "litellm rehearsal rescue"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured"],
  "conversation_ready": false,
  "conversation_summary": "litellm should restore the minimal path after deterministic rescue is exhausted",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 5600,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "doctor could not restore service",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "inactive", "healthy"],
  "restart_profile_sequence": ["down", "down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-rescue-chain-rule-agent)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_rescue_rule process-down-rule-agent <<'EOF'
{
  "rule_id": "process-down-rule-agent",
  "match": {"failure_signature": "process-down"},
  "diagnosis": "offline restart rule",
  "actions": [{"kind": "restart_service", "params": {}}],
  "validations": ["minimal_usable_ready"],
  "risk_level": "low"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured"],
  "conversation_ready": false,
  "conversation_summary": "rule-agent should restore the minimal path after deterministic rescue is exhausted",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 5610,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "doctor could not restore service",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "inactive", "healthy"],
  "restart_profile_sequence": ["down", "down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-candidate-rule-auto-promotion)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_rescue_case case-auto-1 <<'EOF'
{
  "case_id": "case-auto-1",
  "failure_signature": "process-down",
  "status": "recovered",
  "risk_level": "low",
  "candidate_rule": {
    "rule_id": "process-down-litellm",
    "match": {"failure_signature": "process-down"},
    "diagnosis": "litellm restart rescue",
    "actions": [{"kind": "restart_service", "params": {}}],
    "validations": ["minimal_usable_ready"]
  }
}
EOF
    write_rescue_case case-auto-2 <<'EOF'
{
  "case_id": "case-auto-2",
  "failure_signature": "process-down",
  "status": "recovered",
  "risk_level": "low",
  "candidate_rule": {
    "rule_id": "process-down-litellm",
    "match": {"failure_signature": "process-down"},
    "diagnosis": "litellm restart rescue",
    "actions": [{"kind": "restart_service", "params": {}}],
    "validations": ["minimal_usable_ready"]
  }
}
EOF
    write_litellm_response <<'EOF'
{
  "plan_id": "plan-litellm-auto-promote",
  "diagnosis": "third successful litellm restart case",
  "actions": [{"kind": "restart_service", "params": {}}],
  "validations": ["minimal_usable_ready"],
  "rollback_strategy": "auto",
  "risk_level": "low",
  "rationale": "litellm low-risk candidate promotion rehearsal"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured"],
  "conversation_ready": false,
  "conversation_summary": "third low-risk litellm repair should auto-promote a candidate rule",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 5620,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "doctor could not restore service",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "inactive", "healthy"],
  "restart_profile_sequence": ["down", "down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
}
EOF
    ;;
  watchdog-candidate-rule-review-pending)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    write_litellm_response <<'EOF'
{
  "plan_id": "plan-litellm-review",
  "diagnosis": "high-risk litellm config change requires manual review",
  "actions": [{"kind": "restart_service", "params": {}}],
  "validations": ["minimal_usable_ready"],
  "rollback_strategy": "auto",
  "risk_level": "high",
  "rationale": "litellm high-risk candidate review rehearsal"
}
EOF
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured"],
  "conversation_ready": false,
  "conversation_summary": "high-risk litellm repair should create a pending review",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 5630,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "doctor could not restore service",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "inactive", "healthy"],
  "restart_profile_sequence": ["down", "down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
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
  watchdog-model-http-error-failover)
    bash rehearsal/scripts/install-openclaw-shim.sh >/dev/null
    write_valid_config
    seed_model_http_error_failover_fixture
    write_state <<'EOF'
{
  "channel_summary": ["QQ Bot: configured", "Feishu: configured"],
  "conversation_ready": false,
  "conversation_summary": "model failover should rotate to the next provider and restore the minimal path",
  "doctor_fail_message": "",
  "doctor_ok_message": "Doctor OK",
  "listener_pids": [],
  "main_pid": "0",
  "minimal_usable_ready": false,
  "next_pid": 4978,
  "plugin_install_fails": false,
  "plugins": ["@sliverp/qqbot@latest"],
  "repair_fixes_invalid_config": false,
  "repair_message": "SHOULD_NOT_RUN_DOCTOR_REPAIR",
  "restart_mode": "inactive",
  "restart_mode_sequence": ["inactive", "healthy"],
  "restart_profile_sequence": ["down", "minimal"],
  "service_active": false,
  "service_level_reachable": false
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
