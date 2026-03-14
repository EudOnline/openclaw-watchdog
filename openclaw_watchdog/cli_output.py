from __future__ import annotations

import json

from openclaw_watchdog.bootstrap import BootstrapOutcome
from openclaw_watchdog.engine import RunOutcome
from openclaw_watchdog.presenters.bootstrap import render_bootstrap
from openclaw_watchdog.presenters.incidents import render_incident_queue
from openclaw_watchdog.presenters.report import render_report
from openclaw_watchdog.presenters.status import render_status_summary


def print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def print_run_once(outcome: RunOutcome) -> None:
    print(f"state={outcome.state}")
    print(f"summary={outcome.summary}")


def print_check(payload: dict[str, object]) -> None:
    print(f"healthy={str(payload['healthy']).lower()}")
    print(f"healthy_raw={str(payload['healthy_raw']).lower()}")
    print(f"process_layer_healthy={str(payload['process_layer_healthy']).lower()}")
    print(f"service_layer_healthy={str(payload['service_layer_healthy']).lower()}")
    print(f"conversation_ready={str(bool(payload.get('conversation_ready', False))).lower()}")
    print(f"minimal_usable_ready={str(bool(payload.get('minimal_usable_ready', False))).lower()}")
    print(f"conversation_status={payload.get('conversation_status', 'down')}")
    print(f"conversation_probe_summary={payload.get('conversation_probe_summary', 'n/a')}")
    print(f"health_level={payload['health_level']}")
    print(f"current_mode={payload['current_mode']}")
    print(f"service_active={str(payload['service_active']).lower()}")
    print(f"service_main_pid={payload['service_main_pid']}")
    print(f"listener_pids={' '.join(payload['listener_pids']) if payload['listener_pids'] else 'none'}")
    print(f"grace_applied={str(payload['grace_applied']).lower()}")
    print(f"grace_seconds={payload['grace_seconds']}")
    print(f"service_probe_rc={payload['service_probe_rc']}")
    print(f"service_probe_failures={payload['service_probe_failures']}")
    print(f"service_probe_summary={payload['service_probe_summary']}")
    print(f"doctor_rc={payload['doctor_rc']}")
    print(f"config_invalid={str(payload['config_invalid']).lower()}")


def print_status_summary(payload: dict[str, object]) -> None:
    print(render_status_summary(payload))


def print_report(payload: dict[str, object]) -> None:
    print(render_report(payload))


