#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-docs/p7a-live}"
mkdir -p "$OUT_DIR"

run_capture() {
  local name="$1"
  shift
  "$@" > "$OUT_DIR/$name"
}

run_capture "status-summary.txt" ./scripts/openclaw-watchdog status --summary
run_capture "status.json" ./scripts/openclaw-watchdog status --json
run_capture "report-message.txt" ./scripts/openclaw-watchdog report --message
run_capture "report.json" ./scripts/openclaw-watchdog report --json --limit 3
run_capture "metrics.json" ./scripts/openclaw-watchdog metrics --json
run_capture "metrics.prom" ./scripts/openclaw-watchdog metrics --prometheus
run_capture "incidents-list.txt" ./scripts/openclaw-watchdog incidents list --limit 5
if ! ./scripts/openclaw-watchdog incidents current --json > "$OUT_DIR/incidents-current.json"; then
  printf '{}
' > "$OUT_DIR/incidents-current.json"
fi
run_capture "openclaw-status.txt" openclaw status

python3 - <<'PY2' "$OUT_DIR"
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
status = json.loads((out / 'status.json').read_text(encoding='utf-8'))
report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
metrics = json.loads((out / 'metrics.json').read_text(encoding='utf-8'))
inc_current = json.loads((out / 'incidents-current.json').read_text(encoding='utf-8'))
status_summary = (out / 'status-summary.txt').read_text(encoding='utf-8').strip()
metrics_prom = (out / 'metrics.prom').read_text(encoding='utf-8')

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
    'checks': {
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
        'metrics_prom_has_operator_context': 'openclaw_watchdog_current_incident_owner_assigned ' in metrics_prom and 'openclaw_watchdog_current_incident_acknowledged ' in metrics_prom,
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
                'current_incident_events_count',
                'current_incident_latest_event_type',
            ]
        ),
    },
}
summary['all_checks_passed'] = all(summary['checks'].values())
(out / 'acceptance-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + '
', encoding='utf-8')
(out / 'acceptance-summary.txt').write_text(
    '
'.join([
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
        f"report_operator_attention_needed={'true' if report.get('operator_attention_needed') else 'false'}",
        f"all_checks_passed={'true' if summary['all_checks_passed'] else 'false'}",
    ]) + '
',
    encoding='utf-8'
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
if not summary['all_checks_passed']:
    raise SystemExit(1)
PY2
