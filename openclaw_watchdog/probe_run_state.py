from __future__ import annotations

from openclaw_watchdog import survival_state_runtime


def service_probe_failures_for(config, probe: dict[str, object], previous_failures: int) -> int:
    process_layer_healthy = bool(probe.get("process_layer_healthy", False))
    service_layer_healthy = bool(probe.get("service_layer_healthy", True))
    if bool(getattr(config, 'watchdog_enable_service_level_probe', False)) and process_layer_healthy and not service_layer_healthy:
        return previous_failures + 1
    return 0


def derive_health_level(probe: dict[str, object], *, config_invalid: bool) -> str:
    process_layer_healthy = bool(probe.get("process_layer_healthy", False))
    conversation_ready = bool(probe.get("conversation_ready", False))
    minimal_usable_ready = bool(probe.get("minimal_usable_ready", False))
    if config_invalid or not process_layer_healthy:
        return "failed"
    if conversation_ready:
        return "healthy"
    if minimal_usable_ready:
        return "degraded"
    return "failed"


def write_probe_run_state(engine, probe: dict[str, object], *, config_invalid: bool, service_probe_failures: int) -> str:
    engine.ctx.latest_probe = dict(probe)
    service_layer_healthy = bool(probe.get("service_layer_healthy", True))
    conversation_ready = bool(probe.get("conversation_ready", False))
    minimal_usable_ready = bool(probe.get("minimal_usable_ready", False))
    initial_health_level = derive_health_level(probe, config_invalid=config_invalid)
    engine.write_run_state(
        {
            "service_probe_failures": service_probe_failures,
            "last_service_probe_at": str(probe.get("service_probe_checked_at", engine.now_iso())),
            "last_service_probe_result": "healthy" if service_layer_healthy else "degraded",
            "last_service_probe_summary": str(probe.get("service_probe_summary", "")),
            "last_service_probe_rc": int(probe.get("service_probe_rc", 0) or 0),
            "health_level": initial_health_level,
            "current_mode": engine.current_mode(
                maintenance=engine.config.watchdog_maintenance_file.exists(),
                degraded=initial_health_level == "degraded",
                survival=engine.ctx.survival_mode_active,
            ),
            "conversation_ready": conversation_ready,
            "minimal_usable_ready": minimal_usable_ready,
            "conversation_status": str(probe.get("conversation_status", "down") or "down"),
            "conversation_probe_summary": str(probe.get("conversation_probe_summary", "") or ""),
            **survival_state_runtime.run_state_fields(engine),
        }
    )
    return initial_health_level
