from __future__ import annotations

from typing import Any

from openclaw_watchdog import health as health_ops
from openclaw_watchdog import rescue_context_builder
from openclaw_watchdog import rescue_learning_service
from openclaw_watchdog import rescue_runtime
from openclaw_watchdog.flows import recovery_finalize_runtime
from openclaw_watchdog.flows import recovery_probe_runtime


def build_rescue_context(engine, probe: dict[str, Any]):
    helper = getattr(engine, 'build_rescue_context', None)
    if callable(helper):
        return helper(probe)
    return rescue_context_builder.build_rescue_context(engine, probe)


def dispatch_rescue(engine, context):
    helper = getattr(engine, 'dispatch_rescue', None)
    if callable(helper):
        return helper(context)
    return rescue_runtime.dispatch_rescue(engine, context)


def execute_rescue_plan(engine, plan, *, executor: str):
    helper = getattr(engine, 'execute_rescue_plan', None)
    if callable(helper):
        return helper(plan, executor=executor)
    return rescue_runtime.execute_rescue_plan(engine, plan, executor=executor)


def record_learning_from_failure(
    engine,
    *,
    strategy: str,
    recovery_kind: str,
    probe: dict[str, Any],
    context=None,
    dispatch_result=None,
    plan_result=None,
):
    helper = getattr(engine, 'record_learning_from_failure', None)
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
    return rescue_learning_service.record_learning_from_failure(
        engine,
        strategy=strategy,
        recovery_kind=recovery_kind,
        probe=probe,
        context=context,
        dispatch_result=dispatch_result,
        plan_result=plan_result,
    )


def mark_dispatch(engine, dispatch_result) -> None:
    from openclaw_watchdog import rescue_policy

    ctx = getattr(engine, 'ctx', None)
    if ctx is None:
        return
    attempts = list(getattr(dispatch_result, 'attempts', []) or [])
    ctx.rescue_attempt_count = len(attempts)
    ctx.rescue_attempt_order = [str(getattr(attempt, 'executor', '') or '') for attempt in attempts if str(getattr(attempt, 'executor', '') or '')]
    ctx.rescue_rejected_executors = [
        f'{executor}:{status}' if status else executor
        for attempt in attempts
        for executor, status in [(str(getattr(attempt, 'executor', '') or ''), str(getattr(attempt, 'status', '') or ''))]
        if executor and status != 'plan-generated'
    ]
    ctx.rescue_executor_selected = str(getattr(dispatch_result, 'final_executor', '') or '')
    ctx.rescue_plan_generated = bool(getattr(dispatch_result, 'plan', None) is not None)
    ctx.rescue_plan_source = str(getattr(dispatch_result, 'final_executor', '') or '')
    plan = getattr(dispatch_result, 'plan', None)
    ctx.rescue_plan_id = str(getattr(plan, 'plan_id', '') or '') if plan is not None else ''
    ctx.rescue_plan_status = 'generated' if plan is not None else 'no-plan'
    action_payloads = []
    if plan is not None:
        for action in list(getattr(plan, 'actions', []) or []):
            if hasattr(action, 'to_dict'):
                action_payloads.append(action.to_dict())
            elif isinstance(action, dict):
                action_payloads.append(action)
    ctx.rescue_mutation_scope = rescue_policy.mutation_scope(action_payloads)
    selected = ctx.rescue_executor_selected
    if selected == 'litellm':
        ctx.rescue_tier = 'litellm'
    elif selected == 'rule-agent':
        ctx.rescue_tier = 'rule-based'
    elif selected:
        ctx.rescue_tier = 'external-cli'
    else:
        ctx.rescue_tier = 'none'


def run_rescue_phase(engine, ctx, state: recovery_probe_runtime.RecoveryPhaseState):
    context = build_rescue_context(engine, state.probe)
    dispatch_result = dispatch_rescue(engine, context)
    mark_dispatch(engine, dispatch_result)
    plan = getattr(dispatch_result, 'plan', None)
    if plan is not None:
        plan_result = execute_rescue_plan(
            engine,
            plan,
            executor=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'),
        )
        ctx.rescue_plan_status = str(getattr(plan_result, 'status', 'unknown') or 'unknown')
        if ctx.rescue_plan_status == 'rolled-back':
            learning_result = record_learning_from_failure(
                engine,
                strategy=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'),
                recovery_kind='rescue',
                probe=state.probe,
                context=context,
                dispatch_result=dispatch_result,
                plan_result=plan_result,
            )
            recovery_finalize_runtime.mark_learning(engine, learning_result)
            return recovery_finalize_runtime.finalize_failure(
                engine,
                summary='rescue plan failed validation and was rolled back',
            )

        state = recovery_probe_runtime.phase_state_from_probe(
            engine,
            dict(health_ops.live_probe(engine, include_doctor=False, apply_grace=True)),
            config_invalid=state.config_invalid,
        )
        outcome = recovery_finalize_runtime.maybe_finalize_recovery(
            engine,
            strategy=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'),
            recovery_kind='rescue',
            state=state,
            context=context,
            dispatch_result=dispatch_result,
            plan_result=plan_result,
        )
        if outcome is not None:
            return outcome

    learning_result = record_learning_from_failure(
        engine,
        strategy=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'),
        recovery_kind='rescue',
        probe=state.probe,
        context=context,
        dispatch_result=dispatch_result,
        plan_result=None,
    )
    recovery_finalize_runtime.mark_learning(engine, learning_result)
    return recovery_finalize_runtime.finalize_failure(
        engine,
        summary='rescue flow exhausted without restoring minimal usability',
    )
