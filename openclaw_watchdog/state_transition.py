from __future__ import annotations

from openclaw_watchdog import event_runtime
from openclaw_watchdog import incident_service as incident_service_ops
from openclaw_watchdog import last_good_runtime
from openclaw_watchdog import reporting as reporting_ops
from openclaw_watchdog import survival_state_runtime


def _health_level_for(new_state: str, health_level_override: str | None) -> str:
    if health_level_override:
        return health_level_override
    if new_state in {'healthy', 'recovered'}:
        return 'healthy'
    if new_state == 'degraded':
        return 'degraded'
    return 'failed'


def _base_run_state_updates(engine, new_state: str, *, health_level: str) -> dict[str, object]:
    run_state_updates: dict[str, object] = {
        'current_mode': engine.current_mode(
            maintenance=engine.config.watchdog_maintenance_file.exists(),
            degraded=new_state == 'degraded',
            survival=engine.ctx.survival_mode_active,
        ),
        'health_level': health_level,
        'last_backup_result': engine.ctx.pre_repair_backup_result,
        'last_rollback_summary_archive_file': engine.ctx.rollback_summary_archive_file,
        'rollback_candidate_used': engine.ctx.rollback_candidate_used,
        'rollback_reason': engine.ctx.rollback_reason,
        'config_drift_detected': engine.ctx.config_drift_detected,
        'last_recovery_strategy': engine.ctx.last_recovery_strategy,
        'last_recovery_path': engine.recovery_path_text(),
        'last_recovery_action_count': engine.ctx.last_recovery_action_count,
        'last_recovery_restored_conversation': engine.ctx.last_recovery_restored_conversation,
        'rescue_attempt_count': engine.ctx.rescue_attempt_count,
        'rescue_executor_selected': engine.ctx.rescue_executor_selected,
        'rescue_plan_generated': engine.ctx.rescue_plan_generated,
        'rescue_plan_source': engine.ctx.rescue_plan_source,
        'rescue_plan_id': engine.ctx.rescue_plan_id,
        'rescue_plan_status': engine.ctx.rescue_plan_status,
        'rescue_tier': engine.ctx.rescue_tier,
        'case_ingest_result': engine.ctx.case_ingest_result,
        'candidate_rule_status': engine.ctx.candidate_rule_status,
        'rescue_attempt_order': list(engine.ctx.rescue_attempt_order),
        'rescue_rejected_executors': list(engine.ctx.rescue_rejected_executors),
        'rescue_learning_summary': engine.ctx.rescue_learning_summary,
        'rescue_mutation_scope': list(engine.ctx.rescue_mutation_scope),
        **survival_state_runtime.run_state_fields(engine),
        'last_good_validated_at': engine.ctx.last_good_validated_at,
        'last_good_generation_id': engine.ctx.last_good_generation_id,
        'last_good_generation_count': engine.ctx.last_good_generation_count,
        'drift_scope': list(engine.ctx.drift_scope),
        'drift_since_last_good': engine.ctx.drift_since_last_good,
        'drift_summary': engine.ctx.drift_summary,
        **last_good_runtime.guard_status(engine.config),
    }
    if engine.ctx.latest_probe:
        run_state_updates.update(
            {
                'conversation_ready': bool(engine.ctx.latest_probe.get('conversation_ready', False)),
                'minimal_usable_ready': bool(engine.ctx.latest_probe.get('minimal_usable_ready', False)),
                'conversation_status': str(engine.ctx.latest_probe.get('conversation_status', 'down') or 'down'),
                'conversation_probe_summary': str(engine.ctx.latest_probe.get('conversation_probe_summary', '') or ''),
            }
        )
    if engine.ctx.pre_repair_backup_result != 'not-run':
        run_state_updates['last_backup_at'] = engine.ctx.run_ts
    if engine.ctx.rollback_occurred:
        run_state_updates['last_rollback_at'] = engine.ctx.run_ts
        run_state_updates['last_rollback_summary_archive_file'] = engine.ctx.rollback_summary_archive_file
    return run_state_updates


