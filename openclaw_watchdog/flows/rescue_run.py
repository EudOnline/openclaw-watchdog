from __future__ import annotations

from datetime import datetime

from openclaw_watchdog import last_good_runtime
from openclaw_watchdog import recovery_tracking
from openclaw_watchdog.flows import recovery_phases


def _stable_required_runs(engine, ctx) -> int:
    config = getattr(engine, 'config', object())
    if hasattr(config, 'watchdog_survival_stable_ready_runs'):
        return max(1, int(getattr(config, 'watchdog_survival_stable_ready_runs', 1) or 1))
    return max(1, int(getattr(ctx, 'survival_mode_stable_required_runs', 1) or 1))


def _reset_recovery_tracking(engine, ctx) -> None:
    helper = getattr(engine, 'reset_recovery_tracking', None)
    if callable(helper):
        helper()
        return
    recovery_tracking.reset(
        ctx,
        stable_required_runs=_stable_required_runs(engine, ctx),
    )


def _refresh_drift_context(engine):
    helper = getattr(engine, 'refresh_drift_context', None)
    if callable(helper):
        return helper()
    return last_good_runtime.apply_drift_context(engine)


def run(engine, ctx):
    from openclaw_watchdog.engine import RunOutcome

    start_ts = datetime.now().astimezone()
    ctx.last_run_started_at = start_ts
    ctx.run_ts = start_ts.strftime('%F %T %Z')
    engine.write_run_state({'last_run_started_at': start_ts.isoformat(timespec='seconds')})
    engine.log('INFO', 'watchdog rescue tick start')

    try:
        _reset_recovery_tracking(engine, ctx)
        _refresh_drift_context(engine)

        phase_state = recovery_phases.baseline_probe_and_sync(engine)
        outcome = recovery_phases.finish_initial_state(engine, phase_state)
        if outcome is not None:
            return outcome

        outcome, phase_state = recovery_phases.run_deterministic_recovery(engine, ctx, phase_state)
        if outcome is not None:
            return outcome

        return recovery_phases.run_rescue_phase(engine, ctx, phase_state)
    finally:
        finish_ts = datetime.now().astimezone()
        ctx.last_run_finished_at = finish_ts
        duration_ms = max(0, int((finish_ts - start_ts).total_seconds() * 1000))
        engine.write_run_state(
            {
                'last_run_finished_at': finish_ts.isoformat(timespec='seconds'),
                'last_run_duration_ms': duration_ms,
            }
        )
