from __future__ import annotations


def _list_value(payload: dict[str, object], key: str, *, joiner: str, fallback: str = 'none') -> str:
    value = payload.get(key, [])
    if isinstance(value, list) and value:
        return joiner.join(str(item) for item in value)
    return fallback


def render_report(payload: dict[str, object]) -> str:
    last_event = payload.get('last_event', {})
    recent_stats = payload.get('recent_event_stats', {})
    counts = recent_stats.get('counts', {}) if isinstance(recent_stats, dict) else {}
    recent_incidents = payload.get('recent_incidents', [])
    queue_summary = payload.get('incident_queue_summary', {}) if isinstance(payload.get('incident_queue_summary', {}), dict) else {}
    lines = [
        f"status={payload.get('status', 'unknown')}",
        f"conversation_status={payload.get('conversation_status', 'down')}",
        f"conversation_ready={str(bool(payload.get('conversation_ready', False))).lower()}",
        f"minimal_usable_ready={str(bool(payload.get('minimal_usable_ready', False))).lower()}",
        f"health_level={payload.get('health_level', 'unknown')}",
        f"current_mode={payload.get('current_mode', 'unknown')}",
        f"last_recovery_strategy={payload.get('last_recovery_strategy', 'none')}",
        f"last_recovery_path={payload.get('last_recovery_path', 'none')}",
        f"last_recovery_action_count={payload.get('last_recovery_action_count', 0)}",
        f"last_recovery_restored_conversation={str(bool(payload.get('last_recovery_restored_conversation', False))).lower()}",
        f"rollback_candidate_used={payload.get('rollback_candidate_used', '') or 'none'}",
        f"rollback_reason={payload.get('rollback_reason', '') or 'none'}",
        f"config_drift_detected={str(bool(payload.get('config_drift_detected', False))).lower()}",
        f"drift_scope={_list_value(payload, 'drift_scope', joiner=',')}",
        f"drift_since_last_good={payload.get('drift_since_last_good', '') or 'none'}",
        f"survival_mode_active={str(bool(payload.get('survival_mode_active', False))).lower()}",
        f"survival_mode_reason={payload.get('survival_mode_reason', '') or 'none'}",
        f"survival_mode_since={payload.get('survival_mode_since', '') or 'none'}",
        f"survival_mode_summary={payload.get('survival_mode_summary', '') or 'none'}",
        f"survival_mode_actions={_list_value(payload, 'survival_mode_actions', joiner='; ')}",
        f"survival_mode_disabled_features={_list_value(payload, 'survival_mode_disabled_features', joiner=',')}",
        f"survival_mode_config_file={payload.get('survival_mode_config_file', '') or 'none'}",
        f"survival_mode_sticky={str(bool(payload.get('survival_mode_sticky', False))).lower()}",
        f"survival_mode_sticky_reason={payload.get('survival_mode_sticky_reason', '') or 'none'}",
        f"survival_mode_exit_ready={str(bool(payload.get('survival_mode_exit_ready', False))).lower()}",
        f"survival_mode_exit_policy={payload.get('survival_mode_exit_policy', '') or 'none'}",
        f"survival_mode_exit_blockers={_list_value(payload, 'survival_mode_exit_blockers', joiner='; ')}",
        f"survival_mode_stable_ready_runs={payload.get('survival_mode_stable_ready_runs', 0)}",
        f"survival_mode_stable_required_runs={payload.get('survival_mode_stable_required_runs', 0)}",
        f"survival_mode_manual_clear_required={str(bool(payload.get('survival_mode_manual_clear_required', False))).lower()}",
        f"survival_mode_config_changed_away={str(bool(payload.get('survival_mode_config_changed_away', False))).lower()}",
        f"survival_mode_last_exit_at={payload.get('survival_mode_last_exit_at', '') or 'none'}",
        f"survival_mode_last_exit_reason={payload.get('survival_mode_last_exit_reason', '') or 'none'}",
        f"survival_mode_last_exit_kind={payload.get('survival_mode_last_exit_kind', '') or 'none'}",
        f"survival_mode_last_exit_summary={payload.get('survival_mode_last_exit_summary', '') or 'none'}",
        f"last_good_validated_at={payload.get('last_good_validated_at', '') or 'none'}",
        f"service_active={str(bool(payload.get('service_active', False))).lower()}",
        f"service_probe_summary={payload.get('service_probe_summary', 'n/a')}",
        f"conversation_probe_summary={payload.get('conversation_probe_summary', 'n/a')}",
        f"current_incident_id={payload.get('current_incident_id', '') or 'none'}",
        f"current_incident_state={payload.get('current_incident_state', '') or 'none'}",
        f"cooldown_remaining_seconds={payload.get('cooldown_remaining_seconds', 0)}",
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