def print_metrics(payload: dict[str, object]) -> None:
    print(f"status={payload.get('status', 'unknown')}")
    print(f"conversation_status={payload.get('conversation_status', 'down')}")
    print(f"conversation_ready={str(bool(payload.get('conversation_ready', False))).lower()}")
    print(f"minimal_usable_ready={str(bool(payload.get('minimal_usable_ready', False))).lower()}")
    print(f"health_level={payload.get('health_level', 'unknown')}")
    print(f"current_mode={payload.get('current_mode', 'unknown')}")
    print(f"service_active={str(bool(payload.get('service_active', False))).lower()}")
    print(f"process_layer_healthy={str(bool(payload.get('process_layer_healthy', False))).lower()}")
    print(f"service_layer_healthy={str(bool(payload.get('service_layer_healthy', False))).lower()}")
    print(f"last_recovery_strategy={payload.get('last_recovery_strategy', 'none')}")
    print(f"last_recovery_path={payload.get('last_recovery_path', 'none')}")
    print(f"last_recovery_action_count={payload.get('last_recovery_action_count', 0)}")
    print(f"last_recovery_restored_conversation={str(bool(payload.get('last_recovery_restored_conversation', False))).lower()}")
    print(f"rollback_candidate_used={payload.get('rollback_candidate_used', '') or 'none'}")
    print(f"rollback_reason={payload.get('rollback_reason', '') or 'none'}")
    print(f"config_drift_detected={str(bool(payload.get('config_drift_detected', False))).lower()}")
    print(f"drift_scope={','.join(payload.get('drift_scope', [])) if isinstance(payload.get('drift_scope', []), list) and payload.get('drift_scope', []) else 'none'}")
    print(f"drift_since_last_good={payload.get('drift_since_last_good', '') or 'none'}")
    print(f"survival_mode_active={str(bool(payload.get('survival_mode_active', False))).lower()}")
    print(f"survival_mode_reason={payload.get('survival_mode_reason', '') or 'none'}")
    print(f"survival_mode_since={payload.get('survival_mode_since', '') or 'none'}")
    print(f"survival_mode_actions_count={len(payload.get('survival_mode_actions', [])) if isinstance(payload.get('survival_mode_actions', []), list) else 0}")
    print(f"survival_mode_sticky={str(bool(payload.get('survival_mode_sticky', False))).lower()}")
    print(f"survival_mode_sticky_reason={payload.get('survival_mode_sticky_reason', '') or 'none'}")
    print(f"survival_mode_exit_ready={str(bool(payload.get('survival_mode_exit_ready', False))).lower()}")
    print(f"survival_mode_exit_policy={payload.get('survival_mode_exit_policy', '') or 'none'}")
    print(f"survival_mode_exit_blockers={'; '.join(payload.get('survival_mode_exit_blockers', [])) if isinstance(payload.get('survival_mode_exit_blockers', []), list) and payload.get('survival_mode_exit_blockers', []) else 'none'}")
    print(f"survival_mode_stable_ready_runs={payload.get('survival_mode_stable_ready_runs', 0)}")
    print(f"survival_mode_stable_required_runs={payload.get('survival_mode_stable_required_runs', 0)}")
    print(f"survival_mode_manual_clear_required={str(bool(payload.get('survival_mode_manual_clear_required', False))).lower()}")
    print(f"survival_mode_config_changed_away={str(bool(payload.get('survival_mode_config_changed_away', False))).lower()}")
    print(f"survival_mode_last_exit_at={payload.get('survival_mode_last_exit_at', '') or 'none'}")
    print(f"survival_mode_last_exit_reason={payload.get('survival_mode_last_exit_reason', '') or 'none'}")
    print(f"survival_mode_last_exit_kind={payload.get('survival_mode_last_exit_kind', '') or 'none'}")
    print(f"survival_mode_last_exit_summary={payload.get('survival_mode_last_exit_summary', '') or 'none'}")
    print(f"guard_last_operation={payload.get('guard_last_operation', '') or 'none'}")
    print(f"guard_last_summary={payload.get('guard_last_summary', '') or 'none'}")
    print(f"last_good_validated_at={payload.get('last_good_validated_at', '') or 'none'}")
    print(f"consecutive_failures={payload.get('consecutive_failures', 0)}")
    print(f"service_probe_failures={payload.get('service_probe_failures', 0)}")
    print(f"current_incident_open={str(bool(payload.get('current_incident_open', False))).lower()}")
    print(f"current_incident_id={payload.get('current_incident_id', '') or 'none'}")
    print(f"current_incident_state={payload.get('current_incident_state', '') or 'none'}")
    print(f"current_incident_age_seconds={payload.get('current_incident_age_seconds', 0)}")
    print(f"current_incident_owner={payload.get('current_incident_owner', '') or 'none'}")
    print(f"current_incident_owner_assigned={str(bool(payload.get('current_incident_owner_assigned', False))).lower()}")
    print(f"current_incident_acknowledged={str(bool(payload.get('current_incident_acknowledged', False))).lower()}")
    print(f"current_incident_notes_count={payload.get('current_incident_notes_count', 0)}")
    print(
        "recent_counts="
        f"healthy:{payload.get('recent_healthy_total', 0)},"
        f"degraded:{payload.get('recent_degraded_total', 0)},"
        f"recovered:{payload.get('recent_recovered_total', 0)},"
        f"failed:{payload.get('recent_failed_total', 0)}"
    )
    print(f"recent_incidents_count={payload.get('recent_incidents_count', 0)}")
    print(f"last_run_duration_ms={payload.get('last_run_duration_ms', 0)}")
    print(f"last_success_at={payload.get('last_success_at', '') or 'none'}")
    print(f"last_failed_at={payload.get('last_failed_at', '') or 'none'}")
    print(f"last_recovered_at={payload.get('last_recovered_at', '') or 'none'}")


