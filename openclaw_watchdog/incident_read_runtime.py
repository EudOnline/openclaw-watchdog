from __future__ import annotations

import json
from pathlib import Path

from openclaw_watchdog.config import parse_env_file


def incident_bool(value: object) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def incident_state_file(engine, incident_dir: Path) -> Path:
    return incident_dir / 'incident-state.json'


def read_json_dict(path: Path) -> dict[str, object]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_incident_state_payload(engine, incident_dir: Path) -> dict[str, object]:
    return read_json_dict(incident_state_file(engine, incident_dir))


def read_incident_operator_summary_payload(engine, incident_dir: Path) -> dict[str, object]:
    return parse_env_file(incident_dir / 'operator-summary.txt')


def incident_operator_workflow_file(engine, incident_dir: Path) -> Path:
    return incident_dir / 'operator-workflow.json'


def read_incident_operator_workflow_payload(engine, incident_dir: Path) -> dict[str, object]:
    payload = read_json_dict(incident_operator_workflow_file(engine, incident_dir))
    notes = payload.get('notes', []) if isinstance(payload, dict) else []
    if not isinstance(notes, list):
        notes = []
    clean_notes: list[dict[str, object]] = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        clean_notes.append(
            {
                'time': str(note.get('time', '') or ''),
                'by': str(note.get('by', '') or ''),
                'message': str(note.get('message', '') or ''),
            }
        )
    events = payload.get('events', []) if isinstance(payload, dict) else []
    if not isinstance(events, list):
        events = []
    clean_events: list[dict[str, object]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        clean_events.append(
            {
                'time': str(event.get('time', '') or ''),
                'type': str(event.get('type', '') or ''),
                'by': str(event.get('by', '') or ''),
                'owner': str(event.get('owner', '') or ''),
                'acknowledged': bool(event.get('acknowledged', False)),
                'message': str(event.get('message', '') or ''),
                'summary': str(event.get('summary', '') or ''),
            }
        )
    return {
        'incident_id': str(payload.get('incident_id', incident_dir.name) or incident_dir.name),
        'owner': str(payload.get('owner', '') or ''),
        'acknowledged': bool(payload.get('acknowledged', False)),
        'acknowledged_by': str(payload.get('acknowledged_by', '') or ''),
        'acknowledged_at': str(payload.get('acknowledged_at', '') or ''),
        'updated_at': str(payload.get('updated_at', '') or ''),
        'notes': clean_notes,
        'events': clean_events,
    }


def read_incident_index(engine, limit: int | None = None) -> list[dict[str, object]]:
    index_file = engine.config.watchdog_incident_index_file
    if not index_file.exists():
        return []
    try:
        data = json.loads(index_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    items = [item for item in data if isinstance(item, dict)]
    if limit is not None and limit > 0:
        return items[-limit:]
    return items


def incident_attention_items(snapshot: dict[str, object]) -> list[str]:
    if str(snapshot.get('state', '') or '') != 'open':
        return []
    items: list[str] = []
    if not str(snapshot.get('owner', '') or '').strip():
        items.append('unowned')
    if not bool(snapshot.get('acknowledged', False)):
        items.append('unacknowledged')
    if int(snapshot.get('notes_count', 0) or 0) <= 0:
        items.append('no-notes')
    return items


def incident_snapshot(engine, incident_dir: Path) -> dict[str, object]:
    incident_id = incident_dir.name
    state_payload = read_incident_state_payload(engine, incident_dir)
    operator_payload = read_incident_operator_summary_payload(engine, incident_dir)
    workflow_payload = read_incident_operator_workflow_payload(engine, incident_dir)
    index_payload = next(
        (
            item
            for item in reversed(read_incident_index(engine))
            if str(item.get('incident_id', '')) == incident_id
        ),
        {},
    )
    notes = workflow_payload.get('notes', []) if isinstance(workflow_payload.get('notes', []), list) else []
    events = workflow_payload.get('events', []) if isinstance(workflow_payload.get('events', []), list) else []
    latest_note = notes[-1] if notes else {}
    latest_event = events[-1] if events else {}
    artifacts = sorted(path.name for path in incident_dir.iterdir() if path.is_file()) if incident_dir.exists() else []
    snapshot = {
        'incident_id': incident_id,
        'incident_dir': str(incident_dir),
        'state': str(state_payload.get('state', index_payload.get('state', 'unknown')) or 'unknown'),
        'created_at': str(state_payload.get('created_at', index_payload.get('created_at', '')) or ''),
        'resolved_at': str(state_payload.get('resolved_at', index_payload.get('resolved_at', '')) or ''),
        'summary': str(index_payload.get('summary') or state_payload.get('summary') or operator_payload.get('summary') or ''),
        'opened_summary': str(state_payload.get('opened_summary', index_payload.get('summary') or state_payload.get('summary') or operator_payload.get('summary') or '')),
        'resolution_summary': str(state_payload.get('resolution_summary', index_payload.get('resolution_summary', '')) or ''),
        'time': str(index_payload.get('time') or operator_payload.get('time') or ''),
        'health_level': str(index_payload.get('health_level') or operator_payload.get('health_level') or 'unknown'),
        'active': str(index_payload.get('active') or operator_payload.get('active') or 'unknown'),
        'main_pid': str(index_payload.get('main_pid') or operator_payload.get('main_pid') or '0'),
        'listeners': str(index_payload.get('listeners') or operator_payload.get('listeners') or 'none'),
        'pre_repair_backup_result': str(index_payload.get('pre_repair_backup_result') or operator_payload.get('pre_repair_backup_result') or 'not-run'),
        'rollback_occurred': incident_bool(index_payload.get('rollback_occurred', operator_payload.get('rollback_occurred', False))),
        'rollback_summary_archive_file': str(index_payload.get('rollback_summary_archive_file') or operator_payload.get('rollback_summary_archive_file') or ''),
        'owner': str(workflow_payload.get('owner') or index_payload.get('owner') or ''),
        'acknowledged': incident_bool(workflow_payload.get('acknowledged', index_payload.get('acknowledged', False))),
        'acknowledged_by': str(workflow_payload.get('acknowledged_by') or index_payload.get('acknowledged_by') or ''),
        'acknowledged_at': str(workflow_payload.get('acknowledged_at') or index_payload.get('acknowledged_at') or ''),
        'notes_count': len(notes) if notes else int(index_payload.get('notes_count', 0) or 0),
        'latest_note': str(latest_note.get('message') or index_payload.get('latest_note') or ''),
        'latest_note_by': str(latest_note.get('by') or index_payload.get('latest_note_by') or ''),
        'latest_note_at': str(latest_note.get('time') or index_payload.get('latest_note_at') or ''),
        'events_count': len(events),
        'latest_event_type': str(latest_event.get('type') or ''),
        'latest_event_at': str(latest_event.get('time') or ''),
        'notes': notes,
        'events': events,
        'artifacts': artifacts,
    }
    attention_items = incident_attention_items(snapshot)
    snapshot['attention_items'] = attention_items
    snapshot['attention_needed'] = bool(attention_items)
    snapshot['attention_count'] = len(attention_items)
    snapshot['attention_summary'] = ','.join(attention_items)
    return snapshot


def list_incident_snapshots(
    engine,
    *,
    limit: int | None = None,
    state: str = 'all',
    owner: str = '',
    acknowledged: bool | None = None,
    has_notes: bool | None = None,
    attention_needed: bool | None = None,
) -> list[dict[str, object]]:
    if not engine.config.watchdog_incidents_dir.exists():
        return []
    wanted_state = state.strip().lower() if state else 'all'
    wanted_owner = owner.strip().lower() if owner else ''
    snapshots: list[dict[str, object]] = []
    incident_dirs = sorted((path for path in engine.config.watchdog_incidents_dir.iterdir() if path.is_dir()), reverse=True)
    for incident_dir in incident_dirs:
        snapshot = incident_snapshot(engine, incident_dir)
        snapshot_state = str(snapshot.get('state', 'unknown')).lower()
        if wanted_state != 'all' and snapshot_state != wanted_state:
            continue
        snapshot_owner = str(snapshot.get('owner', '') or '').strip().lower()
        if wanted_owner and snapshot_owner != wanted_owner:
            continue
        if acknowledged is not None and bool(snapshot.get('acknowledged', False)) != acknowledged:
            continue
        if has_notes is not None and (int(snapshot.get('notes_count', 0) or 0) > 0) != has_notes:
            continue
        if attention_needed is not None and bool(snapshot.get('attention_needed', False)) != attention_needed:
            continue
        snapshots.append(snapshot)
        if limit is not None and limit > 0 and len(snapshots) >= limit:
            break
    return snapshots


def incident_detail_payload(engine, incident_id: str) -> dict[str, object]:
    incident_dir = engine.config.watchdog_incidents_dir / incident_id
    if not incident_dir.exists() or not incident_dir.is_dir():
        return {}
    return incident_snapshot(engine, incident_dir)


def incident_timeline_payload(engine, incident_id: str, *, limit: int | None = None) -> dict[str, object]:
    detail = incident_detail_payload(engine, incident_id)
    if not detail:
        return {}
    events: list[dict[str, object]] = []
    created_at = str(detail.get('created_at', '') or '')
    if created_at:
        opened_summary = str(detail.get('opened_summary', '') or detail.get('summary', '') or 'incident opened')
        events.append(
            {
                'time': created_at,
                'type': 'opened',
                'by': 'watchdog',
                'summary': opened_summary,
                'message': opened_summary,
            }
        )
    workflow_events = detail.get('events', []) if isinstance(detail.get('events', []), list) else []
    for event in workflow_events:
        if not isinstance(event, dict):
            continue
        events.append(
            {
                'time': str(event.get('time', '') or ''),
                'type': str(event.get('type', '') or 'unknown'),
                'by': str(event.get('by', '') or ''),
                'summary': str(event.get('summary', '') or ''),
                'message': str(event.get('message', '') or ''),
                'owner': str(event.get('owner', '') or ''),
                'acknowledged': bool(event.get('acknowledged', False)),
            }
        )
    resolved_at = str(detail.get('resolved_at', '') or '')
    if resolved_at:
        events.append(
            {
                'time': resolved_at,
                'type': 'resolved',
                'by': 'watchdog',
                'summary': str(detail.get('resolution_summary', '') or 'incident resolved'),
                'message': str(detail.get('resolution_summary', '') or ''),
            }
        )
    event_order = {
        'opened': 0,
        'owner-assigned': 1,
        'owner-unassigned': 2,
        'acknowledged': 3,
        'unacknowledged': 4,
        'note': 5,
        'resolved': 6,
    }
    events = sorted(
        events,
        key=lambda item: (
            str(item.get('time', '') or ''),
            event_order.get(str(item.get('type', '') or 'unknown'), 99),
        ),
    )
    if limit is not None and limit > 0:
        events = events[-limit:]
    return {
        'incident_id': incident_id,
        'state': detail.get('state', 'unknown'),
        'event_count': len(events),
        'events': events,
        'notes_count': detail.get('notes_count', 0),
        'owner': detail.get('owner', ''),
        'acknowledged': detail.get('acknowledged', False),
    }


def current_incident_payload(engine) -> dict[str, object]:
    if not engine.current_incident_marker.exists():
        return {}
    incident_id = engine.current_incident_marker.read_text(encoding='utf-8').strip()
    if not incident_id:
        return {}
    return incident_detail_payload(engine, incident_id)


def incident_queue_payload(engine, *, limit: int | None = None) -> dict[str, object]:
    incidents = list_incident_snapshots(engine, state='open')
    incidents = sorted(
        incidents,
        key=lambda item: (
            0 if bool(item.get('attention_needed', False)) else 1,
            -int(item.get('attention_count', 0) or 0),
            str(item.get('time', '') or ''),
        ),
        reverse=False,
    )
    visible = incidents[:limit] if limit is not None and limit > 0 else incidents
    summary = {
        'open_total': len(incidents),
        'attention_total': sum(1 for item in incidents if bool(item.get('attention_needed', False))),
        'handled_total': sum(1 for item in incidents if not bool(item.get('attention_needed', False))),
        'owned_total': sum(1 for item in incidents if str(item.get('owner', '') or '').strip()),
        'acknowledged_total': sum(1 for item in incidents if bool(item.get('acknowledged', False))),
        'with_notes_total': sum(1 for item in incidents if int(item.get('notes_count', 0) or 0) > 0),
    }
    return {
        'summary': summary,
        'incidents': visible,
    }
