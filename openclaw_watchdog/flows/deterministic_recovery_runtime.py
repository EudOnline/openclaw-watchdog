from __future__ import annotations

from openclaw_watchdog import health as health_ops
from openclaw_watchdog import repair_action_runtime
from openclaw_watchdog import rollback_runtime
from openclaw_watchdog import survival_transition_runtime
from openclaw_watchdog.flows import recovery_finalize_runtime
from openclaw_watchdog.flows import recovery_probe_runtime


def record_step(engine, step: str, outcome: str, detail: str = '') -> None:
    recorder = getattr(engine, 'record_recovery_step', None)
    if callable(recorder):
        recorder(step, outcome, detail)


def run_deterministic_recovery(engine, ctx, state: recovery_probe_runtime.RecoveryPhaseState) -> tuple[object | None, recovery_probe_runtime.RecoveryPhaseState]:
    repair_action_runtime.run_pre_repair_backup(engine)

    restart_ok = bool(repair_action_runtime.restart_service(engine))
    record_step(engine, 'restart', 'applied' if restart_ok else 'failed')
    state = recovery_probe_runtime.phase_state_from_probe(
        engine,
        dict(health_ops.live_probe(engine, include_doctor=False, apply_grace=True)),
        config_invalid=state.config_invalid,
    )
    outcome = recovery_finalize_runtime.maybe_finalize_recovery(
        engine,
        strategy='restart',
        recovery_kind='deterministic',
        state=state,
    )
    if outcome is not None:
        return outcome, state

    rollback_ok = bool(
        rollback_runtime.restore_last_good(
            engine,
            reason='drift-auto-rollback' if getattr(ctx, 'config_drift_detected', False) else 'rescue-flow',
        )
    )
    record_step(engine, 'rollback', 'applied' if rollback_ok else 'failed')
    if rollback_ok:
        repair_action_runtime.restart_service(engine)
    state = recovery_probe_runtime.phase_state_from_probe(
        engine,
        dict(health_ops.live_probe(engine, include_doctor=False, apply_grace=True)),
        config_invalid=state.config_invalid,
    )
    outcome = recovery_finalize_runtime.maybe_finalize_recovery(
        engine,
        strategy='rollback',
        recovery_kind='deterministic',
        state=state,
    )
    if outcome is not None:
        return outcome, state

    if hasattr(engine, 'enter_survival_mode'):
        survival_result = engine.enter_survival_mode(reason='rescue-flow')
    else:
        survival_result = survival_transition_runtime.enter_survival_mode(engine, reason='rescue-flow')
    survival_applied = bool((survival_result or {}).get('applied', False)) if isinstance(survival_result, dict) else bool(survival_result)
    record_step(engine, 'survival', 'applied' if survival_applied else 'failed')
    state = recovery_probe_runtime.phase_state_from_probe(
        engine,
        dict(health_ops.live_probe(engine, include_doctor=False, apply_grace=True)),
        config_invalid=state.config_invalid,
    )
    outcome = recovery_finalize_runtime.maybe_finalize_recovery(
        engine,
        strategy='survival',
        recovery_kind='deterministic',
        state=state,
    )
    if outcome is not None:
        return outcome, state

    doctor_enabled = bool(getattr(getattr(engine, 'config', object()), 'watchdog_enable_doctor_repair', False))
    if doctor_enabled:
        record_step(engine, 'doctor', 'applied')
        repair_action_runtime.run_doctor_repair(engine)
    else:
        record_step(engine, 'doctor', 'skipped')

    return None, state
