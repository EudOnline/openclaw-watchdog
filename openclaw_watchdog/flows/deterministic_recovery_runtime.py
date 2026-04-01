from __future__ import annotations

from openclaw_watchdog import health as health_ops
from openclaw_watchdog import model_failover_runtime
from openclaw_watchdog import repair_action_runtime
from openclaw_watchdog import recovery_tracking
from openclaw_watchdog import rollback_runtime
from openclaw_watchdog import survival_transition_runtime
from openclaw_watchdog.flows import recovery_finalize_runtime
from openclaw_watchdog.flows import recovery_probe_runtime


def record_step(engine, step: str, outcome: str, detail: str = '') -> None:
    recorder = getattr(engine, 'record_recovery_step', None)
    if callable(recorder):
        recorder(step, outcome, detail)
        return
    recovery_tracking.record_step(engine.ctx, step, outcome, detail)


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

    model_failover_enabled = bool(
        getattr(getattr(engine, 'config', object()), 'watchdog_enable_model_http_error_failover', False)
    )
    if model_failover_enabled:
        model_failover_result = model_failover_runtime.apply_model_http_error_failover(engine)
        model_failover_applied = bool((model_failover_result or {}).get('applied', False)) if isinstance(model_failover_result, dict) else False
        model_failover_status = str((model_failover_result or {}).get('status', '') or '') if isinstance(model_failover_result, dict) else ''
        model_failover_detail = str((model_failover_result or {}).get('summary', '') or '') if isinstance(model_failover_result, dict) else ''
        record_step(
            engine,
            'model-failover',
            'applied' if model_failover_applied else 'failed' if model_failover_status == 'failed' else 'skipped',
            model_failover_detail,
        )
        if model_failover_applied:
            repair_action_runtime.restart_service(engine)
            state = recovery_probe_runtime.phase_state_from_probe(
                engine,
                dict(health_ops.live_probe(engine, include_doctor=False, apply_grace=True)),
                config_invalid=state.config_invalid,
            )
            outcome = recovery_finalize_runtime.maybe_finalize_recovery(
                engine,
                strategy='model-failover',
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
    rollback_config_invalid = False if rollback_ok else state.config_invalid
    state = recovery_probe_runtime.phase_state_from_probe(
        engine,
        dict(health_ops.live_probe(engine, include_doctor=False, apply_grace=True)),
        config_invalid=rollback_config_invalid,
    )
    outcome = recovery_finalize_runtime.maybe_finalize_recovery(
        engine,
        strategy='rollback',
        recovery_kind='deterministic',
        state=state,
    )
    if outcome is not None:
        return outcome, state

    survival_result = survival_transition_runtime.enter_survival_mode(engine, reason='rescue-flow')
    survival_applied = bool((survival_result or {}).get('applied', False)) if isinstance(survival_result, dict) else bool(survival_result)
    record_step(engine, 'survival', 'applied' if survival_applied else 'failed')
    if survival_applied:
        repair_action_runtime.restart_service(engine)
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
        doctor_ok = bool(repair_action_runtime.run_doctor_repair(engine))
        record_step(engine, 'doctor', 'applied' if doctor_ok else 'failed')
        if not doctor_ok:
            return None, state
        repair_action_runtime.restart_service(engine)
        doctor_config_invalid = False
        state = recovery_probe_runtime.phase_state_from_probe(
            engine,
            dict(health_ops.live_probe(engine, include_doctor=False, apply_grace=True)),
            config_invalid=doctor_config_invalid,
        )
        outcome = recovery_finalize_runtime.maybe_finalize_recovery(
            engine,
            strategy='doctor',
            recovery_kind='deterministic',
            state=state,
        )
        if outcome is not None:
            return outcome, state
    else:
        record_step(engine, 'doctor', 'skipped')

    return None, state