def print_status(payload: dict[str, object]) -> None:
    maintenance = payload["maintenance"]
    run_state = payload.get("run_state", {})
    last_event = payload.get("last_event", {})
    recent_events = payload.get("recent_events", [])
    recent_stats = payload.get("recent_event_stats", {})
    counts = recent_stats.get("counts", {}) if isinstance(recent_stats, dict) else {}
    recent_incidents = payload.get("recent_incidents", [])
    print(f"last_status={payload['last_status']}")
    print(f"healthy={str(payload['healthy']).lower()}")
    print(f"healthy_raw={str(payload['healthy_raw']).lower()}")
    print(f"process_layer_healthy={str(payload['process_layer_healthy']).lower()}")
    print(f"service_layer_healthy={str(payload['service_layer_healthy']).lower()}")
    print(f"conversation_ready={str(bool(payload.get('conversation_ready', False))).lower()}")
    print(f"minimal_usable_ready={str(bool(payload.get('minimal_usable_ready', False))).lower()}")
    print(f"conversation_status={payload.get('conversation_status', 'down')}")
    print(f"health_level={payload['health_level']}")
    print(f"current_mode={payload['current_mode']}")
    print(f"last_recovery_strategy={payload.get('last_recovery_strategy', 'none')}")
    print(f"last_recovery_path={payload.get('last_recovery_path', 'none')}")
    print(f"last_recovery_action_count={payload.get('last_recovery_action_count', 0)}")
    print(f"last_recovery_restored_conversation={str(bool(payload.get('last_recovery_restored_conversation', False))).lower()}")
    print(f"rollback_candidate_used={payload.get('rollback_candidate_used', '') or 'none'}")
    print(f"rollback_reason={payload.get('rollback_reason', '') or 'none'}")
    print(f"config_drift_detected={str(bool(payload.get('config_drift_detected', False))).lower()}")
    print(f"drift_scope={','.join(payload.get('drift_scope', [])) if isinstance(payload.get('drift_scope', []), list) and payload.get('drift_scope', []) else 'none'}")
    print(f"drift_since_last_good={payload.get('drift_since_last_good', '') or 'none'}")
    print(f"survival_mode_active={str(bool(payload.get('survival_mode_active', False))).lower()}")
    print(f"survival_mode_reason={payload.get('survival_mode_reason', '') or 'none'}")
    print(f"survival_mode_since={payload.get('survival_mode_since', '') or 'none'}")
    print(f"survival_mode_summary={payload.get('survival_mode_summary', '') or 'none'}")
    print(f"survival_mode_actions={'; '.join(payload.get('survival_mode_actions', [])) if isinstance(payload.get('survival_mode_actions', []), list) and payload.get('survival_mode_actions', []) else 'none'}")
    print(f"survival_mode_disabled_features={','.join(payload.get('survival_mode_disabled_features', [])) if isinstance(payload.get('survival_mode_disabled_features', []), list) and payload.get('survival_mode_disabled_features', []) else 'none'}")
    print(f"survival_mode_config_file={payload.get('survival_mode_config_file', '') or 'none'}")
    print(f"survival_mode_sticky={str(bool(payload.get('survival_mode_sticky', False))).lower()}")
    print(f"survival_mode_sticky_reason={payload.get('survival_mode_sticky_reason', '') or 'none'}")
    print(f"survival_mode_exit_ready={str(bool(payload.get('survival_mode_exit_ready', False))).lower()}")
    print(f"survival_mode_exit_policy={payload.get('survival_mode_exit_policy', '') or 'none'}")
    print(f"survival_mode_exit_blockers={'; '.join(payload.get('survival_mode_exit_blockers', [])) if isinstance(payload.get('survival_mode_exit_blockers', []), list) and payload.get('survival_mode_exit_blockers', []) else 'none'}")
    print(f"survival_mode_stable_ready_runs={payload.get('survival_mode_stable_ready_runs', 0)}")
    print(f"survival_mode_stable_required_runs={payload.get('survival_mode_stable_required_runs', 0)}")
    print(f"survival_mode_manual_clear_required={str(bool(payload.get('survival_mode_manual_clear_required', False))).lower()}")
    print(f"survival_mode_config_changed_away={str(bool(payload.get('survival_mode_config_changed_away', False))).lower()}")
    print(f"survival_mode_last_exit_at={payload.get('survival_mode_last_exit_at', '') or 'none'}")
    print(f"survival_mode_last_exit_reason={payload.get('survival_mode_last_exit_reason', '') or 'none'}")
    print(f"survival_mode_last_exit_kind={payload.get('survival_mode_last_exit_kind', '') or 'none'}")
    print(f"survival_mode_last_exit_summary={payload.get('survival_mode_last_exit_summary', '') or 'none'}")
    print(f"last_good_validated_at={payload.get('last_good_validated_at', '') or 'none'}")
    print(f"service_active={str(payload['service_active']).lower()}")
    print(f"service_main_pid={payload['service_main_pid']}")
    print(f"listener_pids={' '.join(payload['listener_pids']) if payload['listener_pids'] else 'none'}")
    print(f"grace_applied={str(payload['grace_applied']).lower()}")
    print(f"grace_seconds={payload['grace_seconds']}")
    print(f"service_probe_failures={payload['service_probe_failures']}")
    print(f"service_probe_summary={payload['service_probe_summary']}")
    print(f"conversation_probe_summary={payload.get('conversation_probe_summary', 'n/a')}")
    print(f"consecutive_failures={payload['consecutive_failures']}")
    print(f"guard_last_operation={payload.get('guard_last_operation', '') or 'none'}")
    print(f"guard_last_summary={payload.get('guard_last_summary', '') or 'none'}")
    print(f"maintenance_mode={str(maintenance['enabled']).lower()}")
    print(f"current_incident_id={payload['current_incident_id'] or 'none'}")
    print(f"current_incident_state={payload.get('current_incident_state') or 'none'}")
    print(f"current_incident_age_seconds={payload.get('current_incident_age_seconds', 0)}")
    print(f"last_run_duration_ms={run_state.get('last_run_duration_ms', 0)}")
    print(f"last_service_probe_result={run_state.get('last_service_probe_result', 'none')}")
    print(f"last_event_severity={last_event.get('severity', 'none')}")
    print(f"last_event_human_summary={last_event.get('human_summary', last_event.get('summary', 'none'))}")
    print(f"recent_events_count={len(recent_events) if isinstance(recent_events, list) else 0}")
    print(f"recent_window_hours={recent_stats.get('window_hours', 0) if isinstance(recent_stats, dict) else 0}")
    print(f"recent_total={recent_stats.get('total', 0) if isinstance(recent_stats, dict) else 0}")
    print(f"recent_counts=healthy:{counts.get('healthy', 0)},degraded:{counts.get('degraded', 0)},recovered:{counts.get('recovered', 0)},failed:{counts.get('failed', 0)}")
    print(f"healthy_streak_events={recent_stats.get('healthy_streak_events', 0) if isinstance(recent_stats, dict) else 0}")
    print(f"healthy_streak_start={recent_stats.get('healthy_streak_start', '') if isinstance(recent_stats, dict) else ''}")
    print(f"healthy_streak_duration_seconds={recent_stats.get('healthy_streak_duration_seconds', 0) if isinstance(recent_stats, dict) else 0}")
    print(f"longest_healthy_gap_seconds={recent_stats.get('longest_healthy_gap_seconds', 0) if isinstance(recent_stats, dict) else 0}")
    print(f"last_recovered_at={recent_stats.get('last_recovered_at', '') if isinstance(recent_stats, dict) else ''}")
    print(f"last_recovery_duration_seconds={recent_stats.get('last_recovery_duration_seconds', 0) if isinstance(recent_stats, dict) else 0}")
    if isinstance(recent_events, list):
        for idx, event in enumerate(recent_events[-3:], start=1):
            if not isinstance(event, dict):
                continue
            print(
                f"recent_event_{idx}={event.get('time', 'unknown')} | {event.get('severity', 'info')} | "
                f"{event.get('status', 'unknown')} | {event.get('human_summary', event.get('summary', ''))}"
            )
    queue_summary = payload.get('incident_queue_summary', {}) if isinstance(payload.get('incident_queue_summary', {}), dict) else {}
    print(f"queue_open_total={queue_summary.get('open_total', 0)}")
    print(f"queue_attention_total={queue_summary.get('attention_total', 0)}")
    print(f"queue_handled_total={queue_summary.get('handled_total', 0)}")
    print(f"recent_incidents_count={len(recent_incidents) if isinstance(recent_incidents, list) else 0}")
    if isinstance(recent_incidents, list):
        for idx, incident in enumerate(recent_incidents[-3:], start=1):
            if not isinstance(incident, dict):
                continue
            latest_note = incident.get('latest_note', '') or ''
            latest_note_suffix = f" | note={latest_note}" if latest_note else ""
            print(
                f"recent_incident_{idx}={incident.get('time', 'unknown')} | {incident.get('incident_id', 'none')} | "
                f"{incident.get('state', 'unknown')} | {incident.get('health_level', 'unknown')} | "
                f"owner={incident.get('owner', '') or 'none'} | ack={str(bool(incident.get('acknowledged', False))).lower()} | notes={incident.get('notes_count', 0)} | "
                f"attention={incident.get('attention_summary', 'none') or 'none'} | {incident.get('summary', '')}{latest_note_suffix}"
            )
    print(f"env_file={payload['env_file'] or 'none'}")


