from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openclaw_watchdog import health as health_ops
from openclaw_watchdog import probe_run_state
from openclaw_watchdog import recovery_tracking
from openclaw_watchdog import survival_transition_runtime
from openclaw_watchdog import state_transition


@dataclass
class RecoveryPhaseState:
    probe: dict[str, Any]
    config_invalid: bool
    health_level: str


def probe_state(
    probe: dict[str, Any],
    *,
    config_invalid: bool,
    survivability_enabled: bool = True,
    service_probe_failures: int = 0,
    service_failure_threshold: int = 1,
) -> str:
    process_layer_healthy = bool(probe.get('process_layer_healthy', False))
    service_layer_healthy = bool(probe.get('service_layer_healthy', False))
    conversation_ready = bool(probe.get('conversation_ready', False))
    minimal_usable_ready = bool(probe.get('minimal_usable_ready', False))
    if config_invalid or not process_layer_healthy:
        return 'failed'
    if not survivability_enabled:
        if not service_layer_healthy and service_probe_failures >= max(1, service_failure_threshold):
            return 'failed'
        return 'healthy' if service_layer_healthy else 'degraded'
    if conversation_ready:
        return 'healthy'
    if minimal_usable_ready:
        return 'degraded'
    return 'failed'


def summary_from_probe(probe: dict[str, Any], *, fallback: str) -> str:
    conversation_status = str(probe.get('conversation_status', '') or '')
    conversation_probe_summary = str(probe.get('conversation_probe_summary', '') or '')
    service_probe_summary = str(probe.get('service_probe_summary', '') or '')
    for value in (conversation_probe_summary, service_probe_summary, conversation_status):
        if value:
            return value
    return fallback


def previous_service_probe_failures(engine) -> int:
    state = engine.read_run_state()
    return int(state.get('service_probe_failures', 0) or 0) if isinstance(state, dict) else 0


def service_probe_failures_for(engine, probe: dict[str, Any]) -> int:
    helper = getattr(engine, '_service_probe_failures_for', None)
    if callable(helper):
        return int(helper(probe, previous_service_probe_failures(engine)) or 0)
    return int(
        probe_run_state.service_probe_failures_for(
            getattr(engine, 'config', object()),
            probe,
            previous_service_probe_failures(engine),
        )
        or 0
    )


def write_probe_run_state(engine, probe: dict[str, Any], *, config_invalid: bool, service_probe_failures: int) -> str:
    helper = getattr(engine, '_write_probe_run_state', None)
    if callable(helper):
        return str(helper(probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures) or 'failed')
    return str(
        probe_run_state.write_probe_run_state(
            engine,
            probe,
            config_invalid=config_invalid,
            service_probe_failures=service_probe_failures,
        )
        or 'failed'
    )


def phase_state_from_probe(engine, probe: dict[str, Any], *, config_invalid: bool) -> RecoveryPhaseState:
    resolved_config_invalid = bool(probe.get('config_invalid', config_invalid))
    survivability_enabled = bool(getattr(getattr(engine, 'config', object()), 'watchdog_enable_survivability_flow', False))
    service_probe_failures = service_probe_failures_for(engine, probe)
    service_failure_threshold = int(getattr(getattr(engine, 'config', object()), 'watchdog_service_level_failure_threshold', 1) or 1)
    write_probe_run_state(
        engine,
        probe,
        config_invalid=resolved_config_invalid,
        service_probe_failures=service_probe_failures,
    )
    return RecoveryPhaseState(
        probe=probe,
        config_invalid=resolved_config_invalid,
        health_level=probe_state(
            probe,
            config_invalid=resolved_config_invalid,
            survivability_enabled=survivability_enabled,
            service_probe_failures=service_probe_failures,
            service_failure_threshold=service_failure_threshold,
        ),
    )


def baseline_probe_and_sync(engine) -> RecoveryPhaseState:
    probe = dict(health_ops.live_probe(engine, include_doctor=True, apply_grace=True))
    config_invalid = bool(probe.get('config_invalid', False))
    survival_transition_runtime.sync_survival_mode(engine, probe=probe, config_invalid=config_invalid)
    return phase_state_from_probe(engine, probe, config_invalid=config_invalid)


def finalize_recovery_tracking(engine, *, strategy: str, restored_conversation: bool) -> None:
    helper = getattr(engine, 'finalize_recovery_tracking', None)
    if callable(helper):
        helper(strategy=strategy, restored_conversation=restored_conversation)
        return
    recovery_tracking.finalize(engine.ctx, strategy=strategy, restored_conversation=restored_conversation)


def finish_initial_state(engine, state: RecoveryPhaseState):
    from openclaw_watchdog.engine import RunOutcome
    from openclaw_watchdog.flows import recovery_finalize_runtime as finalize_runtime

    if state.health_level == 'healthy':
        finalize_runtime.refresh_last_good_if_ready(engine, state.probe)
        finalize_recovery_tracking(engine, strategy='none', restored_conversation=True)
        summary = summary_from_probe(state.probe, fallback='conversation is ready')
        state_transition.set_state(engine, 'healthy', summary, health_level_override='healthy')
        return RunOutcome(exit_code=0, state='healthy', summary=summary)

    if state.health_level == 'degraded':
        finalize_recovery_tracking(engine, strategy='none', restored_conversation=False)
        summary = summary_from_probe(state.probe, fallback='minimal conversation remains available')
        state_transition.set_state(engine, 'degraded', summary, health_level_override='degraded')
        return RunOutcome(exit_code=0, state='degraded', summary=summary)

    return None
