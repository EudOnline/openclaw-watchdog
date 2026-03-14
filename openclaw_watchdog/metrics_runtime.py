from __future__ import annotations

import json
from datetime import datetime

from openclaw_watchdog import health as health_ops
from openclaw_watchdog import incidents as incident_ops
from openclaw_watchdog import operator_snapshot
from openclaw_watchdog.models import IncidentSummary, ProbeSnapshot, RunStateSnapshot


def _incident_summary(value: object) -> IncidentSummary:
    if isinstance(value, IncidentSummary):
        return value
    if isinstance(value, dict):
        return IncidentSummary.from_dict(value)
    return IncidentSummary()


def _run_state_snapshot(payload: dict[str, object]) -> RunStateSnapshot:
    raw_run_state = payload.get("run_state")
    if isinstance(raw_run_state, RunStateSnapshot):
        return raw_run_state
    if isinstance(raw_run_state, dict):
        return RunStateSnapshot.from_dict(raw_run_state)
    return RunStateSnapshot.from_dict(payload)


def _rescue_fields(run_state: RunStateSnapshot) -> dict[str, object]:
    return {
        'rescue_attempt_count': run_state.rescue_attempt_count,
        'rescue_executor_selected': run_state.rescue_executor_selected,
        'rescue_plan_generated': run_state.rescue_plan_generated,
        'rescue_plan_source': run_state.rescue_plan_source,
        'rescue_plan_id': run_state.rescue_plan_id,
        'rescue_plan_status': run_state.rescue_plan_status,
        'rescue_tier': run_state.rescue_tier,
        'case_ingest_result': run_state.case_ingest_result,
        'candidate_rule_status': run_state.candidate_rule_status,
        'rescue_attempt_order': list(run_state.rescue_attempt_order),
        'rescue_rejected_executors': list(run_state.rescue_rejected_executors),
        'rescue_learning_summary': run_state.rescue_learning_summary,
        'rescue_mutation_scope': list(run_state.rescue_mutation_scope),
    }


def unix_timestamp(value: object) -> int:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        return max(0, int(datetime.fromisoformat(text).timestamp()))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S"):
        try:
            return max(0, int(datetime.strptime(text, fmt).timestamp()))
        except ValueError:
            continue
    parts = text.split()
    if len(parts) == 3:
        try:
            return max(0, int(datetime.strptime(" ".join(parts[:2]), "%Y-%m-%d %H:%M:%S").timestamp()))
        except ValueError:
            return 0
    return 0


