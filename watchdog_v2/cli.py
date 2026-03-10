from __future__ import annotations

import argparse
import json
from pathlib import Path

from watchdog_v2.bootstrap import BootstrapOutcome, Bootstrapper
from watchdog_v2.config import Config, default_env_file
from watchdog_v2.engine import RunOutcome, WatchdogEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openclaw-watchdog-v2")
    parser.add_argument("--env", type=Path, default=default_env_file())
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once = subparsers.add_parser("run-once", help="Run one watchdog remediation pass")
    run_once.add_argument("--json", action="store_true")

    check = subparsers.add_parser("check", help="Check health without remediating")
    check.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="Show current watchdog state")
    status.add_argument("--json", action="store_true")
    status.add_argument("--summary", action="store_true", help="Print a compact one-line summary")

    report = subparsers.add_parser("report", help="Show compact watchdog report for humans or machines")
    report.add_argument("--json", action="store_true")
    report.add_argument("--message", action="store_true", help="Print message-ready multiline text")
    report.add_argument("--limit", type=int, default=5, help="How many recent incidents to include")

    metrics = subparsers.add_parser("metrics", help="Show normalized watchdog metrics for scripts or dashboards")
    metrics.add_argument("--json", action="store_true")
    metrics.add_argument("--prometheus", action="store_true", help="Print Prometheus text exposition format")

    incidents = subparsers.add_parser("incidents", help="List or inspect watchdog incident bundles")
    incidents_sub = incidents.add_subparsers(dest="incidents_command", required=True)
    incidents_list = incidents_sub.add_parser("list", help="List recent incidents")
    incidents_list.add_argument("--json", action="store_true")
    incidents_list.add_argument("--limit", type=int, default=10, help="How many incidents to show")
    incidents_list.add_argument("--state", choices=["all", "open", "resolved"], default="all")
    incidents_list.add_argument("--owner", default="", help="Filter incidents by exact owner")
    incidents_list.add_argument("--ack", choices=["all", "yes", "no"], default="all", help="Filter incidents by acknowledgement state")
    incidents_list.add_argument("--notes", choices=["all", "yes", "no"], default="all", help="Filter incidents by whether operator notes exist")
    incidents_list.add_argument("--attention", choices=["all", "yes", "no"], default="all", help="Filter incidents by whether operator attention is still needed")
    incidents_show = incidents_sub.add_parser("show", help="Show one incident in detail")
    incidents_show.add_argument("incident_id")
    incidents_show.add_argument("--json", action="store_true")
    incidents_show.add_argument("--notes-all", action="store_true", help="Print all notes in text mode instead of only recent notes")
    incidents_current = incidents_sub.add_parser("current", help="Show the current active incident if there is one")
    incidents_current.add_argument("--json", action="store_true")
    incidents_queue = incidents_sub.add_parser("queue", help="Show the open-incident operator queue")
    incidents_queue.add_argument("--json", action="store_true")
    incidents_queue.add_argument("--limit", type=int, default=10, help="How many open incidents to show")
    incidents_timeline = incidents_sub.add_parser("timeline", help="Show incident timeline events")
    incidents_timeline.add_argument("incident_id")
    incidents_timeline.add_argument("--json", action="store_true")
    incidents_timeline.add_argument("--limit", type=int, default=0, help="Only show the latest N timeline events")
    incidents_assign = incidents_sub.add_parser("assign", help="Assign an owner to an incident")
    incidents_assign.add_argument("incident_id")
    incidents_assign.add_argument("--owner", required=True)
    incidents_assign.add_argument("--json", action="store_true")
    incidents_unassign = incidents_sub.add_parser("unassign", help="Clear the owner from an incident")
    incidents_unassign.add_argument("incident_id")
    incidents_unassign.add_argument("--json", action="store_true")
    incidents_ack = incidents_sub.add_parser("ack", help="Acknowledge an incident")
    incidents_ack.add_argument("incident_id")
    incidents_ack.add_argument("--by", required=True)
    incidents_ack.add_argument("--note", default="")
    incidents_ack.add_argument("--json", action="store_true")
    incidents_unack = incidents_sub.add_parser("unack", help="Clear incident acknowledgement")
    incidents_unack.add_argument("incident_id")
    incidents_unack.add_argument("--json", action="store_true")
    incidents_note = incidents_sub.add_parser("note", help="Add an operator note to an incident")
    incidents_note.add_argument("incident_id")
    incidents_note.add_argument("--by", required=True)
    incidents_note.add_argument("--message", required=True)
    incidents_note.add_argument("--json", action="store_true")

    bootstrap = subparsers.add_parser(
        "bootstrap",
        aliases=["provision"],
        help="Provision OpenCode fallback, report Codex, and scaffold OpenClaw qqbot/feishu defaults",
    )
    bootstrap.add_argument("--json", action="store_true")
    bootstrap.add_argument(
        "--install-openclaw",
        action="store_true",
        help="Explicitly allow running OPENCLAW_INSTALL_COMMAND when OpenClaw is missing",
    )
    bootstrap.add_argument("--dry-run", action="store_true", help="Report planned changes without editing config or running installs")

    maintenance = subparsers.add_parser("maintenance", help="Manage maintenance mode")
    maintenance_sub = maintenance.add_subparsers(dest="maintenance_command", required=True)
    maintenance_on = maintenance_sub.add_parser("on", help="Enable maintenance mode")
    maintenance_on.add_argument("--reason", default="")
    maintenance_on.add_argument("--json", action="store_true")
    maintenance_off = maintenance_sub.add_parser("off", help="Disable maintenance mode")
    maintenance_off.add_argument("--json", action="store_true")
    maintenance_status = maintenance_sub.add_parser("status", help="Show maintenance status")
    maintenance_status.add_argument("--json", action="store_true")

    return parser


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _print_run_once(outcome: RunOutcome) -> None:
    print(f"state={outcome.state}")
    print(f"summary={outcome.summary}")


