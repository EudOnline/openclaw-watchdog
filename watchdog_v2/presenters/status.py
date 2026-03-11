from __future__ import annotations


def render_status_summary(payload: dict[str, object]) -> str:
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
    if bool(payload.get('survival_mode_active', False)):
        survival_summary = (
            'active'
            f"(sticky={str(bool(payload.get('survival_mode_sticky', False))).lower()},"
            f"exit_ready={str(bool(payload.get('survival_mode_exit_ready', False))).lower()},"
            f"stable={int(payload.get('survival_mode_stable_ready_runs', 0) or 0)}/{int(payload.get('survival_mode_stable_required_runs', 0) or 0)})"
        )
    elif str(payload.get('survival_mode_last_exit_kind', '') or ''):
        survival_summary = f"last-exit={payload.get('survival_mode_last_exit_kind', '') or 'unknown'}"
    return ' | '.join(
        [
            f"status={payload.get('last_status', 'unknown')}",
            f"conv={payload.get('conversation_status', 'down')}",
            f"health={payload.get('health_level', 'unknown')}",
            f"mode={payload.get('current_mode', 'unknown')}",
            f"recovery={payload.get('last_recovery_strategy', 'none')}",
            f"rescue={payload.get('rescue_executor_selected', '') or 'none'}/{payload.get('candidate_rule_status', '') or 'none'}",
            f"order={'>'.join(str(item) for item in payload.get('rescue_attempt_order', []) if str(item)) if isinstance(payload.get('rescue_attempt_order', []), list) and payload.get('rescue_attempt_order', []) else 'none'}",
            f"reject={','.join(str(item) for item in payload.get('rescue_rejected_executors', []) if str(item)) if isinstance(payload.get('rescue_rejected_executors', []), list) and payload.get('rescue_rejected_executors', []) else 'none'}",
            f"survival={survival_summary}",
            f"service={str(bool(payload.get('service_active', False))).lower()}",
            f"probe={payload.get('service_probe_summary', 'n/a')}",
            f"recent=healthy:{counts.get('healthy', 0)},degraded:{counts.get('degraded', 0)},recovered:{counts.get('recovered', 0)},failed:{counts.get('failed', 0)}",
            f"incident_tail={incident_tail}",
            f"last={last_event.get('human_summary', last_event.get('summary', 'none'))}",
        ]
    )
