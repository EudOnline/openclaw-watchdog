from __future__ import annotations

from datetime import datetime

from openclaw_watchdog.flows import recovery_phases


def run(engine, ctx):
    from openclaw_watchdog.engine import RunOutcome

    start_ts = datetime.now().astimezone()
    ctx.last_run_started_at = start_ts
    ctx.run_ts = start_ts.strftime('%F %T %Z')
    engine.write_run_state({'last_run_started_at': start_ts.isoformat(timespec='seconds')})
    engine.log('INFO', 'watchdog rescue tick start')

    try:
        engine.reset_recovery_tracking()
        engine.refresh_drift_context()

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