def _print_check(payload: dict[str, object]) -> None:
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


def _print_status_summary(payload: dict[str, object]) -> None:
    last_event = payload.get("last_event", {})
    recent_stats = payload.get("recent_event_stats", {})
    counts = recent_stats.get("counts", {}) if isinstance(recent_stats, dict) else {}
    recent_incidents = payload.get("recent_incidents", [])
    incident_tail = "none"
    if isinstance(recent_incidents, list) and recent_incidents:
        last_incident = recent_incidents[-1]
        if isinstance(last_incident, dict):
            incident_tail = str(last_incident.get("incident_id", "none"))
    survival_summary = "off"
    if bool(payload.get("survival_mode_active", False)):
        survival_summary = (
            "active"
            f"(sticky={str(bool(payload.get('survival_mode_sticky', False))).lower()},"
            f"exit_ready={str(bool(payload.get('survival_mode_exit_ready', False))).lower()},"
            f"stable={int(payload.get('survival_mode_stable_ready_runs', 0) or 0)}/{int(payload.get('survival_mode_stable_required_runs', 0) or 0)})"
        )
    elif str(payload.get("survival_mode_last_exit_kind", "") or ""):
        survival_summary = f"last-exit={payload.get('survival_mode_last_exit_kind', '') or 'unknown'}"
    print(
        " | ".join(
            [
                f"status={payload.get('last_status', 'unknown')}",
                f"conv={payload.get('conversation_status', 'down')}",
                f"health={payload.get('health_level', 'unknown')}",
                f"mode={payload.get('current_mode', 'unknown')}",
                f"recovery={payload.get('last_recovery_strategy', 'none')}",
                f"survival={survival_summary}",
                f"service={str(bool(payload.get('service_active', False))).lower()}",
                f"probe={payload.get('service_probe_summary', 'n/a')}",
                f"recent=healthy:{counts.get('healthy', 0)},degraded:{counts.get('degraded', 0)},recovered:{counts.get('recovered', 0)},failed:{counts.get('failed', 0)}",
                f"incident_tail={incident_tail}",
                f"last={last_event.get('human_summary', last_event.get('summary', 'none'))}",
            ]
        )
    )


