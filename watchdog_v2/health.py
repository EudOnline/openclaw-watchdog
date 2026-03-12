from __future__ import annotations

import json
import time
from datetime import datetime

from watchdog_v2.config import parse_env_file
from watchdog_v2 import operator_snapshot


def service_level_probe(engine) -> dict[str, object]:
    if not engine.config.watchdog_enable_service_level_probe:
        return {
            "enabled": False,
            "service_layer_healthy": True,
            "service_probe_rc": 0,
            "service_probe_summary": "disabled",
            "service_probe_output": "",
            "service_probe_checked_at": engine.now_iso(),
        }
    result = engine.run_command(
        ["openclaw", "status", "--json", "--timeout", str(engine.config.watchdog_service_level_timeout_seconds * 1000)],
        timeout=max(2, engine.config.watchdog_service_level_timeout_seconds + 2),
        merge_stderr=True,
    )
    raw_output = result.output.strip()
    healthy = result.returncode == 0
    summary = f"rc={result.returncode}"
    payload = None
    candidate_texts: list[str] = []
    if raw_output:
        candidate_texts.append(raw_output)
        if "\n{" in raw_output:
            candidate_texts.append(raw_output[raw_output.rfind("\n{") + 1 :])
        if "{" in raw_output:
            candidate_texts.append(raw_output[raw_output.find("{") :])
    for candidate in candidate_texts:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            payload = parsed
            break
    authoritative = False
    if isinstance(payload, dict):
        gateway = payload.get("gateway")
        if isinstance(gateway, dict) and "reachable" in gateway:
            authoritative = True
            healthy = result.returncode == 0 and bool(gateway.get("reachable"))
            summary = f"gateway.reachable={str(bool(gateway.get('reachable'))).lower()}"
        elif "service_active" in payload:
            authoritative = True
            healthy = result.returncode == 0 and bool(payload.get("service_active"))
            summary = f"service_active={str(bool(payload.get('service_active'))).lower()}"
        else:
            healthy = result.returncode == 0
            summary = "status json parsed"
    elif result.returncode == 0 and raw_output:
        healthy = False
        summary = "status output not parseable"
    else:
        healthy = False
        summary = f"status command failed rc={result.returncode}"

    if not healthy and not authoritative:
        fallback = engine.run_command(["openclaw", "gateway", "status"], timeout=max(2, engine.config.watchdog_service_level_timeout_seconds), merge_stderr=True)
        fallback_output = fallback.output.strip()
        fallback_healthy = False
        fallback_summary = f"fallback rc={fallback.returncode}"
        if "RPC probe: ok" in fallback_output:
            fallback_healthy = True
            fallback_summary = "gateway rpc probe ok"
        elif "active=true" in fallback_output.lower():
            fallback_healthy = True
            fallback_summary = "gateway status active=true"
        elif fallback.returncode != 0:
            fallback_summary = f"gateway status failed rc={fallback.returncode}"
        raw_output = f"{raw_output}\n\n[fallback]\n{fallback_output}".strip()
        if fallback_healthy:
            healthy = True
            summary = fallback_summary
        else:
            summary = f"{summary}; {fallback_summary}"
    return {
        "enabled": True,
        "service_layer_healthy": healthy,
        "service_probe_rc": result.returncode,
        "service_probe_summary": summary,
        "service_probe_output": raw_output,
        "service_status_payload": payload if isinstance(payload, dict) else {},
        "service_probe_checked_at": engine.now_iso(),
    }


