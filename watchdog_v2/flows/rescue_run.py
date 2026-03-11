from __future__ import annotations

from datetime import datetime
from typing import Any


def _probe_state(probe: dict[str, Any], *, config_invalid: bool) -> str:
    process_layer_healthy = bool(probe.get('process_layer_healthy', False))
    conversation_ready = bool(probe.get('conversation_ready', False))
    minimal_usable_ready = bool(probe.get('minimal_usable_ready', False))
    if config_invalid or not process_layer_healthy:
        return 'failed'
    if conversation_ready:
        return 'healthy'
    if minimal_usable_ready:
        return 'degraded'
    return 'failed'


def _summary_from_probe(probe: dict[str, Any], *, fallback: str) -> str:
    conversation_status = str(probe.get('conversation_status', '') or '')
    conversation_probe_summary = str(probe.get('conversation_probe_summary', '') or '')
    service_probe_summary = str(probe.get('service_probe_summary', '') or '')
    for value in (conversation_probe_summary, service_probe_summary, conversation_status):
        if value:
            return value
    return fallback


def _previous_service_probe_failures(engine) -> int:
    if not hasattr(engine, 'read_run_state'):
        return 0
    state = engine.read_run_state()
    return int(state.get('service_probe_failures', 0) or 0) if isinstance(state, dict) else 0


def _service_probe_failures_for(engine, probe: dict[str, Any]) -> int:
    helper = getattr(engine, '_service_probe_failures_for', None)
    if callable(helper):
        return int(helper(probe, _previous_service_probe_failures(engine)) or 0)
    return 0


def _write_probe_run_state(engine, probe: dict[str, Any], *, config_invalid: bool, service_probe_failures: int) -> str:
    helper = getattr(engine, '_write_probe_run_state', None)
    if callable(helper):
        return str(helper(probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures) or 'failed')
    return _probe_state(probe, config_invalid=config_invalid)


def _record_step(engine, step: str, outcome: str, detail: str = '') -> None:
    recorder = getattr(engine, 'record_recovery_step', None)
    if callable(recorder):
        recorder(step, outcome, detail)


def _finalize_success(engine, *, strategy: str, probe: dict[str, Any], recovered_from_failure: bool):
    from watchdog_v2.engine import RunOutcome

    restored_conversation = bool(probe.get('conversation_ready', False))
    if hasattr(engine, 'finalize_recovery_tracking'):
        engine.finalize_recovery_tracking(strategy=strategy, restored_conversation=restored_conversation)
    summary = _summary_from_probe(probe, fallback=f'rescue restored via {strategy}')
    state = 'healthy' if restored_conversation and not recovered_from_failure else 'recovered' if recovered_from_failure else 'degraded'
    health_override = 'healthy' if state == 'healthy' else 'degraded'
    if hasattr(engine, 'set_state'):
        engine.set_state(state, summary, health_level_override=health_override)
    return RunOutcome(exit_code=0, state=state, summary=summary)