def _print_report(payload: dict[str, object]) -> None:
    last_event = payload.get("last_event", {})
    recent_stats = payload.get("recent_event_stats", {})
    counts = recent_stats.get("counts", {}) if isinstance(recent_stats, dict) else {}
    recent_incidents = payload.get("recent_incidents", [])
    print(f"status={payload.get('status', 'unknown')}")
    print(f"conversation_status={payload.get('conversation_status', 'down')}")
    print(f"conversation_ready={str(bool(payload.get('conversation_ready', False))).lower()}")
    print(f"minimal_usable_ready={str(bool(payload.get('minimal_usable_ready', False))).lower()}")
    print(f"health_level={payload.get('health_level', 'unknown')}")
    print(f"current_mode={payload.get('current_mode', 'unknown')}")
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
    print(f"service_active={str(bool(payload.get('service_active', False))).lower()}")
    print(f"service_probe_summary={payload.get('service_probe_summary', 'n/a')}")
    print(f"conversation_probe_summary={payload.get('conversation_probe_summary', 'n/a')}")
    print(f"current_incident_id={payload.get('current_incident_id', '') or 'none'}")
    print(f"current_incident_state={payload.get('current_incident_state', '') or 'none'}")
    print(f"cooldown_remaining_seconds={payload.get('cooldown_remaining_seconds', 0)}")
    print(f"last_event_severity={last_event.get('severity', 'none')}")
    print(f"last_event_human_summary={last_event.get('human_summary', last_event.get('summary', 'none'))}")
    print(f"recent_counts=healthy:{counts.get('healthy', 0)},degraded:{counts.get('degraded', 0)},recovered:{counts.get('recovered', 0)},failed:{counts.get('failed', 0)}")
    queue_summary = payload.get('incident_queue_summary', {}) if isinstance(payload.get('incident_queue_summary', {}), dict) else {}
    print(f"queue_open_total={queue_summary.get('open_total', 0)}")
    print(f"queue_attention_total={queue_summary.get('attention_total', 0)}")
    print(f"queue_handled_total={queue_summary.get('handled_total', 0)}")
    print(f"recent_incidents_count={len(recent_incidents) if isinstance(recent_incidents, list) else 0}")
    print(f"operator_attention_needed={str(bool(payload.get('operator_attention_needed', False))).lower()}")
    print(f"operator_attention_count={payload.get('operator_attention_count', 0)}")
    attention_items = payload.get('operator_attention_items', [])
    if isinstance(attention_items, list):
        for idx, item in enumerate(attention_items, start=1):
            print(f"attention_{idx}={item}")
    if isinstance(recent_incidents, list):
        for idx, incident in enumerate(recent_incidents[-5:], start=1):
            if not isinstance(incident, dict):
                continue
            latest_note = incident.get('latest_note', '') or ''
            latest_note_suffix = f" | note={latest_note}" if latest_note else ""
            print(
                f"incident_{idx}={incident.get('time', 'unknown')} | {incident.get('incident_id', 'none')} | "
                f"{incident.get('state', 'unknown')} | {incident.get('health_level', 'unknown')} | "
                f"owner={incident.get('owner', '') or 'none'} | ack={str(bool(incident.get('acknowledged', False))).lower()} | notes={incident.get('notes_count', 0)} | "
                f"attention={incident.get('attention_summary', 'none') or 'none'} | {incident.get('summary', '')}{latest_note_suffix}"
            )


