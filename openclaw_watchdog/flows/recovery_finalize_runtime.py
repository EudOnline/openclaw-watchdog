from __future__ import annotations

from typing import Any

from openclaw_watchdog import last_good_runtime
from openclaw_watchdog import rescue_learning_service
from openclaw_watchdog import state_transition
from openclaw_watchdog.flows.recovery_probe_runtime import RecoveryPhaseState, summary_from_probe


def record_learning_from_recovery(
    engine,
    *,
    strategy: str,
    recovery_kind: str,
    probe: dict[str, Any],
    context=None,
    dispatch_result=None,
    plan_result=None,
):
    helper = getattr(engine, 'record_learning_from_recovery', None)
    if callable(helper):
        return helper(
            strategy=strategy,
            recovery_kind=recovery_kind,
            probe=probe,
            context=context,
            dispatch_result=dispatch_result,
            plan_result=plan_result,
        )
    config = getattr(engine, 'config', object())
    if not hasattr(config, 'watchdog_rescue_knowledge_root'):
        return None
    return rescue_learning_service.record_learning_from_recovery(
        engine,
        strategy=strategy,
        recovery_kind=recovery_kind,
        probe=probe,
        context=context,
        dispatch_result=dispatch_result,
        plan_result=plan_result,
    )


def mark_learning(engine, learning_result: dict[str, Any] | None) -> None:
    ctx = getattr(engine, 'ctx', None)
    if ctx is None or not isinstance(learning_result, dict):
        return
    case_ingest_result = str(learning_result.get('case_ingest_result', getattr(ctx, 'case_ingest_result', 'not-run')) or getattr(ctx, 'case_ingest_result', 'not-run'))
    candidate_rule_status = str(
        learning_result.get('candidate_rule_status', getattr(ctx, 'candidate_rule_status', 'none'))
        or getattr(ctx, 'candidate_rule_status', 'none')
    )
    ctx.case_ingest_result = case_ingest_result
    ctx.candidate_rule_status = candidate_rule_status
    ctx.rescue_learning_summary = f'{case_ingest_result} / {candidate_rule_status}'


def refresh_last_good_if_ready(engine, probe: dict[str, Any]) -> None:
    if not bool(probe.get('conversation_ready', False)):
        return
    last_good_runtime.backup_last_good(engine, validation=probe)


def finalize_success(engine, *, strategy: str, probe: dict[str, Any], recovered_from_failure: bool):
    from openclaw_watchdog.engine import RunOutcome

    restored_conversation = bool(probe.get('conversation_ready', False))
    refresh_last_good_if_ready(engine, probe)
    if hasattr(engine, 'finalize_recovery_tracking'):
        engine.finalize_recovery_tracking(strategy=strategy, restored_conversation=restored_conversation)
    summary = summary_from_probe(probe, fallback=f'rescue restored via {strategy}')
    state = 'healthy' if restored_conversation and not recovered_from_failure else 'recovered' if recovered_from_failure else 'degraded'
    health_override = 'healthy' if state == 'healthy' else 'degraded'
    state_transition.set_state(engine, state, summary, health_level_override=health_override)
    return RunOutcome(exit_code=0, state=state, summary=summary)


def finalize_failure(engine, *, summary: str):
    from openclaw_watchdog.engine import RunOutcome

    if hasattr(engine, 'finalize_recovery_tracking'):
        engine.finalize_recovery_tracking(strategy='failed', restored_conversation=False)
    state_transition.set_state(engine, 'failed', summary, health_level_override='failed')
    return RunOutcome(exit_code=1, state='failed', summary=summary)


def maybe_finalize_recovery(
    engine,
    *,
    strategy: str,
    recovery_kind: str,
    state: RecoveryPhaseState,
    context=None,
    dispatch_result=None,
    plan_result=None,
):
    if state.health_level not in {'healthy', 'degraded'}:
        return None
    learning_result = record_learning_from_recovery(
        engine,
        strategy=strategy,
        recovery_kind=recovery_kind,
        probe=state.probe,
        context=context,
        dispatch_result=dispatch_result,
        plan_result=plan_result,
    )
    mark_learning(engine, learning_result)
    return finalize_success(engine, strategy=strategy, probe=state.probe, recovered_from_failure=True)