def print_incidents_list(payload: dict[str, object]) -> None:
    incidents = payload.get("incidents", [])
    print(f"state_filter={payload.get('state_filter', 'all')}")
    print(f"owner_filter={payload.get('owner_filter', '') or 'all'}")
    print(f"ack_filter={payload.get('ack_filter', 'all')}")
    print(f"notes_filter={payload.get('notes_filter', 'all')}")
    print(f"attention_filter={payload.get('attention_filter', 'all')}")
    print(f"incident_count={len(incidents) if isinstance(incidents, list) else 0}")
    if isinstance(incidents, list):
        for idx, incident in enumerate(incidents, start=1):
            if not isinstance(incident, dict):
                continue
            latest_note = incident.get('latest_note', '') or ''
            latest_note_suffix = f" | note={latest_note}" if latest_note else ""
            print(
                f"incident_{idx}={incident.get('incident_id', 'none')} | {incident.get('state', 'unknown')} | "
                f"{incident.get('health_level', 'unknown')} | owner={incident.get('owner', '') or 'none'} | "
                f"ack={str(bool(incident.get('acknowledged', False))).lower()} | notes={incident.get('notes_count', 0)} | "
                f"attention={incident.get('attention_summary', 'none') or 'none'} | {incident.get('summary', '')}{latest_note_suffix}"
            )