def conversation_level_probe(engine, status_payload: dict[str, object] | None, *, service_layer_healthy: bool) -> dict[str, object]:
    payload = status_payload if isinstance(status_payload, dict) else {}
    gateway = payload.get("gateway") if isinstance(payload.get("gateway"), dict) else {}
    conversation = payload.get("conversation") if isinstance(payload.get("conversation"), dict) else {}
    channel_summary = payload.get("channelSummary") if isinstance(payload.get("channelSummary"), list) else []
    gateway_reachable = bool(gateway.get("reachable", service_layer_healthy))
    gateway_misconfigured = bool(gateway.get("misconfigured", False))
    channel_configured = any("configured" in str(item).lower() for item in channel_summary)
    optional_failures_allowed = engine.config.watchdog_minimal_usable_allow_optional_failures

    ready: bool | None = None
    minimal_usable: bool | None = None
    for key in ("ready", "conversation_ready"):
        if key in conversation:
            ready = bool(conversation.get(key))
            break
    for key in ("minimalUsable", "minimal_usable", "minimal_usable_ready"):
        if key in conversation:
            minimal_usable = bool(conversation.get(key))
            break

    if minimal_usable is None:
        minimal_usable = bool(gateway_reachable and (channel_configured or optional_failures_allowed or ready is True))
    if ready is None:
        if channel_summary:
            ready = bool(gateway_reachable and channel_configured and not gateway_misconfigured)
        else:
            ready = bool(minimal_usable and gateway_reachable)
    if ready:
        minimal_usable = True

    status = "ready" if ready else "minimal" if minimal_usable else "down"
    reason_parts = [
        f"gateway={'up' if gateway_reachable else 'down'}",
        f"channels={'configured' if channel_configured else 'missing'}",
    ]
    summary_text = str(conversation.get("summary", "") or "").strip()
    if gateway_misconfigured:
        reason_parts.append("gateway_misconfigured")
    if optional_failures_allowed and not ready and minimal_usable:
        reason_parts.append("optional_failures_allowed")
    if summary_text:
        reason_parts.append(summary_text)
    probe_summary = f"{status}: " + ", ".join(reason_parts)
    if not engine.config.watchdog_enable_conversation_probe:
        probe_summary = f"probe-disabled: service_layer={'up' if service_layer_healthy else 'down'}"
        return {
            "conversation_ready": bool(service_layer_healthy),
            "minimal_usable_ready": bool(service_layer_healthy),
            "conversation_status": "ready" if service_layer_healthy else "down",
            "conversation_probe_summary": probe_summary,
            "conversation_probe_checked_at": engine.now_iso(),
            "conversation_probe_targets": list(engine.config.watchdog_primary_conversation_targets),
        }
    return {
        "conversation_ready": bool(ready),
        "minimal_usable_ready": bool(minimal_usable),
        "conversation_status": status,
        "conversation_probe_summary": probe_summary,
        "conversation_probe_checked_at": engine.now_iso(),
        "conversation_probe_targets": list(engine.config.watchdog_primary_conversation_targets),
    }


def raw_live_probe(engine) -> dict[str, object]:
    active = engine.service_active()
    main_pid = engine.service_main_pid()
    listeners = engine.listener_pids()
    tree_match, match_kind, matching_listener_pid = engine.listener_matches_service_tree(main_pid)
    healthy = active and tree_match
    return {
        "service_active": active,
        "service_main_pid": main_pid,
        "listener_pids": listeners,
        "service_tree_listener_match": tree_match,
        "listener_match_kind": match_kind,
        "matching_listener_pid": matching_listener_pid,
        "healthy": healthy,
    }


