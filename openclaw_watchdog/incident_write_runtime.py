from __future__ import annotations

import json
from pathlib import Path

from openclaw_watchdog import incident_context as incident_context_ops
from openclaw_watchdog import incident_read_runtime


def incident_operator_summary(engine, *, summary: str, active: str, main_pid: str, listeners: str) -> str:
    run_state = engine.read_run_state()
    lines = [
        f'incident_id={engine.ctx.incident_id}',
        f'time={engine.ctx.run_ts}',
        f'summary={summary}',
        f"health_level={run_state.get('health_level', 'unknown')}",
        f"conversation_status={run_state.get('conversation_status', 'down')}",
        f'active={active}',
        f'main_pid={main_pid}',
        f'listeners={listeners}',
        f'pre_repair_backup_result={engine.ctx.pre_repair_backup_result}',
        f"rollback_occurred={'true' if engine.ctx.rollback_occurred else 'false'}",
        f"rollback_summary_archive_file={engine.ctx.rollback_summary_archive_file or 'none'}",
        f"rollback_candidate_used={engine.ctx.rollback_candidate_used or 'none'}",
        f"rollback_reason={engine.ctx.rollback_reason or 'none'}",
        f'last_recovery_strategy={engine.ctx.last_recovery_strategy}',
        f'last_recovery_path={engine.recovery_path_text()}',
    ]
    return '\n'.join(lines) + '\n'


def incident_index_entry(
    engine,
    *,
    summary: str,
    active: str,
    main_pid: str,
    listeners: str,
    health_level: str | None = None,
    pre_repair_backup_result: str | None = None,
    rollback_occurred: bool | None = None,
    rollback_summary_archive_file: str | None = None,
    incident_id: str | None = None,
    incident_dir: Path | None = None,
) -> dict[str, object]:
    target_incident_id = incident_id or engine.ctx.incident_id
    target_incident_dir = incident_dir or engine.ctx.incident_dir
    run_state = engine.read_run_state()
    return incident_context_ops.build_incident_index_entry(
        run_ts=engine.ctx.run_ts,
        incident_id=target_incident_id,
        incident_dir=str(target_incident_dir) if target_incident_dir else '',
        summary=summary,
        state_payload=incident_read_runtime.read_incident_state_payload(engine, target_incident_dir) if target_incident_dir is not None else {},
        workflow_payload=incident_read_runtime.read_incident_operator_workflow_payload(engine, target_incident_dir) if target_incident_dir is not None else {},
        run_state={
            **run_state,
            'health_level': health_level or str(run_state.get('health_level', 'unknown') or 'unknown'),
        },
        active=active,
        main_pid=main_pid,
        listeners=listeners,
        pre_repair_backup_result=pre_repair_backup_result or engine.ctx.pre_repair_backup_result,
        rollback_occurred=engine.ctx.rollback_occurred if rollback_occurred is None else rollback_occurred,
        rollback_summary_archive_file=rollback_summary_archive_file if rollback_summary_archive_file is not None else engine.ctx.rollback_summary_archive_file,
        rollback_candidate_used=engine.ctx.rollback_candidate_used,
        rollback_reason=engine.ctx.rollback_reason,
        last_recovery_strategy=engine.ctx.last_recovery_strategy,
        last_recovery_path=engine.recovery_path_text(),
    )