def _mark_dispatch(engine, dispatch_result) -> None:
    from watchdog_v2 import rescue_policy

    ctx = getattr(engine, 'ctx', None)
    if ctx is None:
        return
    attempts = list(getattr(dispatch_result, 'attempts', []) or [])
    ctx.rescue_attempt_count = len(attempts)
    ctx.rescue_attempt_order = [str(getattr(attempt, 'executor', '') or '') for attempt in attempts if str(getattr(attempt, 'executor', '') or '')]
    ctx.rescue_rejected_executors = [
        f"{executor}:{status}" if status else executor
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


def _mark_learning(engine, learning_result: dict[str, Any] | None) -> None:
    ctx = getattr(engine, 'ctx', None)
    if ctx is None or not isinstance(learning_result, dict):
        return
    ctx.case_ingest_result = str(learning_result.get('case_ingest_result', ctx.case_ingest_result) or ctx.case_ingest_result)
    ctx.candidate_rule_status = str(learning_result.get('candidate_rule_status', ctx.candidate_rule_status) or ctx.candidate_rule_status)
    ctx.rescue_learning_summary = f"{ctx.case_ingest_result} / {ctx.candidate_rule_status}"


def run(engine, ctx):
    from watchdog_v2.engine import RunOutcome

    start_ts = datetime.now().astimezone()
    ctx.last_run_started_at = start_ts
    ctx.run_ts = start_ts.strftime('%F %T %Z')
    if hasattr(engine, 'write_run_state'):
        engine.write_run_state({'last_run_started_at': start_ts.isoformat(timespec='seconds')})
    if hasattr(engine, 'log'):
        engine.log('INFO', 'watchdog rescue tick start')

    try:
        if hasattr(engine, 'reset_recovery_tracking'):
            engine.reset_recovery_tracking()

        probe = dict(engine.live_probe(include_doctor=True, apply_grace=True))
        config_invalid = bool(probe.get('config_invalid', False))
        if hasattr(engine, 'sync_survival_mode'):
            engine.sync_survival_mode(probe=probe, config_invalid=config_invalid)
        service_probe_failures = _service_probe_failures_for(engine, probe)
        _write_probe_run_state(engine, probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
        initial_health = _probe_state(probe, config_invalid=config_invalid)

        if initial_health == 'healthy':
            if hasattr(engine, 'finalize_recovery_tracking'):
                engine.finalize_recovery_tracking(strategy='none', restored_conversation=True)
            summary = _summary_from_probe(probe, fallback='conversation is ready')
            if hasattr(engine, 'set_state'):
                engine.set_state('healthy', summary, health_level_override='healthy')
            return RunOutcome(exit_code=0, state='healthy', summary=summary)
        if initial_health == 'degraded':
            if hasattr(engine, 'finalize_recovery_tracking'):
                engine.finalize_recovery_tracking(strategy='none', restored_conversation=False)
            summary = _summary_from_probe(probe, fallback='minimal conversation remains available')
            if hasattr(engine, 'set_state'):
                engine.set_state('degraded', summary, health_level_override='degraded')
            return RunOutcome(exit_code=0, state='degraded', summary=summary)

        if hasattr(engine, 'run_pre_repair_backup'):
            engine.run_pre_repair_backup()

        if hasattr(engine, 'restart_service'):
            restart_ok = bool(engine.restart_service())
            _record_step(engine, 'restart', 'applied' if restart_ok else 'failed')
            probe = dict(engine.live_probe(include_doctor=False, apply_grace=True))
            config_invalid = bool(probe.get('config_invalid', config_invalid))
            service_probe_failures = _service_probe_failures_for(engine, probe)
            _write_probe_run_state(engine, probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
            health_level = _probe_state(probe, config_invalid=config_invalid)
            if health_level in {'healthy', 'degraded'}:
                learning_result = None
                if hasattr(engine, 'record_learning_from_recovery'):
                    learning_result = engine.record_learning_from_recovery(strategy='restart', recovery_kind='deterministic', probe=probe)
                _mark_learning(engine, learning_result)
                return _finalize_success(engine, strategy='restart', probe=probe, recovered_from_failure=True)

        if hasattr(engine, 'restore_last_good'):
            rollback_ok = bool(engine.restore_last_good(reason='rescue-flow'))
            _record_step(engine, 'rollback', 'applied' if rollback_ok else 'failed')
            probe = dict(engine.live_probe(include_doctor=False, apply_grace=True))
            config_invalid = bool(probe.get('config_invalid', config_invalid))
            service_probe_failures = _service_probe_failures_for(engine, probe)
            _write_probe_run_state(engine, probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
            health_level = _probe_state(probe, config_invalid=config_invalid)
            if health_level in {'healthy', 'degraded'}:
                learning_result = None
                if hasattr(engine, 'record_learning_from_recovery'):
                    learning_result = engine.record_learning_from_recovery(strategy='rollback', recovery_kind='deterministic', probe=probe)
                _mark_learning(engine, learning_result)
                return _finalize_success(engine, strategy='rollback', probe=probe, recovered_from_failure=True)

        if hasattr(engine, 'enter_survival_mode'):
            survival_result = engine.enter_survival_mode(reason='rescue-flow')
            survival_applied = bool((survival_result or {}).get('applied', False)) if isinstance(survival_result, dict) else bool(survival_result)
            _record_step(engine, 'survival', 'applied' if survival_applied else 'failed')
            probe = dict(engine.live_probe(include_doctor=False, apply_grace=True))
            config_invalid = bool(probe.get('config_invalid', config_invalid))
            service_probe_failures = _service_probe_failures_for(engine, probe)
            _write_probe_run_state(engine, probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
            health_level = _probe_state(probe, config_invalid=config_invalid)
            if health_level in {'healthy', 'degraded'}:
                learning_result = None
                if hasattr(engine, 'record_learning_from_recovery'):
                    learning_result = engine.record_learning_from_recovery(strategy='survival', recovery_kind='deterministic', probe=probe)
                _mark_learning(engine, learning_result)
                return _finalize_success(engine, strategy='survival', probe=probe, recovered_from_failure=True)

        doctor_enabled = bool(getattr(getattr(engine, 'config', object()), 'watchdog_enable_doctor_repair', False))
        if doctor_enabled and hasattr(engine, 'run_doctor_repair'):
            _record_step(engine, 'doctor', 'applied')
            engine.run_doctor_repair()
        else:
            _record_step(engine, 'doctor', 'skipped')

        context = engine.build_rescue_context(probe)
        dispatch_result = engine.dispatch_rescue(context)
        _mark_dispatch(engine, dispatch_result)
        plan = getattr(dispatch_result, 'plan', None)
        if plan is not None:
            plan_result = engine.execute_rescue_plan(plan, executor=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'))
            ctx.rescue_plan_status = str(getattr(plan_result, 'status', 'unknown') or 'unknown')
            probe = dict(engine.live_probe(include_doctor=False, apply_grace=True))
            config_invalid = bool(probe.get('config_invalid', config_invalid))
            service_probe_failures = _service_probe_failures_for(engine, probe)
            _write_probe_run_state(engine, probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
            health_level = _probe_state(probe, config_invalid=config_invalid)
            if health_level in {'healthy', 'degraded'}:
                learning_result = None
                if hasattr(engine, 'record_learning_from_recovery'):
                    learning_result = engine.record_learning_from_recovery(
                        strategy=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'),
                        recovery_kind='rescue',
                        probe=probe,
                        context=context,
                        dispatch_result=dispatch_result,
                        plan_result=plan_result,
                    )
                elif hasattr(engine, 'record_learning_from_rescue'):
                    learning_result = engine.record_learning_from_rescue(context=context, dispatch_result=dispatch_result, plan_result=plan_result)
                _mark_learning(engine, learning_result)
                return _finalize_success(
                    engine,
                    strategy=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'),
                    probe=probe,
                    recovered_from_failure=True,
                )

        summary = 'rescue flow exhausted without restoring minimal usability'
        if hasattr(engine, 'finalize_recovery_tracking'):
            engine.finalize_recovery_tracking(strategy='failed', restored_conversation=False)
        if hasattr(engine, 'set_state'):
            engine.set_state('failed', summary, health_level_override='failed')
        return RunOutcome(exit_code=1, state='failed', summary=summary)
    finally:
        finish_ts = datetime.now().astimezone()
        ctx.last_run_finished_at = finish_ts
        duration_ms = max(0, int((finish_ts - start_ts).total_seconds() * 1000))
        if hasattr(engine, 'write_run_state'):
            engine.write_run_state(
                {
                    'last_run_finished_at': finish_ts.isoformat(timespec='seconds'),
                    'last_run_duration_ms': duration_ms,
                }
            )