def prometheus_metrics_text(metrics: dict[str, object]) -> str:
    status = str(metrics.get("status", "unknown") or "unknown")
    health_level = str(metrics.get("health_level", "unknown") or "unknown")
    current_mode = str(metrics.get("current_mode", "unknown") or "unknown")
    conversation_status = str(metrics.get("conversation_status", "down") or "down")
    last_recovery_strategy = str(metrics.get("last_recovery_strategy", "none") or "none")
    lines = [
        "# HELP openclaw_watchdog_info Static current state labels for the watchdog.",
        "# TYPE openclaw_watchdog_info gauge",
        ('openclaw_watchdog_info{' f'status="{status}",health_level="{health_level}",current_mode="{current_mode}",conversation_status="{conversation_status}",last_recovery_strategy="{last_recovery_strategy}"' "} 1"),
        "# HELP openclaw_watchdog_service_active Whether the gateway service is active.",
        "# TYPE openclaw_watchdog_service_active gauge",
        f"openclaw_watchdog_service_active {1 if metrics.get('service_active', False) else 0}",
        "# HELP openclaw_watchdog_process_layer_healthy Whether the process layer is healthy.",
        "# TYPE openclaw_watchdog_process_layer_healthy gauge",
        f"openclaw_watchdog_process_layer_healthy {1 if metrics.get('process_layer_healthy', False) else 0}",
        "# HELP openclaw_watchdog_service_layer_healthy Whether the service layer probe is healthy.",
        "# TYPE openclaw_watchdog_service_layer_healthy gauge",
        f"openclaw_watchdog_service_layer_healthy {1 if metrics.get('service_layer_healthy', False) else 0}",
        "# HELP openclaw_watchdog_conversation_ready Whether the full conversation path is ready.",
        "# TYPE openclaw_watchdog_conversation_ready gauge",
        f"openclaw_watchdog_conversation_ready {1 if metrics.get('conversation_ready', False) else 0}",
        "# HELP openclaw_watchdog_minimal_usable_ready Whether the minimal usable conversation path is ready.",
        "# TYPE openclaw_watchdog_minimal_usable_ready gauge",
        f"openclaw_watchdog_minimal_usable_ready {1 if metrics.get('minimal_usable_ready', False) else 0}",
        "# HELP openclaw_watchdog_survival_mode_active Whether survival mode is currently active.",
        "# TYPE openclaw_watchdog_survival_mode_active gauge",
        f"openclaw_watchdog_survival_mode_active {1 if metrics.get('survival_mode_active', False) else 0}",
        "# HELP openclaw_watchdog_survival_mode_sticky Whether survival mode is intentionally held sticky until exit is safe.",
        "# TYPE openclaw_watchdog_survival_mode_sticky gauge",
        f"openclaw_watchdog_survival_mode_sticky {1 if metrics.get('survival_mode_sticky', False) else 0}",
        "# HELP openclaw_watchdog_survival_mode_exit_ready Whether survival mode has satisfied its exit-readiness conditions.",
        "# TYPE openclaw_watchdog_survival_mode_exit_ready gauge",
        f"openclaw_watchdog_survival_mode_exit_ready {1 if metrics.get('survival_mode_exit_ready', False) else 0}",
        "# HELP openclaw_watchdog_survival_mode_manual_clear_required Whether survival mode is waiting for operator clear or reconfiguration.",
        "# TYPE openclaw_watchdog_survival_mode_manual_clear_required gauge",
        f"openclaw_watchdog_survival_mode_manual_clear_required {1 if metrics.get('survival_mode_manual_clear_required', False) else 0}",
        "# HELP openclaw_watchdog_survival_mode_config_changed_away Whether the live config has moved away from the applied survival config.",
        "# TYPE openclaw_watchdog_survival_mode_config_changed_away gauge",
        f"openclaw_watchdog_survival_mode_config_changed_away {1 if metrics.get('survival_mode_config_changed_away', False) else 0}",
        "# HELP openclaw_watchdog_survival_mode_stable_ready_runs Current count of consecutive stable full-ready windows while in survival mode.",
        "# TYPE openclaw_watchdog_survival_mode_stable_ready_runs gauge",
        f"openclaw_watchdog_survival_mode_stable_ready_runs {int(metrics.get('survival_mode_stable_ready_runs', 0) or 0)}",
        "# HELP openclaw_watchdog_survival_mode_stable_required_runs Required stable full-ready windows before survival mode may exit.",
        "# TYPE openclaw_watchdog_survival_mode_stable_required_runs gauge",
        f"openclaw_watchdog_survival_mode_stable_required_runs {int(metrics.get('survival_mode_stable_required_runs', 0) or 0)}",
        "# HELP openclaw_watchdog_survival_mode_actions_count Number of configured survival-mode downgrade actions.",
        "# TYPE openclaw_watchdog_survival_mode_actions_count gauge",
        f"openclaw_watchdog_survival_mode_actions_count {len(metrics.get('survival_mode_actions', [])) if isinstance(metrics.get('survival_mode_actions', []), list) else 0}",
        "# HELP openclaw_watchdog_last_recovery_action_count Number of actions attempted in the last recovery path.",
        "# TYPE openclaw_watchdog_last_recovery_action_count gauge",
        f"openclaw_watchdog_last_recovery_action_count {int(metrics.get('last_recovery_action_count', 0) or 0)}",
        "# HELP openclaw_watchdog_last_recovery_restored_conversation Whether the last recovery restored a usable conversation path.",
        "# TYPE openclaw_watchdog_last_recovery_restored_conversation gauge",
        f"openclaw_watchdog_last_recovery_restored_conversation {1 if metrics.get('last_recovery_restored_conversation', False) else 0}",
        "# HELP openclaw_watchdog_config_drift_detected Whether config drift was detected in the last remediation pass.",
        "# TYPE openclaw_watchdog_config_drift_detected gauge",
        f"openclaw_watchdog_config_drift_detected {1 if metrics.get('config_drift_detected', False) else 0}",
        "# HELP openclaw_watchdog_consecutive_failures Current consecutive failure counter.",
        "# TYPE openclaw_watchdog_consecutive_failures gauge",
        f"openclaw_watchdog_consecutive_failures {int(metrics.get('consecutive_failures', 0) or 0)}",
        "# HELP openclaw_watchdog_service_probe_failures Current service probe failure counter.",
        "# TYPE openclaw_watchdog_service_probe_failures gauge",
        f"openclaw_watchdog_service_probe_failures {int(metrics.get('service_probe_failures', 0) or 0)}",
        "# HELP openclaw_watchdog_current_incident_open Whether there is an open current incident.",
        "# TYPE openclaw_watchdog_current_incident_open gauge",
        f"openclaw_watchdog_current_incident_open {1 if metrics.get('current_incident_open', False) else 0}",
        "# HELP openclaw_watchdog_current_incident_age_seconds Age of the current incident in seconds.",
        "# TYPE openclaw_watchdog_current_incident_age_seconds gauge",
        f"openclaw_watchdog_current_incident_age_seconds {int(metrics.get('current_incident_age_seconds', 0) or 0)}",
        "# HELP openclaw_watchdog_current_incident_owner_assigned Whether the current incident has an owner assigned.",
        "# TYPE openclaw_watchdog_current_incident_owner_assigned gauge",
        f"openclaw_watchdog_current_incident_owner_assigned {1 if metrics.get('current_incident_owner_assigned', False) else 0}",
        "# HELP openclaw_watchdog_current_incident_acknowledged Whether the current incident has been acknowledged.",
        "# TYPE openclaw_watchdog_current_incident_acknowledged gauge",
        f"openclaw_watchdog_current_incident_acknowledged {1 if metrics.get('current_incident_acknowledged', False) else 0}",
        "# HELP openclaw_watchdog_current_incident_notes_count Number of operator notes attached to the current incident.",
        "# TYPE openclaw_watchdog_current_incident_notes_count gauge",
        f"openclaw_watchdog_current_incident_notes_count {int(metrics.get('current_incident_notes_count', 0) or 0)}",
        "# HELP openclaw_watchdog_recent_incidents_total Number of indexed recent incidents included in metrics.",
        "# TYPE openclaw_watchdog_recent_incidents_total gauge",
        f"openclaw_watchdog_recent_incidents_total {int(metrics.get('recent_incidents_count', 0) or 0)}",
        "# HELP openclaw_watchdog_recent_healthy_total Number of healthy events in the recent stats window.",
        "# TYPE openclaw_watchdog_recent_healthy_total gauge",
        f"openclaw_watchdog_recent_healthy_total {int(metrics.get('recent_healthy_total', 0) or 0)}",
        "# HELP openclaw_watchdog_recent_degraded_total Number of degraded events in the recent stats window.",
        "# TYPE openclaw_watchdog_recent_degraded_total gauge",
        f"openclaw_watchdog_recent_degraded_total {int(metrics.get('recent_degraded_total', 0) or 0)}",
        "# HELP openclaw_watchdog_recent_recovered_total Number of recovered events in the recent stats window.",
        "# TYPE openclaw_watchdog_recent_recovered_total gauge",
        f"openclaw_watchdog_recent_recovered_total {int(metrics.get('recent_recovered_total', 0) or 0)}",
        "# HELP openclaw_watchdog_recent_failed_total Number of failed events in the recent stats window.",
        "# TYPE openclaw_watchdog_recent_failed_total gauge",
        f"openclaw_watchdog_recent_failed_total {int(metrics.get('recent_failed_total', 0) or 0)}",
        "# HELP openclaw_watchdog_last_run_duration_ms Duration of the last run in milliseconds.",
        "# TYPE openclaw_watchdog_last_run_duration_ms gauge",
        f"openclaw_watchdog_last_run_duration_ms {int(metrics.get('last_run_duration_ms', 0) or 0)}",
        "# HELP openclaw_watchdog_last_success_timestamp Unix timestamp of last success.",
        "# TYPE openclaw_watchdog_last_success_timestamp gauge",
        f"openclaw_watchdog_last_success_timestamp {int(metrics.get('last_success_timestamp', 0) or 0)}",
        "# HELP openclaw_watchdog_last_failed_timestamp Unix timestamp of last failed state.",
        "# TYPE openclaw_watchdog_last_failed_timestamp gauge",
        f"openclaw_watchdog_last_failed_timestamp {int(metrics.get('last_failed_timestamp', 0) or 0)}",
        "# HELP openclaw_watchdog_last_recovered_timestamp Unix timestamp of last recovered state.",
        "# TYPE openclaw_watchdog_last_recovered_timestamp gauge",
        f"openclaw_watchdog_last_recovered_timestamp {int(metrics.get('last_recovered_timestamp', 0) or 0)}",
    ]
    return "\n".join(lines) + "\n"