def update_incident_index(
    engine,
    *,
    summary: str,
    active: str,
    main_pid: str,
    listeners: str,
    health_level: str | None = None,
    pre_repair_backup_result: str | None = None,
    rollback_occurred: bool | None = None,
    rollback_summary_archive_file: str | None = None,
    incident_id: str | None = None,
    incident_dir: Path | None = None,
) -> None:
    index_file = engine.config.watchdog_incident_index_file
    items: list[dict[str, object]] = []
    if index_file.exists():
        try:
            data = json.loads(index_file.read_text(encoding='utf-8'))
            if isinstance(data, list):
                items = [item for item in data if isinstance(item, dict)]
        except json.JSONDecodeError:
            items = []
    target_incident_id = incident_id or engine.ctx.incident_id
    entry = incident_index_entry(
        engine,
        summary=summary,
        active=active,
        main_pid=main_pid,
        listeners=listeners,
        health_level=health_level,
        pre_repair_backup_result=pre_repair_backup_result,
        rollback_occurred=rollback_occurred,
        rollback_summary_archive_file=rollback_summary_archive_file,
        incident_id=target_incident_id,
        incident_dir=incident_dir,
    )
    items = [item for item in items if str(item.get('incident_id', '')) != target_incident_id]
    items.append(entry)
    items = sorted(items, key=lambda item: str(item.get('incident_id', '')))
    keep = max(1, engine.config.watchdog_incident_index_limit)
    index_file.write_text(json.dumps(items[-keep:], ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def refresh_current_incident_index(engine, *, summary: str | None = None, health_level: str | None = None) -> None:
    if engine.ctx.incident_dir is None:
        return
    operator_payload = incident_read_runtime.read_incident_operator_summary_payload(engine, engine.ctx.incident_dir)
    existing_index_payload = next(
        (
            item
            for item in reversed(incident_read_runtime.read_incident_index(engine))
            if str(item.get('incident_id', '')) == engine.ctx.incident_id
        ),
        {},
    )
    current_summary = summary or str(operator_payload.get('summary', existing_index_payload.get('summary', '')) or '')
    update_incident_index(
        engine,
        summary=current_summary,
        active=str(operator_payload.get('active', existing_index_payload.get('active', 'unknown')) or 'unknown'),
        main_pid=str(operator_payload.get('main_pid', existing_index_payload.get('main_pid', '0')) or '0'),
        listeners=str(operator_payload.get('listeners', existing_index_payload.get('listeners', 'none')) or 'none'),
        health_level=health_level,
        pre_repair_backup_result=str(existing_index_payload.get('pre_repair_backup_result', engine.ctx.pre_repair_backup_result) or engine.ctx.pre_repair_backup_result),
        rollback_occurred=bool(existing_index_payload.get('rollback_occurred', engine.ctx.rollback_occurred)),
        rollback_summary_archive_file=str(existing_index_payload.get('rollback_summary_archive_file', engine.ctx.rollback_summary_archive_file) or engine.ctx.rollback_summary_archive_file),
    )


def write_incident_operator_summary(engine, *, summary: str, active: str, main_pid: str, listeners: str) -> None:
    if engine.ctx.incident_dir is None:
        return
    engine.ctx.incident_dir.mkdir(parents=True, exist_ok=True)
    (engine.ctx.incident_dir / 'operator-summary.txt').write_text(
        incident_operator_summary(engine, summary=summary, active=active, main_pid=main_pid, listeners=listeners),
        encoding='utf-8',
    )
    update_incident_index(engine, summary=summary, active=active, main_pid=main_pid, listeners=listeners)


def update_incident_state(engine, state: str, summary: str, *, resolved: bool = False) -> None:
    if engine.ctx.incident_dir is None:
        return
    engine.ctx.incident_dir.mkdir(parents=True, exist_ok=True)
    state_file = incident_read_runtime.incident_state_file(engine, engine.ctx.incident_dir)
    payload: dict[str, object] = {
        'incident_id': engine.ctx.incident_id,
        'state': state,
        'summary': summary,
    }
    if state_file.exists():
        try:
            existing = json.loads(state_file.read_text(encoding='utf-8'))
            if isinstance(existing, dict):
                payload = {**existing, **payload}
        except json.JSONDecodeError:
            pass
    payload.setdefault('created_at', engine.now_iso())
    if state == 'open' and summary != 'incident created':
        if not str(payload.get('opened_summary', '') or '') or str(payload.get('opened_summary', '') or '') == 'incident created':
            payload['opened_summary'] = summary
    elif not str(payload.get('opened_summary', '') or ''):
        payload['opened_summary'] = summary
    if resolved:
        payload['resolved_at'] = engine.now_iso()
        payload['resolution_summary'] = summary
    state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def load_existing_incident_context(engine, incident_id: str) -> bool:
    incident_id = incident_id.strip()
    if not incident_id:
        return False
    incident_dir = engine.config.watchdog_incidents_dir / incident_id
    if not incident_dir.exists() or not incident_dir.is_dir():
        return False
    engine.ctx.incident_id = incident_id
    engine.ctx.incident_dir = incident_dir
    engine.current_incident_marker.write_text(f'{incident_id}\n', encoding='utf-8')
    return True


def attach_current_incident_if_any(engine) -> bool:
    if engine.ctx.incident_dir is not None and engine.ctx.incident_id:
        return True
    if not engine.current_incident_marker.exists():
        return False
    incident_id = engine.current_incident_marker.read_text(encoding='utf-8').strip()
    return load_existing_incident_context(engine, incident_id)


def reset_incident_state(engine) -> None:
    engine.current_incident_marker.unlink(missing_ok=True)
    engine.ctx.incident_id = ''
    engine.ctx.incident_dir = None


def _compact_text(text: str, limit: int = 72) -> str:
    text = str(text or '').strip().replace('\n', ' ')
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + '…'


def refresh_incident_index_for(engine, incident_id: str, *, summary: str | None = None, health_level: str | None = None) -> None:
    incident_id = incident_id.strip()
    if not incident_id:
        return
    incident_dir = engine.config.watchdog_incidents_dir / incident_id
    if not incident_dir.exists() or not incident_dir.is_dir():
        return
    operator_payload = incident_read_runtime.read_incident_operator_summary_payload(engine, incident_dir)
    state_payload = incident_read_runtime.read_incident_state_payload(engine, incident_dir)
    existing_index_payload = next(
        (
            item
            for item in reversed(incident_read_runtime.read_incident_index(engine))
            if str(item.get('incident_id', '')) == incident_id
        ),
        {},
    )
    current_summary = summary or str(existing_index_payload.get('summary') or state_payload.get('summary') or operator_payload.get('summary') or '')
    current_health_level = health_level or str(
        existing_index_payload.get('health_level')
        or operator_payload.get('health_level')
        or engine.read_run_state().get('health_level', 'unknown')
    )
    update_incident_index(
        engine,
        summary=current_summary,
        active=str(operator_payload.get('active', existing_index_payload.get('active', 'unknown')) or 'unknown'),
        main_pid=str(operator_payload.get('main_pid', existing_index_payload.get('main_pid', '0')) or '0'),
        listeners=str(operator_payload.get('listeners', existing_index_payload.get('listeners', 'none')) or 'none'),
        health_level=current_health_level,
        pre_repair_backup_result=str(existing_index_payload.get('pre_repair_backup_result', engine.ctx.pre_repair_backup_result) or engine.ctx.pre_repair_backup_result),
        rollback_occurred=bool(existing_index_payload.get('rollback_occurred', engine.ctx.rollback_occurred)),
        rollback_summary_archive_file=str(existing_index_payload.get('rollback_summary_archive_file', engine.ctx.rollback_summary_archive_file) or engine.ctx.rollback_summary_archive_file),
        incident_id=incident_id,
        incident_dir=incident_dir,
    )


def update_incident_operator_workflow(
    engine,
    incident_id: str,
    *,
    owner: str | None = None,
    acknowledged: bool | None = None,
    acknowledged_by: str | None = None,
    note_by: str | None = None,
    note_message: str | None = None,
    clear_owner: bool = False,
    clear_ack: bool = False,
) -> dict[str, object]:
    incident_id = incident_id.strip()
    if not incident_id:
        return {}
    incident_dir = engine.config.watchdog_incidents_dir / incident_id
    if not incident_dir.exists() or not incident_dir.is_dir():
        return {}
    payload = incident_read_runtime.read_incident_operator_workflow_payload(engine, incident_dir)
    notes = payload.get('notes', []) if isinstance(payload.get('notes', []), list) else []
    clean_notes = [note for note in notes if isinstance(note, dict)]
    events = payload.get('events', []) if isinstance(payload.get('events', []), list) else []
    clean_events = [event for event in events if isinstance(event, dict)]
    now_iso = engine.now_iso()
    current_owner = str(payload.get('owner', '') or '')
    current_ack = bool(payload.get('acknowledged', False))
    current_ack_by = str(payload.get('acknowledged_by', '') or '')
    if clear_owner and current_owner:
        payload['owner'] = ''
        clean_events.append({'time': now_iso, 'type': 'owner-unassigned', 'by': '', 'owner': '', 'acknowledged': current_ack, 'message': '', 'summary': 'owner cleared'})
    elif owner is not None:
        next_owner = owner.strip()
        if next_owner != current_owner:
            payload['owner'] = next_owner
            clean_events.append({'time': now_iso, 'type': 'owner-assigned', 'by': next_owner, 'owner': next_owner, 'acknowledged': current_ack, 'message': '', 'summary': f"owner -> {next_owner or 'none'}"})
    if clear_ack and current_ack:
        payload['acknowledged'] = False
        payload['acknowledged_at'] = ''
        payload['acknowledged_by'] = ''
        clean_events.append({'time': now_iso, 'type': 'unacknowledged', 'by': '', 'owner': str(payload.get('owner', '') or ''), 'acknowledged': False, 'message': '', 'summary': 'acknowledgement cleared'})
    elif acknowledged is not None:
        next_ack = bool(acknowledged)
        payload['acknowledged'] = next_ack
        if next_ack:
            ack_by = (acknowledged_by or payload.get('acknowledged_by') or '').strip()
            payload['acknowledged_at'] = now_iso
            payload['acknowledged_by'] = ack_by
            if not current_ack or ack_by != current_ack_by:
                clean_events.append({'time': now_iso, 'type': 'acknowledged', 'by': ack_by, 'owner': str(payload.get('owner', '') or ''), 'acknowledged': True, 'message': '', 'summary': f"acknowledged by {ack_by or 'unknown'}"})
    if note_message is not None and note_message.strip():
        note_by_value = (note_by or acknowledged_by or '').strip()
        note_text = note_message.strip()
        clean_notes.append({'time': now_iso, 'by': note_by_value, 'message': note_text})
        clean_events.append({'time': now_iso, 'type': 'note', 'by': note_by_value, 'owner': str(payload.get('owner', '') or ''), 'acknowledged': bool(payload.get('acknowledged', False)), 'message': note_text, 'summary': _compact_text(note_text)})
    payload['incident_id'] = incident_id
    payload['notes'] = clean_notes
    payload['events'] = clean_events
    payload['updated_at'] = now_iso
    incident_read_runtime.incident_operator_workflow_file(engine, incident_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    refresh_incident_index_for(engine, incident_id)
    return incident_read_runtime.incident_detail_payload(engine, incident_id)


def set_incident_owner(engine, incident_id: str, owner: str) -> dict[str, object]:
    return update_incident_operator_workflow(engine, incident_id, owner=owner)


def clear_incident_owner(engine, incident_id: str) -> dict[str, object]:
    return update_incident_operator_workflow(engine, incident_id, clear_owner=True)


def acknowledge_incident(engine, incident_id: str, *, acknowledged_by: str, note: str = '') -> dict[str, object]:
    return update_incident_operator_workflow(
        engine,
        incident_id,
        acknowledged=True,
        acknowledged_by=acknowledged_by,
        note_by=acknowledged_by,
        note_message=note,
    )


def clear_incident_acknowledgement(engine, incident_id: str) -> dict[str, object]:
    return update_incident_operator_workflow(engine, incident_id, clear_ack=True)


def add_incident_note(engine, incident_id: str, *, note_by: str, message: str) -> dict[str, object]:
    return update_incident_operator_workflow(engine, incident_id, note_by=note_by, note_message=message)