def _print_metrics(payload: dict[str, object]) -> None:
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
    print(f"cooldown_remaining_seconds={payload.get('cooldown_remaining_seconds', 0)}")
    print(f"current_incident_open={str(bool(payload.get('current_incident_open', False))).lower()}")
    print(f"current_incident_id={payload.get('current_incident_id', '') or 'none'}")
    print(f"current_incident_state={payload.get('current_incident_state', '') or 'none'}")
    print(f"current_incident_age_seconds={payload.get('current_incident_age_seconds', 0)}")
    print(f"current_incident_owner={payload.get('current_incident_owner', '') or 'none'}")
    print(f"current_incident_owner_assigned={str(bool(payload.get('current_incident_owner_assigned', False))).lower()}")
    print(f"current_incident_acknowledged={str(bool(payload.get('current_incident_acknowledged', False))).lower()}")
    print(f"current_incident_notes_count={payload.get('current_incident_notes_count', 0)}")
    print(f"current_incident_events_count={payload.get('current_incident_events_count', 0)}")
    print(f"current_incident_latest_event_type={payload.get('current_incident_latest_event_type', '') or 'none'}")
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


def _print_status(payload: dict[str, object]) -> None:
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
    print(f"cooldown_remaining_seconds={payload['cooldown_remaining_seconds']}")
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


def _print_incidents_list(payload: dict[str, object]) -> None:
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


def _print_incident_detail(payload: dict[str, object], *, notes_all: bool = False) -> None:
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
    print(f"codex_trigger_result={payload.get('codex_trigger_result', 'not-run')}")
    print(f"opencode_fallback_trigger_result={payload.get('opencode_fallback_trigger_result', 'not-run')}")
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


def _print_incident_queue(payload: dict[str, object]) -> None:
    summary = payload.get('summary', {}) if isinstance(payload.get('summary', {}), dict) else {}
    incidents = payload.get('incidents', [])
    print(f"open_total={summary.get('open_total', 0)}")
    print(f"attention_total={summary.get('attention_total', 0)}")
    print(f"handled_total={summary.get('handled_total', 0)}")
    print(f"owned_total={summary.get('owned_total', 0)}")
    print(f"acknowledged_total={summary.get('acknowledged_total', 0)}")
    print(f"with_notes_total={summary.get('with_notes_total', 0)}")
    print(f"queue_count={len(incidents) if isinstance(incidents, list) else 0}")
    if isinstance(incidents, list):
        for idx, incident in enumerate(incidents, start=1):
            if not isinstance(incident, dict):
                continue
            latest_note = incident.get('latest_note', '') or ''
            latest_note_suffix = f" | note={latest_note}" if latest_note else ""
            print(
                f"queue_{idx}={incident.get('incident_id', 'none')} | {incident.get('state', 'unknown')} | {incident.get('health_level', 'unknown')} | "
                f"owner={incident.get('owner', '') or 'none'} | ack={str(bool(incident.get('acknowledged', False))).lower()} | notes={incident.get('notes_count', 0)} | "
                f"attention={incident.get('attention_summary', 'none') or 'none'} | {incident.get('summary', '')}{latest_note_suffix}"
            )


def _print_incident_timeline(payload: dict[str, object]) -> None:
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


def _print_maintenance(payload: dict[str, object]) -> None:
    print(f"enabled={str(payload['enabled']).lower()}")
    print(f"file={payload['file']}")
    print(f"detail={payload['detail'] or 'none'}")