def _apply_state_effects(engine, new_state: str, summary: str, *, health_level: str, run_state_updates: dict[str, object]) -> tuple[bool, bool]:
    should_refresh_incident_index = False
    should_clear_incident_context = False

    if new_state == 'healthy':
        engine.reset_failure_count()
        engine.incident_backup_marker.unlink(missing_ok=True)
        engine.ctx.pre_repair_backup_result = 'not-run'
        if engine.ctx.incident_dir is not None:
            incident_service_ops.update_incident_state(engine, 'resolved', summary, resolved=True)
            should_refresh_incident_index = True
            should_clear_incident_context = True
        run_state_updates['last_success_at'] = engine.ctx.run_ts
        run_state_updates['current_incident_id'] = ''
        run_state_updates['current_incident_state'] = ''
        run_state_updates['current_incident_age_seconds'] = 0
        return should_refresh_incident_index, should_clear_incident_context

    if new_state == 'recovered':
        engine.reset_failure_count()
        if engine.ctx.incident_dir is not None:
            incident_service_ops.update_incident_state(engine, 'resolved', summary, resolved=True)
            run_state_updates['current_incident_id'] = engine.ctx.incident_id
            run_state_updates['current_incident_state'] = 'resolved'
            should_refresh_incident_index = True
        run_state_updates['last_success_at'] = engine.ctx.run_ts
        run_state_updates['last_recovered_at'] = engine.ctx.run_ts
        return should_refresh_incident_index, should_clear_incident_context

    if new_state == 'degraded':
        run_state_updates['last_degraded_at'] = engine.ctx.run_ts
        return should_refresh_incident_index, should_clear_incident_context

    if new_state == 'failed':
        if engine.ctx.incident_dir is not None:
            incident_service_ops.update_incident_state(engine, 'open', summary)
            run_state_updates['current_incident_id'] = engine.ctx.incident_id
            run_state_updates['current_incident_state'] = 'open'
            should_refresh_incident_index = True
        run_state_updates['last_failed_at'] = engine.ctx.run_ts
        return should_refresh_incident_index, should_clear_incident_context

    return should_refresh_incident_index, should_clear_incident_context


def _notify_state_change(engine, new_state: str, old_state: str, *, report_text: str) -> None:
    if new_state == 'healthy':
        return
    if new_state == 'degraded' and old_state != 'degraded' and engine.config.watchdog_notify_on_degraded:
        engine.notify(f'⚠️ OpenClaw watchdog 状态变化\n时间：{engine.ctx.run_ts}\n{report_text}')
    elif new_state == 'recovered' and old_state != 'recovered' and engine.config.watchdog_notify_on_recovery:
        engine.notify(f'✅ OpenClaw watchdog 状态变化\n时间：{engine.ctx.run_ts}\n{report_text}')
    elif new_state == 'failed' and old_state != 'failed' and engine.config.watchdog_notify_on_failure:
        engine.notify(
            f'❌ OpenClaw watchdog 状态变化\n时间：{engine.ctx.run_ts}\n{report_text}\n日志：{engine.config.watchdog_log_file}'
        )


def set_state(engine, new_state: str, summary: str, *, health_level_override: str | None = None) -> None:
    if new_state in {'healthy', 'recovered'}:
        incident_service_ops.attach_current_incident_if_any(engine)
    old_state = 'unknown'
    if engine.last_status_file.exists():
        old_state = engine.last_status_file.read_text(encoding='utf-8').strip() or 'unknown'
    engine.last_status_file.write_text(new_state, encoding='utf-8')

    health_level = _health_level_for(new_state, health_level_override)
    run_state_updates = _base_run_state_updates(engine, new_state, health_level=health_level)
    should_refresh_incident_index, should_clear_incident_context = _apply_state_effects(
        engine,
        new_state,
        summary,
        health_level=health_level,
        run_state_updates=run_state_updates,
    )
    engine.write_run_state(run_state_updates)
    if should_refresh_incident_index:
        incident_service_ops.refresh_current_incident_index(engine, summary=summary, health_level=health_level)
    if should_clear_incident_context:
        incident_service_ops.reset_incident_state(engine)
    event_runtime.write_event(engine, new_state, summary)
    transition_report = reporting_ops.report_payload(engine, incident_limit=5)
    report_text = engine.append_rollback_summary(str(transition_report.get('message_text', '') or ''))
    _notify_state_change(engine, new_state, old_state, report_text=report_text)