def write_metrics_snapshot(engine, metrics: dict[str, object]) -> None:
    engine.config.watchdog_last_metrics_file.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    engine.config.watchdog_last_metrics_file.with_suffix(".prom").write_text(
        prometheus_metrics_text(metrics),
        encoding="utf-8",
    )


def metrics_payload(engine) -> dict[str, object]:
    payload = health_ops.status_payload(engine)
    probe = ProbeSnapshot.from_dict(payload)
    run_state = _run_state_snapshot(payload)
    recent_stats = payload.get("recent_event_stats", {}) if isinstance(payload.get("recent_event_stats"), dict) else {}
    counts = recent_stats.get("counts", {}) if isinstance(recent_stats.get("counts"), dict) else {}
    current_incident_state = str(payload.get("current_incident_state", "") or "")
    current_incident = _incident_summary(
        incident_ops.current_incident_payload(engine) if str(payload.get("current_incident_id", "") or "") else {}
    )
    snapshot_source = dict(payload)
    if isinstance(payload.get('run_state'), dict):
        snapshot_source.update(payload.get('run_state', {}))
    snapshot = operator_snapshot.build_operator_snapshot(
        snapshot_source,
        stable_required_runs=int(payload.get('survival_mode_stable_required_runs', 0) or 0) or 1,
        guard_manifest_file=str(payload.get('guard_manifest_file', '') or ''),
    )
    metrics = {
        "generated_at": engine.now_iso(),
        "env_file": payload.get("env_file", ""),
        "status": payload.get("last_status", "unknown"),
        "health_level": payload.get("health_level", "unknown"),
        "current_mode": payload.get("current_mode", "unknown"),
        "service_active": probe.service_active,
        "process_layer_healthy": probe.process_layer_healthy,
        "service_layer_healthy": probe.service_layer_healthy,
        "conversation_ready": probe.conversation_ready,
        "minimal_usable_ready": probe.minimal_usable_ready,
        "conversation_status": probe.conversation_status,
        "service_probe_summary": probe.service_probe_summary,
        "conversation_probe_summary": probe.conversation_probe_summary,
        "maintenance_enabled": bool((payload.get("maintenance") or {}).get("enabled", False)),
        "survival_mode_active": bool(payload.get("survival_mode_active", False)),
        "survival_mode_reason": str(payload.get("survival_mode_reason", "") or ""),
        "survival_mode_since": str(payload.get("survival_mode_since", "") or ""),
        "survival_mode_summary": str(payload.get("survival_mode_summary", "") or ""),
        "survival_mode_actions": list(payload.get("survival_mode_actions", [])) if isinstance(payload.get("survival_mode_actions", []), list) else [],
        "survival_mode_disabled_features": list(payload.get("survival_mode_disabled_features", [])) if isinstance(payload.get("survival_mode_disabled_features", []), list) else [],
        "survival_mode_config_file": str(payload.get("survival_mode_config_file", "") or ""),
        "survival_mode_sticky": bool(payload.get("survival_mode_sticky", False)),
        "survival_mode_sticky_reason": str(payload.get("survival_mode_sticky_reason", "") or ""),
        "survival_mode_exit_ready": bool(payload.get("survival_mode_exit_ready", False)),
        "survival_mode_exit_policy": str(payload.get("survival_mode_exit_policy", "") or "none"),
        "survival_mode_exit_blockers": list(payload.get("survival_mode_exit_blockers", [])) if isinstance(payload.get("survival_mode_exit_blockers", []), list) else [],
        "survival_mode_stable_ready_runs": int(payload.get("survival_mode_stable_ready_runs", 0) or 0),
        "survival_mode_stable_required_runs": int(payload.get("survival_mode_stable_required_runs", 0) or 0),
        "survival_mode_manual_clear_required": bool(payload.get("survival_mode_manual_clear_required", False)),
        "survival_mode_config_changed_away": bool(payload.get("survival_mode_config_changed_away", False)),
        "survival_mode_last_exit_at": str(payload.get("survival_mode_last_exit_at", "") or ""),
        "survival_mode_last_exit_reason": str(payload.get("survival_mode_last_exit_reason", "") or ""),
        "survival_mode_last_exit_kind": str(payload.get("survival_mode_last_exit_kind", "") or ""),
        "survival_mode_last_exit_summary": str(payload.get("survival_mode_last_exit_summary", "") or ""),
        "consecutive_failures": int(payload.get("consecutive_failures", 0) or 0),
        "service_probe_failures": int(payload.get("service_probe_failures", 0) or 0),
        "last_recovery_strategy": run_state.last_recovery_strategy,
        "last_recovery_path": run_state.last_recovery_path,
        "last_recovery_action_count": run_state.last_recovery_action_count,
        "last_recovery_restored_conversation": run_state.last_recovery_restored_conversation,
        **_rescue_fields(run_state),
        "last_good_validated_at": run_state.last_good_validated_at,
        "last_good_generation_id": run_state.last_good_generation_id,
        "last_good_generation_count": run_state.last_good_generation_count,
        "rollback_candidate_used": run_state.rollback_candidate_used,
        "rollback_reason": run_state.rollback_reason,
        "config_drift_detected": run_state.config_drift_detected,
        "drift_scope": list(run_state.drift_scope),
        "drift_since_last_good": run_state.drift_since_last_good,
        "drift_summary": run_state.drift_summary,
        "guard_manifest_file": run_state.guard_manifest_file or str(payload.get("guard_manifest_file", "") or ""),
        "guard_last_operation": run_state.guard_last_operation or str(payload.get("guard_last_operation", "") or ""),
        "guard_last_phase": run_state.guard_last_phase or str(payload.get("guard_last_phase", "") or ""),
        "guard_last_time": run_state.guard_last_time or str(payload.get("guard_last_time", "") or ""),
        "guard_last_summary": run_state.guard_last_summary or str(payload.get("guard_last_summary", "") or ""),
        "current_incident_open": bool(payload.get("current_incident_id")) and current_incident_state == "open",
        "current_incident_id": payload.get("current_incident_id", ""),
        "current_incident_state": current_incident_state,
        "current_incident_age_seconds": int(payload.get("current_incident_age_seconds", 0) or 0),
        "current_incident_owner": current_incident.owner,
        "current_incident_owner_assigned": bool(current_incident.owner.strip()),
        "current_incident_acknowledged": current_incident.acknowledged,
        "current_incident_notes_count": current_incident.notes_count,
        "recent_event_stats": recent_stats,
        "recent_healthy_total": int(counts.get("healthy", 0) or 0),
        "recent_degraded_total": int(counts.get("degraded", 0) or 0),
        "recent_recovered_total": int(counts.get("recovered", 0) or 0),
        "recent_failed_total": int(counts.get("failed", 0) or 0),
        "recent_incidents_count": len(payload.get("recent_incidents", [])) if isinstance(payload.get("recent_incidents"), list) else 0,
        "last_run_duration_ms": int(payload.get("last_run_duration_ms", 0) or 0),
        "last_success_at": str(payload.get("last_success_at", "") or ""),
        "last_failed_at": str(payload.get("last_failed_at", "") or ""),
        "last_recovered_at": str(payload.get("last_recovered_at", "") or ""),
    }
    metrics.update(operator_snapshot.to_payload(snapshot))
    metrics["last_success_timestamp"] = unix_timestamp(metrics.get("last_success_at"))
    metrics["last_failed_timestamp"] = unix_timestamp(metrics.get("last_failed_at"))
    metrics["last_recovered_timestamp"] = unix_timestamp(metrics.get("last_recovered_at"))
    metrics["last_good_validated_timestamp"] = unix_timestamp(metrics.get("last_good_validated_at"))
    write_metrics_snapshot(engine, metrics)
    return metrics
