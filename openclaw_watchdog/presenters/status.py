from __future__ import annotations

from openclaw_watchdog import operator_snapshot


def render_status_summary(payload: dict[str, object]) -> str:
    snapshot = operator_snapshot.build_operator_snapshot(
        payload,
        stable_required_runs=int(payload.get('survival_mode_stable_required_runs', 0) or 0) or 1,
        guard_manifest_file=str(payload.get('guard_manifest_file', '') or ''),
    )
    last_event = payload.get('last_event', {})
    recent_stats = payload.get('recent_event_stats', {})
    counts = recent_stats.get('counts', {}) if isinstance(recent_stats, dict) else {}
    recent_incidents = payload.get('recent_incidents', [])
    incident_tail = 'none'
    if isinstance(recent_incidents, list) and recent_incidents:
        last_incident = recent_incidents[-1]
        if isinstance(last_incident, dict):
            incident_tail = str(last_incident.get('incident_id', 'none'))
    survival_summary = 'off'
    if bool(snapshot.get('survival_mode_active', False)):
        survival_summary = (
            'active'
            f"(sticky={str(bool(snapshot.get('survival_mode_sticky', False))).lower()},"
            f"exit_ready={str(bool(snapshot.get('survival_mode_exit_ready', False))).lower()},"
            f"stable={int(snapshot.get('survival_mode_stable_ready_runs', 0) or 0)}/{int(snapshot.get('survival_mode_stable_required_runs', 0) or 0)})"
        )
    elif str(snapshot.get('survival_mode_last_exit_kind', '') or ''):
        survival_summary = f"last-exit={snapshot.get('survival_mode_last_exit_kind', '') or 'unknown'}"
    message_loop_summary = ''
    if bool(payload.get('message_loop_probe_enabled', False)):
        message_loop_summary = str(payload.get('message_loop_probe_summary', '') or 'enabled')
    return ' | '.join(
        [
            f"status={payload.get('last_status', payload.get('status', 'unknown'))}",
            f"conversation={snapshot.get('conversation_status', 'down')}",
            f"health={payload.get('health_level', 'unknown')}",
            f"mode={payload.get('current_mode', 'unknown')}",
            f"recovery={snapshot.get('last_recovery_strategy', 'none')}",
            f"rescue={snapshot.get('rescue_executor_selected', '') or 'none'}/{snapshot.get('candidate_rule_status', '') or 'none'}",
            f"order={operator_snapshot.list_text(snapshot.get('rescue_attempt_order', []), joiner='>')}",
            f"reject={operator_snapshot.list_text(snapshot.get('rescue_rejected_executors', []), joiner=',')}",
            f"learn={snapshot.get('rescue_learning_summary', '') or 'none'}",
            f"survival={survival_summary}",
            f"service={str(bool(payload.get('service_active', False))).lower()}",
            f"probe={payload.get('service_probe_summary', 'n/a')}",
            f"msg_loop={message_loop_summary or 'off'}",
            f"recent=healthy:{counts.get('healthy', 0)},degraded:{counts.get('degraded', 0)},recovered:{counts.get('recovered', 0)},failed:{counts.get('failed', 0)}",
            f"incident_tail={incident_tail}",
            f"last={last_event.get('human_summary', last_event.get('summary', 'none'))}",
        ]
    )
