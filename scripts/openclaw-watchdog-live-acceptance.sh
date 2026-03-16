#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="docs/p7a-live"
ENV_FILE=""

usage() {
  cat <<'EOF' >&2
Usage: ./scripts/openclaw-watchdog-live-acceptance.sh [--env <path>] [--out-dir <path>]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      [[ $# -ge 2 ]] || {
        usage
        exit 2
      }
      ENV_FILE="$2"
      shift 2
      ;;
    --out-dir)
      [[ $# -ge 2 ]] || {
        usage
        exit 2
      }
      OUT_DIR="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      if [[ $# -eq 1 && "$1" != --* ]]; then
        OUT_DIR="$1"
        shift
      else
        usage
        exit 2
      fi
      ;;
  esac
done

mkdir -p "$OUT_DIR"

WATCHDOG_CMD=(./scripts/openclaw-watchdog)
if [[ -n "$ENV_FILE" ]]; then
  WATCHDOG_CMD+=(--env "$ENV_FILE")
fi

run_capture() {
  local name="$1"
  shift
  "$@" > "$OUT_DIR/$name"
}

run_capture_allow_failure() {
  local name="$1"
  shift
  local output_file="$OUT_DIR/$name"
  local exit_code=0

  set +e
  "$@" >"$output_file" 2>&1
  exit_code=$?
  set -e

  printf '\n__exit_code__=%s\n' "$exit_code" >>"$output_file"
  return 0
}

run_watchdog_capture() {
  local name="$1"
  shift
  run_capture "$name" "${WATCHDOG_CMD[@]}" "$@"
}

eval "$(
  python3 - <<'PY' "$ENV_FILE"
import shlex
import sys
from pathlib import Path

from openclaw_watchdog.config import Config
from openclaw_watchdog.platforms.resolver import resolve_platform

env_arg = sys.argv[1]
env_path = Path(env_arg).expanduser() if env_arg else None
config = Config.load(env_path)
platform = resolve_platform()

values = {
    "ACCEPTANCE_HOST_FAMILY": platform.capabilities.host_family,
    "ACCEPTANCE_SUPERVISOR": platform.capabilities.supervisor,
    "ACCEPTANCE_GATEWAY_SERVICE": config.openclaw_gateway_service,
    "ACCEPTANCE_RESOLVED_ENV_FILE": str(config.env_file) if config.env_file else "",
}

for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"

run_watchdog_capture "status-summary.txt" status --summary
run_watchdog_capture "status.json" status --json
run_watchdog_capture "report-message.txt" report --message
run_watchdog_capture "report.json" report --json --limit 3
run_watchdog_capture "metrics.json" metrics --json
run_watchdog_capture "metrics.prom" metrics --prometheus
run_watchdog_capture "incidents-list.txt" incidents list --limit 5
if ! "${WATCHDOG_CMD[@]}" incidents current --json > "$OUT_DIR/incidents-current.json"; then
  printf '{}\n' > "$OUT_DIR/incidents-current.json"
fi
run_capture "openclaw-status.txt" openclaw status

if [[ "$ACCEPTANCE_HOST_FAMILY" == "darwin" && "$ACCEPTANCE_SUPERVISOR" == "launchd" ]]; then
  run_capture_allow_failure "watchdog-launchd.txt" launchctl print "gui/$UID/com.eudonline.openclaw-watchdog"
  run_capture_allow_failure "gateway-launchd.txt" launchctl print "gui/$UID/$ACCEPTANCE_GATEWAY_SERVICE"
fi

python3 - <<'PY2' "$OUT_DIR" "$ACCEPTANCE_HOST_FAMILY" "$ACCEPTANCE_SUPERVISOR" "$ACCEPTANCE_GATEWAY_SERVICE" "$ACCEPTANCE_RESOLVED_ENV_FILE"
import json
import sys
from pathlib import Path


def capture_succeeded(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    return '__exit_code__=0' in text


out = Path(sys.argv[1])
host_family = sys.argv[2]
supervisor = sys.argv[3]
gateway_service = sys.argv[4]
resolved_env_file = sys.argv[5]
status = json.loads((out / 'status.json').read_text(encoding='utf-8'))
report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
metrics = json.loads((out / 'metrics.json').read_text(encoding='utf-8'))
inc_current = json.loads((out / 'incidents-current.json').read_text(encoding='utf-8'))
status_summary = (out / 'status-summary.txt').read_text(encoding='utf-8').strip()
metrics_prom = (out / 'metrics.prom').read_text(encoding='utf-8')

checks = {
    'status_report_match': status.get('last_status') == report.get('status'),
    'status_metrics_match': status.get('last_status') == metrics.get('status'),
    'health_metrics_match': status.get('health_level') == metrics.get('health_level'),
    'conversation_ready_match': status.get('conversation_ready') == report.get('conversation_ready') == metrics.get('conversation_ready'),
    'minimal_usable_match': status.get('minimal_usable_ready') == report.get('minimal_usable_ready') == metrics.get('minimal_usable_ready'),
    'recovery_strategy_match': status.get('last_recovery_strategy') == report.get('last_recovery_strategy') == metrics.get('last_recovery_strategy'),
    'recovery_path_match': status.get('last_recovery_path') == report.get('last_recovery_path') == metrics.get('last_recovery_path'),
    'metrics_prom_has_info': 'openclaw_watchdog_info{' in metrics_prom,
    'metrics_prom_has_service_active': 'openclaw_watchdog_service_active ' in metrics_prom,
    'metrics_prom_has_survivability_gauges': all(
        key in metrics_prom
        for key in [
            'openclaw_watchdog_conversation_ready ',
            'openclaw_watchdog_minimal_usable_ready ',
            'openclaw_watchdog_survival_mode_active ',
            'openclaw_watchdog_last_recovery_action_count ',
            'openclaw_watchdog_config_drift_detected ',
        ]
    ),
    'metrics_prom_has_operator_context': (
        'openclaw_watchdog_current_incident_owner_assigned ' in metrics_prom
        and 'openclaw_watchdog_current_incident_acknowledged ' in metrics_prom
        and 'openclaw_watchdog_current_incident_notes_count ' in metrics_prom
    ),
    'status_summary_has_probe': 'probe=' in status_summary,
    'status_summary_has_conversation': 'conversation=' in status_summary,
    'status_summary_has_recovery': 'recovery=' in status_summary,
    'incident_current_consistent': (not status.get('current_incident_id') and inc_current == {}) or (status.get('current_incident_id') == inc_current.get('incident_id', '')),
    'report_attention_shape': isinstance(report.get('operator_attention_items', []), list),
    'report_attention_none_when_no_incident': (status.get('current_incident_id') not in (None, '')) or (report.get('operator_attention_needed') is False),
    'report_has_survivability_fields': all(
        key in report
        for key in [
            'conversation_status',
            'conversation_ready',
            'minimal_usable_ready',
            'conversation_probe_summary',
            'survival_mode_active',
            'survival_mode_reason',
            'survival_mode_actions',
            'last_recovery_strategy',
            'last_recovery_path',
            'last_recovery_action_count',
            'last_recovery_restored_conversation',
            'rollback_candidate_used',
            'config_drift_detected',
            'drift_scope',
            'drift_since_last_good',
        ]
    ),
    'metrics_has_survivability_fields': all(
        key in metrics
        for key in [
            'conversation_status',
            'conversation_ready',
            'minimal_usable_ready',
            'conversation_probe_summary',
            'survival_mode_active',
            'survival_mode_reason',
            'survival_mode_actions',
            'last_recovery_strategy',
            'last_recovery_path',
            'last_recovery_action_count',
            'last_recovery_restored_conversation',
            'rollback_candidate_used',
            'config_drift_detected',
            'drift_scope',
            'drift_since_last_good',
            'guard_last_operation',
            'guard_last_summary',
            'last_good_generation_id',
            'last_good_generation_count',
            'last_good_validated_at',
        ]
    ),
    'metrics_has_operator_fields': all(
        key in metrics
        for key in [
            'current_incident_owner',
            'current_incident_owner_assigned',
            'current_incident_acknowledged',
            'current_incident_notes_count',
        ]
    ),
}

summary = {
    'status': status.get('last_status', ''),
    'health_level': status.get('health_level', ''),
    'current_mode': status.get('current_mode', ''),
    'conversation_status': status.get('conversation_status', ''),
    'conversation_ready': bool(status.get('conversation_ready', False)),
    'minimal_usable_ready': bool(status.get('minimal_usable_ready', False)),
    'survival_mode_active': bool(status.get('survival_mode_active', False)),
    'config_drift_detected': bool(status.get('config_drift_detected', False)),
    'last_recovery_strategy': status.get('last_recovery_strategy', 'none'),
    'last_recovery_path': status.get('last_recovery_path', 'none'),
    'rollback_candidate_used': status.get('rollback_candidate_used', '') or 'none',
    'service_probe_summary': status.get('service_probe_summary', ''),
    'conversation_probe_summary': status.get('conversation_probe_summary', ''),
    'recent_incidents_count': metrics.get('recent_incidents_count', 0),
    'current_incident_id': status.get('current_incident_id', ''),
    'host_family': host_family,
    'supervisor': supervisor,
    'gateway_service': gateway_service,
    'resolved_env_file': resolved_env_file,
    'checks': checks,
}

if host_family == 'darwin' and supervisor == 'launchd':
    checks['watchdog_launchd_capture'] = capture_succeeded(out / 'watchdog-launchd.txt')
    checks['gateway_launchd_capture'] = capture_succeeded(out / 'gateway-launchd.txt')

summary['all_checks_passed'] = all(summary['checks'].values())
(out / 'acceptance-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding='utf-8')
(out / 'acceptance-summary.txt').write_text(
    "\n".join([
        f"status={summary['status']}",
        f"health_level={summary['health_level']}",
        f"current_mode={summary['current_mode']}",
        f"conversation_status={summary['conversation_status']}",
        f"conversation_ready={'true' if summary['conversation_ready'] else 'false'}",
        f"minimal_usable_ready={'true' if summary['minimal_usable_ready'] else 'false'}",
        f"survival_mode_active={'true' if summary['survival_mode_active'] else 'false'}",
        f"config_drift_detected={'true' if summary['config_drift_detected'] else 'false'}",
        f"last_recovery_strategy={summary['last_recovery_strategy']}",
        f"last_recovery_path={summary['last_recovery_path']}",
        f"rollback_candidate_used={summary['rollback_candidate_used']}",
        f"service_probe_summary={summary['service_probe_summary']}",
        f"conversation_probe_summary={summary['conversation_probe_summary']}",
        f"recent_incidents_count={summary['recent_incidents_count']}",
        f"current_incident_id={summary['current_incident_id'] or 'none'}",
        f"host_family={summary['host_family']}",
        f"supervisor={summary['supervisor']}",
        f"gateway_service={summary['gateway_service']}",
        f"resolved_env_file={summary['resolved_env_file'] or 'none'}",
        f"report_operator_attention_needed={'true' if report.get('operator_attention_needed') else 'false'}",
        f"all_checks_passed={'true' if summary['all_checks_passed'] else 'false'}",
    ]) + "\n",
    encoding='utf-8'
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
if not summary['all_checks_passed']:
    raise SystemExit(1)
PY2