def print_incident_detail(payload: dict[str, object], *, notes_all: bool = False) -> None:
    if not payload:
        print("incident=none")
        return
    print(f"incident_id={payload.get('incident_id', 'none')}")
    print(f"state={payload.get('state', 'unknown')}")
    print(f"health_level={payload.get('health_level', 'unknown')}")
    print(f"time={payload.get('time', '') or 'none'}")
    print(f"created_at={payload.get('created_at', '') or 'none'}")
    print(f"resolved_at={payload.get('resolved_at', '') or 'none'}")
    print(f"summary={payload.get('summary', '')}")
    print(f"resolution_summary={payload.get('resolution_summary', '') or 'none'}")
    print(f"incident_dir={payload.get('incident_dir', '') or 'none'}")
    print(f"active={payload.get('active', 'unknown')}")
    print(f"main_pid={payload.get('main_pid', '0')}")
    print(f"listeners={payload.get('listeners', 'none')}")
    print(f"pre_repair_backup_result={payload.get('pre_repair_backup_result', 'not-run')}")
    print(f"rollback_occurred={str(bool(payload.get('rollback_occurred', False))).lower()}")
    print(f"rollback_summary_archive_file={payload.get('rollback_summary_archive_file', '') or 'none'}")
    print(f"owner={payload.get('owner', '') or 'none'}")
    print(f"acknowledged={str(bool(payload.get('acknowledged', False))).lower()}")
    print(f"acknowledged_by={payload.get('acknowledged_by', '') or 'none'}")
    print(f"acknowledged_at={payload.get('acknowledged_at', '') or 'none'}")
    print(f"notes_count={payload.get('notes_count', 0)}")
    print(f"events_count={payload.get('events_count', 0)}")
    print(f"latest_event_type={payload.get('latest_event_type', '') or 'none'}")
    print(f"latest_event_at={payload.get('latest_event_at', '') or 'none'}")
    print(f"attention_needed={str(bool(payload.get('attention_needed', False))).lower()}")
    print(f"attention_count={payload.get('attention_count', 0)}")
    print(f"attention_summary={payload.get('attention_summary', '') or 'none'}")
    print(f"latest_note_by={payload.get('latest_note_by', '') or 'none'}")
    print(f"latest_note_at={payload.get('latest_note_at', '') or 'none'}")
    print(f"latest_note={payload.get('latest_note', '') or 'none'}")
    notes = payload.get('notes', [])
    if isinstance(notes, list) and notes:
        visible_notes = notes if notes_all else notes[-3:]
        for idx, note in enumerate(visible_notes, start=1):
            if not isinstance(note, dict):
                continue
            print(
                f"note_{idx}={note.get('time', '') or 'none'} | {note.get('by', '') or 'none'} | {note.get('message', '') or ''}"
            )
    artifacts = payload.get('artifacts', [])
    print(f"artifacts={','.join(artifacts) if isinstance(artifacts, list) and artifacts else 'none'}")


