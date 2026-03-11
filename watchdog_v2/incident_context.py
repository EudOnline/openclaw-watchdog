from __future__ import annotations

from watchdog_v2.models import IncidentSummary, RunStateSnapshot


def report_attention_items(report: dict[str, object]) -> list[str]:
    items: list[str] = []
    if str(report.get('current_incident_state', '') or '') != 'open':
        return items
    if not str(report.get('current_incident_owner', '') or '').strip():
        items.append('current incident is unowned')
    if not bool(report.get('current_incident_acknowledged', False)):
        items.append('current incident is unacknowledged')
    if int(report.get('current_incident_notes_count', 0) or 0) <= 0:
        items.append('current incident has no operator notes')
    return items


def _incident_summary(incident: object) -> IncidentSummary:
    if isinstance(incident, IncidentSummary):
        return incident
    if isinstance(incident, dict):
        return IncidentSummary.from_dict(incident)
    return IncidentSummary()


def build_report_incident_context(
    *,
    current_incident_id: object,
    current_incident_state: object,
    current_incident: IncidentSummary | dict[str, object] | None,
    recent_incidents: list[IncidentSummary] | list[dict[str, object]] | None,
    incident_limit: int,
) -> dict[str, object]:
    incident_payload = _incident_summary(current_incident)
    summaries = [_incident_summary(incident) for incident in (recent_incidents if isinstance(recent_incidents, list) else [])]
    incidents = [summary.to_dict() for summary in summaries[-max(1, incident_limit):]]
    context = {
        'current_incident_id': current_incident_id or '',
        'current_incident_state': current_incident_state or '',
        'current_incident_owner': incident_payload.owner,
        'current_incident_acknowledged': incident_payload.acknowledged,
        'current_incident_notes_count': incident_payload.notes_count,
        'recent_incidents': incidents,
    }
    context['operator_attention_items'] = report_attention_items(context)
    context['operator_attention_needed'] = bool(context['operator_attention_items'])
    context['operator_attention_count'] = len(context['operator_attention_items'])
    return context


def build_incident_index_entry(
    *,
    run_ts: str,
    incident_id: str,
    incident_dir: str,
    summary: str,
    state_payload: dict[str, object] | None,
    workflow_payload: dict[str, object] | None,
    run_state: dict[str, object] | None,
    active: str,
    main_pid: str,
    listeners: str,
    pre_repair_backup_result: str,
    rollback_occurred: bool,
    rollback_summary_archive_file: str,
    rollback_candidate_used: str,
    rollback_reason: str,
    last_recovery_strategy: str,
    last_recovery_path: str,
    codex_trigger_result: str,
    opencode_fallback_trigger_result: str,
) -> dict[str, object]:
    state = state_payload if isinstance(state_payload, dict) else {}
    workflow = workflow_payload if isinstance(workflow_payload, dict) else {}
    current_run_state = RunStateSnapshot.from_dict(run_state)
    notes = workflow.get('notes', []) if isinstance(workflow.get('notes', []), list) else []
    latest_note = notes[-1] if notes else {}
    return {
        'incident_id': incident_id,
        'time': run_ts,
        'summary': summary,
        'state': str(state.get('state', 'unknown') or 'unknown'),
        'created_at': str(state.get('created_at', '') or ''),
        'resolved_at': str(state.get('resolved_at', '') or ''),
        'resolution_summary': str(state.get('resolution_summary', '') or ''),
        'health_level': current_run_state.health_level,
        'active': active,
        'main_pid': main_pid,
        'listeners': listeners,
        'incident_dir': incident_dir,
        'pre_repair_backup_result': pre_repair_backup_result,
        'rollback_occurred': rollback_occurred,
        'rollback_summary_archive_file': rollback_summary_archive_file,
        'rollback_candidate_used': rollback_candidate_used,
        'rollback_reason': rollback_reason,
        'conversation_status': current_run_state.conversation_status,
        'last_recovery_strategy': last_recovery_strategy,
        'last_recovery_path': last_recovery_path,
        'codex_trigger_result': codex_trigger_result,
        'opencode_fallback_trigger_result': opencode_fallback_trigger_result,
        'owner': str(workflow.get('owner', '') or ''),
        'acknowledged': bool(workflow.get('acknowledged', False)),
        'acknowledged_by': str(workflow.get('acknowledged_by', '') or ''),
        'acknowledged_at': str(workflow.get('acknowledged_at', '') or ''),
        'notes_count': len(notes),
        'latest_note': str(latest_note.get('message', '') or ''),
        'latest_note_by': str(latest_note.get('by', '') or ''),
        'latest_note_at': str(latest_note.get('time', '') or ''),
    }