def live_probe(engine, *, include_doctor: bool, apply_grace: bool = True) -> dict[str, object]:
    payload = raw_live_probe(engine)
    payload["process_layer_healthy"] = payload["healthy"]
    payload["maintenance_mode"] = engine.config.watchdog_maintenance_file.exists()
    payload["grace_seconds"] = engine.config.watchdog_active_no_listener_grace_seconds
    payload["grace_applied"] = False
    payload["grace_reason"] = ""
    payload["healthy_raw"] = payload["healthy"]

    should_wait_for_listener = (
        apply_grace
        and bool(payload["service_active"])
        and str(payload["service_main_pid"]).isdigit()
        and str(payload["service_main_pid"]) != "0"
        and not bool(payload.get("service_tree_listener_match", False))
        and engine.config.watchdog_active_no_listener_grace_seconds > 0
    )
    if should_wait_for_listener:
        payload["grace_applied"] = True
        payload["grace_reason"] = "service active but listener does not yet match MainPID or its child process tree"
        payload["grace_before_listener_pids"] = list(payload["listener_pids"])
        time.sleep(engine.config.watchdog_active_no_listener_grace_seconds)
        after_grace = raw_live_probe(engine)
        payload.update(after_grace)

    payload["process_layer_healthy"] = bool(payload["healthy"])
    payload["service_probe_retry_grace_seconds"] = engine.config.watchdog_service_level_retry_grace_seconds
    payload["service_probe_retry_applied"] = False
    payload["service_probe_retry_reason"] = ""
    payload["service_probe_retry_initial_summary"] = ""
    payload["service_probe_retry_final_summary"] = ""

    service_probe = service_level_probe(engine)
    payload.update(service_probe)
    payload.update(
        conversation_level_probe(
            engine,
            service_probe.get("service_status_payload") if isinstance(service_probe.get("service_status_payload"), dict) else {},
            service_layer_healthy=bool(payload["service_layer_healthy"]),
        )
    )

    should_retry_service_probe = (
        apply_grace
        and bool(payload["process_layer_healthy"])
        and not bool(payload.get("service_layer_healthy", True))
        and engine.config.watchdog_service_level_retry_grace_seconds > 0
    )
    if should_retry_service_probe:
        payload["service_probe_retry_applied"] = True
        payload["service_probe_retry_reason"] = "process healthy but gateway/service probe not yet reachable"
        payload["service_probe_retry_initial_summary"] = str(payload.get("service_probe_summary", "") or "")
        time.sleep(engine.config.watchdog_service_level_retry_grace_seconds)
        retried_service_probe = service_level_probe(engine)
        payload.update(retried_service_probe)
        payload.update(
            conversation_level_probe(
                engine,
                retried_service_probe.get("service_status_payload") if isinstance(retried_service_probe.get("service_status_payload"), dict) else {},
                service_layer_healthy=bool(payload["service_layer_healthy"]),
            )
        )
        payload["service_probe_retry_final_summary"] = str(payload.get("service_probe_summary", "") or "")
        if bool(payload.get("service_layer_healthy", False)):
            payload["service_probe_summary"] = (
                f"{payload['service_probe_retry_final_summary']} "
                f"(after {engine.config.watchdog_service_level_retry_grace_seconds}s retry; initial {payload['service_probe_retry_initial_summary']})"
            ).strip()
        elif payload["service_probe_retry_initial_summary"]:
            payload["service_probe_summary"] = (
                f"{payload['service_probe_retry_initial_summary']}; retried {engine.config.watchdog_service_level_retry_grace_seconds}s later: "
                f"{payload['service_probe_retry_final_summary'] or payload['service_probe_retry_initial_summary']}"
            )
    if engine.config.watchdog_enable_survivability_flow:
        payload["healthy"] = bool(payload["process_layer_healthy"]) and bool(payload["minimal_usable_ready"])
        if payload["process_layer_healthy"] and payload["conversation_ready"]:
            payload["health_level"] = "healthy"
        elif payload["process_layer_healthy"] and payload["minimal_usable_ready"]:
            payload["health_level"] = "degraded"
        else:
            payload["health_level"] = "failed"
    else:
        payload["healthy"] = bool(payload["process_layer_healthy"]) and bool(payload["service_layer_healthy"])
        if payload["healthy"]:
            payload["health_level"] = "healthy"
        elif payload["process_layer_healthy"]:
            payload["health_level"] = "degraded"
        else:
            payload["health_level"] = "failed"

    payload["survival_mode_active"] = bool(engine.read_run_state().get("survival_mode_active", False))
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
        maintenance=payload["maintenance_mode"],
        degraded=payload["health_level"] == "degraded",
        survival=payload["survival_mode_active"],
    )
    payload["service_probe_failures"] = int(engine.read_run_state().get("service_probe_failures", 0) or 0)
    if include_doctor:
        doctor_rc, doctor_output = engine.run_doctor()
        payload["doctor_rc"] = doctor_rc
        payload["config_invalid"] = engine.config_invalid(doctor_output)
        payload["doctor_output"] = doctor_output.strip()
    return payload


def healthy_now(engine) -> bool:
    probe = live_probe(engine, include_doctor=False, apply_grace=True)
    return bool(probe.get("minimal_usable_ready", probe["process_layer_healthy"]))


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
    queue_payload = engine.incident_queue_payload(limit=5)
    payload: dict[str, object] = {
        "env_file": str(engine.config.env_file) if engine.config.env_file else "",
        "state_dir": str(engine.config.watchdog_state_dir),
        "last_status": last_status,
        "consecutive_failures": engine.read_failure_count(),
        "maintenance": maintenance_info,
        "last_event": read_last_event(engine),
        "recent_events": engine.read_event_history(limit=5),
        "recent_event_stats": engine.recent_event_stats(hours=24),
        "recent_incidents": engine.list_incident_snapshots(limit=5),
        "incident_queue": queue_payload,
        "incident_queue_summary": queue_payload.get("summary", {}),
        "last_good_config_exists": engine.config.watchdog_last_good_config.exists(),
        "current_incident_id": current_incident_id,
        "current_incident_state": current_incident_state,
        "current_incident_age_seconds": current_incident_age_seconds,
        "run_state": run_state,
    }
    payload.update(live_probe(engine, include_doctor=False))
    payload.update(engine.last_good_status())
    payload.update(engine.guard_status())
    payload["health_level"] = payload.get("health_level") or run_state.get("health_level", "unknown")
    for key, default in (
        ("conversation_ready", False),
        ("minimal_usable_ready", False),
        ("conversation_status", "down"),
        ("conversation_probe_summary", ""),
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
