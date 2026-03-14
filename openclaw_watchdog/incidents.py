from __future__ import annotations

from pathlib import Path

from openclaw_watchdog import incident_read_runtime
from openclaw_watchdog import incident_write_runtime


def incident_attention_items(snapshot: dict[str, object]) -> list[str]:
    return incident_read_runtime.incident_attention_items(snapshot)


def incident_snapshot(engine, incident_dir: Path) -> dict[str, object]:
    return incident_read_runtime.incident_snapshot(engine, incident_dir)


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
    return incident_read_runtime.list_incident_snapshots(
        engine,
        limit=limit,
        state=state,
        owner=owner,
        acknowledged=acknowledged,
        has_notes=has_notes,
        attention_needed=attention_needed,
    )


def incident_detail_payload(engine, incident_id: str) -> dict[str, object]:
    return incident_read_runtime.incident_detail_payload(engine, incident_id)


def incident_timeline_payload(engine, incident_id: str, *, limit: int | None = None) -> dict[str, object]:
    return incident_read_runtime.incident_timeline_payload(engine, incident_id, limit=limit)


def current_incident_payload(engine) -> dict[str, object]:
    return incident_read_runtime.current_incident_payload(engine)


def incident_queue_payload(engine, *, limit: int | None = None) -> dict[str, object]:
    return incident_read_runtime.incident_queue_payload(engine, limit=limit)


def refresh_incident_index_for(engine, incident_id: str, *, summary: str | None = None, health_level: str | None = None) -> None:
    incident_write_runtime.refresh_incident_index_for(engine, incident_id, summary=summary, health_level=health_level)


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
    return incident_write_runtime.update_incident_operator_workflow(
        engine,
        incident_id,
        owner=owner,
        acknowledged=acknowledged,
        acknowledged_by=acknowledged_by,
        note_by=note_by,
        note_message=note_message,
        clear_owner=clear_owner,
        clear_ack=clear_ack,
    )


def set_incident_owner(engine, incident_id: str, owner: str) -> dict[str, object]:
    return incident_write_runtime.set_incident_owner(engine, incident_id, owner)


def clear_incident_owner(engine, incident_id: str) -> dict[str, object]:
    return incident_write_runtime.clear_incident_owner(engine, incident_id)


def acknowledge_incident(engine, incident_id: str, *, acknowledged_by: str, note: str = '') -> dict[str, object]:
    return incident_write_runtime.acknowledge_incident(engine, incident_id, acknowledged_by=acknowledged_by, note=note)


def clear_incident_acknowledgement(engine, incident_id: str) -> dict[str, object]:
    return incident_write_runtime.clear_incident_acknowledgement(engine, incident_id)


def add_incident_note(engine, incident_id: str, *, note_by: str, message: str) -> dict[str, object]:
    return incident_write_runtime.add_incident_note(engine, incident_id, note_by=note_by, message=message)
