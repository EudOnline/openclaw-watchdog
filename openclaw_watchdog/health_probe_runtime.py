from __future__ import annotations

import json
import time

from openclaw_watchdog import doctor_runtime
from openclaw_watchdog import operator_snapshot
from openclaw_watchdog import service_runtime


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
    active = service_runtime.service_active(engine)
    main_pid = service_runtime.service_main_pid(engine)
    listeners = service_runtime.listener_pids(engine)
    tree_match, match_kind, matching_listener_pid = service_runtime.listener_matches_service_tree(engine, main_pid)
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
        doctor_rc, doctor_output = doctor_runtime.run_doctor(engine)
        payload["doctor_rc"] = doctor_rc
        payload["config_invalid"] = doctor_runtime.config_invalid(engine, doctor_output)
        payload["doctor_output"] = doctor_output.strip()
    return payload


def healthy_now(engine) -> bool:
    probe = live_probe(engine, include_doctor=False, apply_grace=True)
    return bool(probe.get("minimal_usable_ready", probe["process_layer_healthy"]))
