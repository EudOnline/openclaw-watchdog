from __future__ import annotations

from openclaw_watchdog import operator_snapshot


def _list_value(payload: dict[str, object], key: str, *, joiner: str, fallback: str = 'none') -> str:
    value = payload.get(key, [])
    return operator_snapshot.list_text(value, joiner=joiner, fallback=fallback)


def render_report(payload: dict[str, object]) -> str:
    snapshot = operator_snapshot.build_operator_snapshot(
        payload,
        stable_required_runs=int(payload.get('survival_mode_stable_required_runs', 0) or 0) or 1,
        guard_manifest_file=str(payload.get('guard_manifest_file', '') or ''),
    )
    last_event = payload.get('last_event', {})
    recent_stats = payload.get('recent_event_stats', {})
    counts = recent_stats.get('counts', {}) if isinstance(recent_stats, dict) else {}
    recent_incidents = payload.get('recent_incidents', [])
    queue_summary = payload.get('incident_queue_summary', {}) if isinstance(payload.get('incident_queue_summary', {}), dict) else {}
    lines = [
        f"status={payload.get('status', payload.get('last_status', 'unknown'))}",
        f"conversation_status={snapshot.get('conversation_status', 'down')}",
        f"conversation_ready={str(bool(snapshot.get('conversation_ready', False))).lower()}",
        f"minimal_usable_ready={str(bool(snapshot.get('minimal_usable_ready', False))).lower()}",
        f"health_level={payload.get('health_level', 'unknown')}",
        f"current_mode={payload.get('current_mode', 'unknown')}",
        f"last_recovery_strategy={snapshot.get('last_recovery_strategy', 'none')}",
        f"last_recovery_path={snapshot.get('last_recovery_path', 'none')}",
        f"last_recovery_action_count={snapshot.get('last_recovery_action_count', 0)}",
        f"last_recovery_restored_conversation={str(bool(snapshot.get('last_recovery_restored_conversation', False))).lower()}",
        f"rescue_attempt_count={snapshot.get('rescue_attempt_count', 0)}",
        f"rescue_executor_selected={snapshot.get('rescue_executor_selected', '') or 'none'}",
        f"rescue_plan_generated={str(bool(snapshot.get('rescue_plan_generated', False))).lower()}",
        f"rescue_plan_source={snapshot.get('rescue_plan_source', '') or 'none'}",
        f"rescue_plan_status={snapshot.get('rescue_plan_status', '') or 'none'}",
        f"rescue_tier={snapshot.get('rescue_tier', '') or 'none'}",
        f"case_ingest_result={snapshot.get('case_ingest_result', '') or 'none'}",
        f"candidate_rule_status={snapshot.get('candidate_rule_status', '') or 'none'}",
        f"rescue_attempt_order={operator_snapshot.list_text(snapshot.get('rescue_attempt_order', []), joiner=' -> ')}",
        f"rescue_rejected_executors={operator_snapshot.list_text(snapshot.get('rescue_rejected_executors', []), joiner=', ')}",
        f"rescue_learning_summary={snapshot.get('rescue_learning_summary', '') or 'none'}",
        f"rescue_mutation_scope={operator_snapshot.list_text(snapshot.get('rescue_mutation_scope', []), joiner=', ')}",
        f"rollback_candidate_used={snapshot.get('rollback_candidate_used', '') or 'none'}",
        f"rollback_reason={snapshot.get('rollback_reason', '') or 'none'}",
        f"config_drift_detected={str(bool(snapshot.get('config_drift_detected', False))).lower()}",
        f"drift_scope={operator_snapshot.list_text(snapshot.get('drift_scope', []), joiner=',')}",
        f"drift_since_last_good={snapshot.get('drift_since_last_good', '') or 'none'}",
        f"survival_mode_active={str(bool(snapshot.get('survival_mode_active', False))).lower()}",
        f"survival_mode_reason={snapshot.get('survival_mode_reason', '') or 'none'}",
        f"survival_mode_since={snapshot.get('survival_mode_since', '') or 'none'}",
        f"survival_mode_summary={snapshot.get('survival_mode_summary', '') or 'none'}",
        f"survival_mode_actions={operator_snapshot.list_text(snapshot.get('survival_mode_actions', []), joiner='; ')}",
        f"survival_mode_disabled_features={operator_snapshot.list_text(snapshot.get('survival_mode_disabled_features', []), joiner=',')}",
        f"survival_mode_config_file={snapshot.get('survival_mode_config_file', '') or 'none'}",
        f"survival_mode_sticky={str(bool(snapshot.get('survival_mode_sticky', False))).lower()}",
        f"survival_mode_sticky_reason={snapshot.get('survival_mode_sticky_reason', '') or 'none'}",
        f"survival_mode_exit_ready={str(bool(snapshot.get('survival_mode_exit_ready', False))).lower()}",
        f"survival_mode_exit_policy={snapshot.get('survival_mode_exit_policy', '') or 'none'}",
        f"survival_mode_exit_blockers={operator_snapshot.list_text(snapshot.get('survival_mode_exit_blockers', []), joiner='; ')}",
        f"survival_mode_stable_ready_runs={snapshot.get('survival_mode_stable_ready_runs', 0)}",
        f"survival_mode_stable_required_runs={snapshot.get('survival_mode_stable_required_runs', 0)}",
        f"survival_mode_manual_clear_required={str(bool(snapshot.get('survival_mode_manual_clear_required', False))).lower()}",
        f"survival_mode_config_changed_away={str(bool(snapshot.get('survival_mode_config_changed_away', False))).lower()}",
        f"survival_mode_last_exit_at={snapshot.get('survival_mode_last_exit_at', '') or 'none'}",
        f"survival_mode_last_exit_reason={snapshot.get('survival_mode_last_exit_reason', '') or 'none'}",
        f"survival_mode_last_exit_kind={snapshot.get('survival_mode_last_exit_kind', '') or 'none'}",
        f"survival_mode_last_exit_summary={snapshot.get('survival_mode_last_exit_summary', '') or 'none'}",
        f"last_good_validated_at={snapshot.get('last_good_validated_at', '') or 'none'}",
        f"service_active={str(bool(payload.get('service_active', False))).lower()}",
        f"service_probe_summary={payload.get('service_probe_summary', 'n/a')}",
        f"conversation_probe_summary={snapshot.get('conversation_probe_summary', '') or payload.get('conversation_probe_summary', 'n/a')}",
        f"current_incident_id={payload.get('current_incident_id', '') or 'none'}",
        f"current_incident_state={payload.get('current_incident_state', '') or 'none'}",
        f"last_event_severity={last_event.get('severity', 'none')}",
        f"last_event_human_summary={last_event.get('human_summary', last_event.get('summary', 'none'))}",
        f"recent_counts=healthy:{counts.get('healthy', 0)},degraded:{counts.get('degraded', 0)},recovered:{counts.get('recovered', 0)},failed:{counts.get('failed', 0)}",
        f"queue_open_total={queue_summary.get('open_total', 0)}",
        f"queue_attention_total={queue_summary.get('attention_total', 0)}",
        f"queue_handled_total={queue_summary.get('handled_total', 0)}",
        f"recent_incidents_count={len(recent_incidents) if isinstance(recent_incidents, list) else 0}",
        f"operator_attention_needed={str(bool(payload.get('operator_attention_needed', False))).lower()}",
        f"operator_attention_count={payload.get('operator_attention_count', 0)}",
    ]
    attention_items = payload.get('operator_attention_items', [])
    if isinstance(attention_items, list):
        for idx, item in enumerate(attention_items, start=1):
            lines.append(f'attention_{idx}={item}')
    if isinstance(recent_incidents, list):
        for idx, incident in enumerate(recent_incidents[-5:], start=1):
            if not isinstance(incident, dict):
                continue
            latest_note = incident.get('latest_note', '') or ''
            latest_note_suffix = f' | note={latest_note}' if latest_note else ''
            lines.append(
                f"recent_incident_{idx}={incident.get('incident_id', 'none')} | "
                f"{incident.get('state', 'unknown')} | {incident.get('health_level', 'unknown')} | "
                f"owner={incident.get('owner', '') or 'none'} | ack={str(bool(incident.get('acknowledged', False))).lower()} | "
                f"notes={incident.get('notes_count', 0)} | attention={incident.get('attention_summary', 'none') or 'none'} | "
                f"{incident.get('summary', '')}{latest_note_suffix}"
            )
    return '\n'.join(lines)