def print_incident_queue(payload: dict[str, object]) -> None:
    print(render_incident_queue(payload))


def print_incident_timeline(payload: dict[str, object]) -> None:
    if not payload:
        print("incident=none")
        return
    print(f"incident_id={payload.get('incident_id', 'none')}")
    print(f"state={payload.get('state', 'unknown')}")
    print(f"owner={payload.get('owner', '') or 'none'}")
    print(f"acknowledged={str(bool(payload.get('acknowledged', False))).lower()}")
    print(f"notes_count={payload.get('notes_count', 0)}")
    events = payload.get('events', [])
    print(f"event_count={len(events) if isinstance(events, list) else 0}")
    if isinstance(events, list):
        for idx, event in enumerate(events, start=1):
            if not isinstance(event, dict):
                continue
            summary = event.get('summary', '') or event.get('message', '') or 'none'
            print(
                f"event_{idx}={event.get('time', '') or 'none'} | {event.get('type', '') or 'unknown'} | {event.get('by', '') or 'none'} | {summary}"
            )


def print_maintenance(payload: dict[str, object]) -> None:
    print(f"enabled={str(payload['enabled']).lower()}")
    print(f"file={payload['file']}")
    print(f"detail={payload['detail'] or 'none'}")


def print_bootstrap(outcome: BootstrapOutcome) -> None:
    print(render_bootstrap(outcome))