def _print_bootstrap(outcome: BootstrapOutcome) -> None:
    payload = outcome.payload
    opencode = payload.get("opencode", {})
    opencode_config = opencode.get("config", {})
    codex = payload.get("codex", {})
    openclaw = payload.get("openclaw", {})
    qq_plugin = payload.get("qq_plugin", {})
    config = payload.get("config", {})
    feishu_runtime = payload.get("feishu_runtime", {})
    placeholders = config.get("placeholders_remaining") or []
    files_changed = payload.get("files_changed") or []
    flow = payload.get("flow") or []
    print(f"state={outcome.state}")
    print(f"summary={outcome.summary}")
    print(f"opencode_installed={str(bool(opencode.get('installed'))).lower()}")
    print(f"opencode_install_planned={str(bool(opencode.get('would_install'))).lower()}")
    print(f"opencode_config_path={opencode_config.get('path', 'none')}")
    print(f"opencode_model={opencode_config.get('configured_model') or opencode.get('desired_model') or 'none'}")
    print(f"opencode_config_changed={str(bool(opencode_config.get('changed'))).lower()}")
    print(f"opencode_backup_path={opencode_config.get('backup_path') or 'none'}")
    print(f"opencode_watchdog_bin_ready={str(bool(opencode.get('watchdog_bin_available'))).lower()}")
    print(f"codex_available={str(bool(codex.get('available'))).lower()}")
    print(f"codex_binary={codex.get('detected_binary') or 'none'}")
    print(f"openclaw_installed={str(bool(openclaw.get('installed'))).lower()}")
    print(f"confirmation_required={str(bool(openclaw.get('confirmation_required'))).lower()}")
    print(f"qq_plugin_installed={str(bool(qq_plugin.get('installed'))).lower()}")
    print(f"config_path={config.get('path', 'none')}")
    print(f"config_changed={str(bool(config.get('changed'))).lower()}")
    print(f"backup_path={config.get('backup_path') or 'none'}")
    print(f"feishu_markers_found={str(bool(feishu_runtime.get('found'))).lower()}")
    print(f"placeholders_remaining={','.join(placeholders) if placeholders else 'none'}")
    print(f"files_changed={','.join(files_changed) if files_changed else 'none'}")
    print(f"bootstrap_flow={' -> '.join(flow) if flow else 'none'}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env_file = args.env if args.env and args.env.exists() else args.env
    config = Config.load(env_file)

    if args.command == "bootstrap":
        outcome = Bootstrapper(
            config,
            allow_install=args.install_openclaw,
            dry_run=args.dry_run,
        ).run()
        if args.json:
            _print_json(outcome.payload)
        else:
            _print_bootstrap(outcome)
        return outcome.exit_code

    with WatchdogEngine(config) as engine:
        if args.command == "run-once":
            if not engine.acquire_lock():
                payload = {"state": "locked", "summary": f"lock busy: {config.watchdog_lock_file}"}
                if args.json:
                    _print_json(payload)
                else:
                    print(f"state={payload['state']}")
                    print(f"summary={payload['summary']}")
                return 0
            outcome = engine.run_once()
            if args.json:
                _print_json({"state": outcome.state, "summary": outcome.summary, "exit_code": outcome.exit_code})
            else:
                _print_run_once(outcome)
            return outcome.exit_code

        if args.command == "check":
            payload = engine.live_probe(include_doctor=True)
            if args.json:
                _print_json(payload)
            else:
                _print_check(payload)
            return 0 if payload["healthy"] else 1

        if args.command == "status":
            payload = engine.status_payload()
            if args.json:
                _print_json(payload)
            elif getattr(args, "summary", False):
                _print_status_summary(payload)
            else:
                _print_status(payload)
            return 0

        if args.command == "report":
            payload = engine.report_payload(incident_limit=max(1, getattr(args, 'limit', 5)))
            if args.json:
                _print_json(payload)
            elif getattr(args, "message", False):
                print(payload.get("message_text", ""))
            else:
                _print_report(payload)
            return 0

        if args.command == "metrics":
            payload = engine.metrics_payload()
            if getattr(args, "json", False):
                _print_json(payload)
            elif getattr(args, "prometheus", False):
                print(engine.prometheus_metrics_text(payload), end="")
            else:
                _print_metrics(payload)
            return 0

        if args.command == "incidents":
            if args.incidents_command == "list":
                ack_arg = getattr(args, "ack", "all")
                acknowledged = None if ack_arg == "all" else ack_arg == "yes"
                notes_arg = getattr(args, "notes", "all")
                has_notes = None if notes_arg == "all" else notes_arg == "yes"
                payload = {
                    "state_filter": getattr(args, "state", "all"),
                    "owner_filter": getattr(args, "owner", ""),
                    "ack_filter": ack_arg,
                    "notes_filter": notes_arg,
                    "attention_filter": getattr(args, "attention", "all"),
                    "incidents": engine.list_incident_snapshots(
                        limit=max(1, getattr(args, "limit", 10)),
                        state=getattr(args, "state", "all"),
                        owner=getattr(args, "owner", ""),
                        acknowledged=acknowledged,
                        has_notes=has_notes,
                        attention_needed=None if getattr(args, "attention", "all") == "all" else getattr(args, "attention", "all") == "yes",
                    ),
                }
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incidents_list(payload)
                return 0
            if args.incidents_command == "show":
                payload = engine.incident_detail_payload(args.incident_id)
                if not payload:
                    if getattr(args, "json", False):
                        _print_json({"error": "incident-not-found", "incident_id": args.incident_id})
                    else:
                        print(f"incident_not_found={args.incident_id}")
                    return 1
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incident_detail(payload, notes_all=getattr(args, "notes_all", False))
                return 0
            if args.incidents_command == "queue":
                payload = engine.incident_queue_payload(limit=max(1, getattr(args, "limit", 10)))
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incident_queue(payload)
                return 0
            if args.incidents_command == "timeline":
                limit = getattr(args, "limit", 0)
                payload = engine.incident_timeline_payload(args.incident_id, limit=limit if limit > 0 else None)
                if not payload:
                    if getattr(args, "json", False):
                        _print_json({"error": "incident-not-found", "incident_id": args.incident_id})
                    else:
                        print(f"incident_not_found={args.incident_id}")
                    return 1
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incident_timeline(payload)
                return 0
            if args.incidents_command == "assign":
                payload = engine.set_incident_owner(args.incident_id, args.owner)
                if not payload:
                    if getattr(args, "json", False):
                        _print_json({"error": "incident-not-found", "incident_id": args.incident_id})
                    else:
                        print(f"incident_not_found={args.incident_id}")
                    return 1
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incident_detail(payload)
                return 0
            if args.incidents_command == "unassign":
                payload = engine.clear_incident_owner(args.incident_id)
                if not payload:
                    if getattr(args, "json", False):
                        _print_json({"error": "incident-not-found", "incident_id": args.incident_id})
                    else:
                        print(f"incident_not_found={args.incident_id}")
                    return 1
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incident_detail(payload)
                return 0
            if args.incidents_command == "ack":
                payload = engine.acknowledge_incident(args.incident_id, acknowledged_by=args.by, note=args.note)
                if not payload:
                    if getattr(args, "json", False):
                        _print_json({"error": "incident-not-found", "incident_id": args.incident_id})
                    else:
                        print(f"incident_not_found={args.incident_id}")
                    return 1
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incident_detail(payload)
                return 0
            if args.incidents_command == "unack":
                payload = engine.clear_incident_acknowledgement(args.incident_id)
                if not payload:
                    if getattr(args, "json", False):
                        _print_json({"error": "incident-not-found", "incident_id": args.incident_id})
                    else:
                        print(f"incident_not_found={args.incident_id}")
                    return 1
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incident_detail(payload)
                return 0
            if args.incidents_command == "note":
                payload = engine.add_incident_note(args.incident_id, note_by=args.by, message=args.message)
                if not payload:
                    if getattr(args, "json", False):
                        _print_json({"error": "incident-not-found", "incident_id": args.incident_id})
                    else:
                        print(f"incident_not_found={args.incident_id}")
                    return 1
                if getattr(args, "json", False):
                    _print_json(payload)
                else:
                    _print_incident_detail(payload)
                return 0
            payload = engine.current_incident_payload()
            if not payload:
                if getattr(args, "json", False):
                    _print_json({})
                else:
                    print("incident=none")
                return 0
            if getattr(args, "json", False):
                _print_json(payload)
            else:
                _print_incident_detail(payload)
            return 0

        if args.command == "maintenance":
            if args.maintenance_command == "on":
                payload = engine.maintenance_on(reason=args.reason)
            elif args.maintenance_command == "off":
                payload = engine.maintenance_off()
            else:
                payload = engine.maintenance_status_payload()
            if getattr(args, "json", False):
                _print_json(payload)
            else:
                _print_maintenance(payload)
            return 0

    return 2
