from __future__ import annotations

import json
from datetime import datetime

from openclaw_watchdog import event_history
from openclaw_watchdog import health_probe_runtime
from openclaw_watchdog import incidents as incident_ops
from openclaw_watchdog import last_good_runtime
from openclaw_watchdog import operator_snapshot
from openclaw_watchdog.config import parse_env_file


def read_last_event(engine) -> dict[str, object]:
    event_json_file = engine.sibling_json_path(engine.config.watchdog_event_file)
    if event_json_file.exists():
        try:
            data = json.loads(event_json_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return parse_env_file(engine.config.watchdog_event_file)


def maintenance_status_payload(engine) -> dict[str, object]:
    enabled = engine.config.watchdog_maintenance_file.exists()
    content = engine.config.watchdog_maintenance_file.read_text(encoding="utf-8").strip() if enabled else ""
    return {
        "enabled": enabled,
        "file": str(engine.config.watchdog_maintenance_file),
        "detail": content,
    }


def status_payload(engine) -> dict[str, object]:
    last_status = engine.last_status_file.read_text(encoding="utf-8").strip() if engine.last_status_file.exists() else "unknown"
    maintenance_info = maintenance_status_payload(engine)
    run_state = engine.read_run_state()
    current_incident_id = engine.current_incident_marker.read_text(encoding="utf-8").strip() if engine.current_incident_marker.exists() else ""
    current_incident_state = run_state.get("current_incident_state", "")
    current_incident_age_seconds = 0
    if current_incident_id:
        incident_state_file = engine.config.watchdog_incidents_dir / current_incident_id / "incident-state.json"
        if incident_state_file.exists():
            try:
                incident_state = json.loads(incident_state_file.read_text(encoding="utf-8"))
                if isinstance(incident_state, dict):
                    current_incident_state = str(incident_state.get("state", current_incident_state))
                    created_at = incident_state.get("created_at")
                    if isinstance(created_at, str) and created_at:
                        try:
                            current_incident_age_seconds = max(0, int((datetime.now().astimezone() - datetime.fromisoformat(created_at)).total_seconds()))
                        except ValueError:
                            current_incident_age_seconds = int(run_state.get("current_incident_age_seconds", 0) or 0)
            except json.JSONDecodeError:
                current_incident_age_seconds = int(run_state.get("current_incident_age_seconds", 0) or 0)
    queue_payload = incident_ops.incident_queue_payload(engine, limit=5)
    payload: dict[str, object] = {
        "env_file": str(engine.config.env_file) if engine.config.env_file else "",
        "state_dir": str(engine.config.watchdog_state_dir),
        "last_status": last_status,
        "consecutive_failures": engine.read_failure_count(),
        "maintenance": maintenance_info,
        "last_event": read_last_event(engine),
        "recent_events": event_history.read_event_history(engine, limit=5),
        "recent_event_stats": event_history.recent_event_stats(engine, hours=24),
        "recent_incidents": incident_ops.list_incident_snapshots(engine, limit=5),
        "incident_queue": queue_payload,
        "incident_queue_summary": queue_payload.get("summary", {}),
        "last_good_config_exists": engine.config.watchdog_last_good_config.exists(),
        "current_incident_id": current_incident_id,
        "current_incident_state": current_incident_state,
        "current_incident_age_seconds": current_incident_age_seconds,
        "run_state": run_state,
    }
    payload.update(health_probe_runtime.live_probe(engine, include_doctor=False))
    payload.update(last_good_runtime.last_good_status(engine))
    payload.update(last_good_runtime.guard_status(engine.config))
    payload["health_level"] = payload.get("health_level") or run_state.get("health_level", "unknown")
    for key, default in (
        ("conversation_ready", False),
        ("minimal_usable_ready", False),
        ("conversation_status", "down"),
        ("conversation_probe_summary", ""),
        ("model_http_error_count", 0),
        ("model_http_error_latest_at", ""),
        ("model_http_error_latest_status", 0),
        ("model_failover_last_applied_at", ""),
        ("model_failover_last_from_model", ""),
        ("model_failover_last_to_model", ""),
        ("model_failover_last_status", "not-run"),
        ("model_failover_last_summary", ""),
        ("last_recovery_strategy", "none"),
        ("last_recovery_path", "none"),
        ("last_recovery_action_count", 0),
        ("last_recovery_restored_conversation", False),
        ("rescue_attempt_count", 0),
        ("rescue_executor_selected", ""),
        ("rescue_plan_generated", False),
        ("rescue_plan_source", ""),
        ("rescue_plan_id", ""),
        ("rescue_plan_status", "not-run"),
        ("rescue_tier", "none"),
        ("case_ingest_result", "not-run"),
        ("candidate_rule_status", "none"),
        ("rescue_attempt_order", []),
        ("rescue_rejected_executors", []),
        ("rescue_learning_summary", "not-run / none"),
        ("rescue_mutation_scope", []),
        ("rollback_candidate_used", ""),
        ("rollback_reason", ""),
        ("config_drift_detected", False),
        ("drift_scope", []),
        ("drift_since_last_good", ""),
        ("drift_summary", ""),
        ("survival_mode_active", False),
        ("survival_mode_reason", ""),
        ("survival_mode_since", ""),
        ("survival_mode_summary", ""),
        ("survival_mode_actions", []),
        ("survival_mode_disabled_features", []),
        ("survival_mode_config_file", ""),
        ("survival_mode_sticky", False),
        ("survival_mode_sticky_reason", ""),
        ("survival_mode_exit_ready", False),
        ("survival_mode_exit_policy", "none"),
        ("survival_mode_exit_blockers", []),
        ("survival_mode_stable_ready_runs", 0),
        ("survival_mode_stable_required_runs", engine.config.watchdog_survival_stable_ready_runs),
        ("survival_mode_manual_clear_required", False),
        ("survival_mode_config_changed_away", False),
        ("survival_mode_last_exit_at", ""),
        ("survival_mode_last_exit_reason", ""),
        ("survival_mode_last_exit_kind", ""),
        ("survival_mode_last_exit_summary", ""),
        ("guard_manifest_file", str(engine.config.watchdog_guard_manifest_file)),
        ("guard_last_operation", ""),
        ("guard_last_phase", ""),
        ("guard_last_time", ""),
        ("guard_last_summary", ""),
    ):
        payload[key] = run_state.get(key, payload.get(key, default))
    payload.update(
        operator_snapshot.to_payload(
            operator_snapshot.build_operator_snapshot(
                payload,
                stable_required_runs=engine.config.watchdog_survival_stable_ready_runs,
                guard_manifest_file=str(engine.config.watchdog_guard_manifest_file),
            )
        )
    )
    payload["current_mode"] = engine.current_mode(
        maintenance=maintenance_info["enabled"],
        degraded=payload.get("health_level") == "degraded",
        survival=bool(payload.get("survival_mode_active", False)),
    )
    payload["run_state"]["current_mode"] = payload["current_mode"]
    payload["run_state"]["health_level"] = payload["health_level"]
    payload["run_state"]["current_incident_age_seconds"] = payload["current_incident_age_seconds"]
    return payload
