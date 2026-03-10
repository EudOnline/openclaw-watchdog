from __future__ import annotations

import json
from pathlib import Path


def _compact_text(text: str, limit: int = 72) -> str:
    text = str(text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def incident_attention_items(snapshot: dict[str, object]) -> list[str]:
    if str(snapshot.get("state", "") or "") != "open":
        return []
    items: list[str] = []
    if not str(snapshot.get("owner", "") or "").strip():
        items.append("unowned")
    if not bool(snapshot.get("acknowledged", False)):
        items.append("unacknowledged")
    if int(snapshot.get("notes_count", 0) or 0) <= 0:
        items.append("no-notes")
    return items


def incident_snapshot(engine, incident_dir: Path) -> dict[str, object]:
    incident_id = incident_dir.name
    state_payload = engine.read_incident_state_payload(incident_dir)
    operator_payload = engine.read_incident_operator_summary_payload(incident_dir)
    workflow_payload = engine.read_incident_operator_workflow_payload(incident_dir)
    index_payload = next(
        (
            item
            for item in reversed(engine.read_incident_index())
            if str(item.get("incident_id", "")) == incident_id
        ),
        {},
    )
    notes = workflow_payload.get("notes", []) if isinstance(workflow_payload.get("notes", []), list) else []
    events = workflow_payload.get("events", []) if isinstance(workflow_payload.get("events", []), list) else []
    latest_note = notes[-1] if notes else {}
    latest_event = events[-1] if events else {}
    artifacts = sorted(path.name for path in incident_dir.iterdir() if path.is_file()) if incident_dir.exists() else []
    snapshot = {
        "incident_id": incident_id,
        "incident_dir": str(incident_dir),
        "state": str(state_payload.get("state", index_payload.get("state", "unknown")) or "unknown"),
        "created_at": str(state_payload.get("created_at", index_payload.get("created_at", "")) or ""),
        "resolved_at": str(state_payload.get("resolved_at", index_payload.get("resolved_at", "")) or ""),
        "summary": str(index_payload.get("summary") or state_payload.get("summary") or operator_payload.get("summary") or ""),
        "opened_summary": str(state_payload.get("opened_summary", index_payload.get("summary") or state_payload.get("summary") or operator_payload.get("summary") or "")),
        "resolution_summary": str(state_payload.get("resolution_summary", index_payload.get("resolution_summary", "")) or ""),
        "time": str(index_payload.get("time") or operator_payload.get("time") or ""),
        "health_level": str(index_payload.get("health_level") or operator_payload.get("health_level") or "unknown"),
        "active": str(index_payload.get("active") or operator_payload.get("active") or "unknown"),
        "main_pid": str(index_payload.get("main_pid") or operator_payload.get("main_pid") or "0"),
        "listeners": str(index_payload.get("listeners") or operator_payload.get("listeners") or "none"),
        "pre_repair_backup_result": str(index_payload.get("pre_repair_backup_result") or operator_payload.get("pre_repair_backup_result") or "not-run"),
        "rollback_occurred": engine._incident_bool(index_payload.get("rollback_occurred", operator_payload.get("rollback_occurred", False))),
        "rollback_summary_archive_file": str(index_payload.get("rollback_summary_archive_file") or operator_payload.get("rollback_summary_archive_file") or ""),
        "codex_trigger_result": str(index_payload.get("codex_trigger_result") or operator_payload.get("codex_trigger_result") or "not-run"),
        "opencode_fallback_trigger_result": str(index_payload.get("opencode_fallback_trigger_result") or operator_payload.get("opencode_fallback_trigger_result") or "not-run"),
        "owner": str(workflow_payload.get("owner") or index_payload.get("owner") or ""),
        "acknowledged": engine._incident_bool(workflow_payload.get("acknowledged", index_payload.get("acknowledged", False))),
        "acknowledged_by": str(workflow_payload.get("acknowledged_by") or index_payload.get("acknowledged_by") or ""),
        "acknowledged_at": str(workflow_payload.get("acknowledged_at") or index_payload.get("acknowledged_at") or ""),
        "notes_count": len(notes) if notes else int(index_payload.get("notes_count", 0) or 0),
        "latest_note": str(latest_note.get("message") or index_payload.get("latest_note") or ""),
        "latest_note_by": str(latest_note.get("by") or index_payload.get("latest_note_by") or ""),
        "latest_note_at": str(latest_note.get("time") or index_payload.get("latest_note_at") or ""),
        "events_count": len(events),
        "latest_event_type": str(latest_event.get("type") or ""),
        "latest_event_at": str(latest_event.get("time") or ""),
        "notes": notes,
        "events": events,
        "artifacts": artifacts,
    }
    attention_items = incident_attention_items(snapshot)
    snapshot["attention_items"] = attention_items
    snapshot["attention_needed"] = bool(attention_items)
    snapshot["attention_count"] = len(attention_items)
    snapshot["attention_summary"] = ",".join(attention_items)
    return snapshot


def list_incident_snapshots(
    engine,
    *,
    limit: int | None = None,
    state: str = "all",
    owner: str = "",
    acknowledged: bool | None = None,
    has_notes: bool | None = None,
    attention_needed: bool | None = None,
) -> list[dict[str, object]]:
    if not engine.config.watchdog_incidents_dir.exists():
        return []
    wanted_state = state.strip().lower() if state else "all"
    wanted_owner = owner.strip().lower() if owner else ""
    snapshots: list[dict[str, object]] = []
    incident_dirs = sorted((path for path in engine.config.watchdog_incidents_dir.iterdir() if path.is_dir()), reverse=True)
    for incident_dir in incident_dirs:
        snapshot = incident_snapshot(engine, incident_dir)
        snapshot_state = str(snapshot.get("state", "unknown")).lower()
        if wanted_state != "all" and snapshot_state != wanted_state:
            continue
        snapshot_owner = str(snapshot.get("owner", "") or "").strip().lower()
        if wanted_owner and snapshot_owner != wanted_owner:
            continue
        if acknowledged is not None and bool(snapshot.get("acknowledged", False)) != acknowledged:
            continue
        if has_notes is not None and (int(snapshot.get("notes_count", 0) or 0) > 0) != has_notes:
            continue
        if attention_needed is not None and bool(snapshot.get("attention_needed", False)) != attention_needed:
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
    created_at = str(detail.get("created_at", "") or "")
    if created_at:
        opened_summary = str(detail.get("opened_summary", "") or detail.get("summary", "") or "incident opened")
        events.append(
            {
                "time": created_at,
                "type": "opened",
                "by": "watchdog",
                "summary": opened_summary,
                "message": opened_summary,
            }
        )
    workflow_events = detail.get("events", []) if isinstance(detail.get("events", []), list) else []
    for event in workflow_events:
        if not isinstance(event, dict):
            continue
        events.append(
            {
                "time": str(event.get("time", "") or ""),
                "type": str(event.get("type", "") or "unknown"),
                "by": str(event.get("by", "") or ""),
                "summary": str(event.get("summary", "") or ""),
                "message": str(event.get("message", "") or ""),
                "owner": str(event.get("owner", "") or ""),
                "acknowledged": bool(event.get("acknowledged", False)),
            }
        )
    resolved_at = str(detail.get("resolved_at", "") or "")
    if resolved_at:
        events.append(
            {
                "time": resolved_at,
                "type": "resolved",
                "by": "watchdog",
                "summary": str(detail.get("resolution_summary", "") or "incident resolved"),
                "message": str(detail.get("resolution_summary", "") or ""),
            }
        )
    event_order = {
        "opened": 0,
        "owner-assigned": 1,
        "owner-unassigned": 2,
        "acknowledged": 3,
        "unacknowledged": 4,
        "note": 5,
        "resolved": 6,
    }
    events = sorted(
        events,
        key=lambda item: (
            str(item.get("time", "") or ""),
            event_order.get(str(item.get("type", "") or "unknown"), 99),
        ),
    )
    if limit is not None and limit > 0:
        events = events[-limit:]
    return {
        "incident_id": incident_id,
        "state": detail.get("state", "unknown"),
        "event_count": len(events),
        "events": events,
        "notes_count": detail.get("notes_count", 0),
        "owner": detail.get("owner", ""),
        "acknowledged": detail.get("acknowledged", False),
    }


def current_incident_payload(engine) -> dict[str, object]:
    if not engine.current_incident_marker.exists():
        return {}
    incident_id = engine.current_incident_marker.read_text(encoding="utf-8").strip()
    if not incident_id:
        return {}
    return incident_detail_payload(engine, incident_id)


def incident_queue_payload(engine, *, limit: int | None = None) -> dict[str, object]:
    incidents = list_incident_snapshots(engine, state="open")
    incidents = sorted(
        incidents,
        key=lambda item: (
            0 if bool(item.get("attention_needed", False)) else 1,
            -int(item.get("attention_count", 0) or 0),
            str(item.get("time", "") or ""),
        ),
        reverse=False,
    )
    visible = incidents[:limit] if limit is not None and limit > 0 else incidents
    summary = {
        "open_total": len(incidents),
        "attention_total": sum(1 for item in incidents if bool(item.get("attention_needed", False))),
        "handled_total": sum(1 for item in incidents if not bool(item.get("attention_needed", False))),
        "owned_total": sum(1 for item in incidents if str(item.get("owner", "") or "").strip()),
        "acknowledged_total": sum(1 for item in incidents if bool(item.get("acknowledged", False))),
        "with_notes_total": sum(1 for item in incidents if int(item.get("notes_count", 0) or 0) > 0),
    }
    return {
        "summary": summary,
        "incidents": visible,
    }


def refresh_incident_index_for(engine, incident_id: str, *, summary: str | None = None, health_level: str | None = None) -> None:
    incident_id = incident_id.strip()
    if not incident_id:
        return
    incident_dir = engine.config.watchdog_incidents_dir / incident_id
    if not incident_dir.exists() or not incident_dir.is_dir():
        return
    operator_payload = engine.read_incident_operator_summary_payload(incident_dir)
    state_payload = engine.read_incident_state_payload(incident_dir)
    existing_index_payload = next(
        (
            item
            for item in reversed(engine.read_incident_index())
            if str(item.get("incident_id", "")) == incident_id
        ),
        {},
    )
    current_summary = summary or str(existing_index_payload.get("summary") or state_payload.get("summary") or operator_payload.get("summary") or "")
    current_health_level = health_level or str(
        existing_index_payload.get("health_level")
        or operator_payload.get("health_level")
        or engine.read_run_state().get("health_level", "unknown")
    )
    engine.update_incident_index(
        summary=current_summary,
        active=str(operator_payload.get("active", existing_index_payload.get("active", "unknown")) or "unknown"),
        main_pid=str(operator_payload.get("main_pid", existing_index_payload.get("main_pid", "0")) or "0"),
        listeners=str(operator_payload.get("listeners", existing_index_payload.get("listeners", "none")) or "none"),
        health_level=current_health_level,
        pre_repair_backup_result=str(existing_index_payload.get("pre_repair_backup_result", engine.pre_repair_backup_result) or engine.pre_repair_backup_result),
        rollback_occurred=bool(existing_index_payload.get("rollback_occurred", engine.rollback_occurred)),
        rollback_summary_archive_file=str(existing_index_payload.get("rollback_summary_archive_file", engine.rollback_summary_archive_file) or engine.rollback_summary_archive_file),
        codex_trigger_result=str(existing_index_payload.get("codex_trigger_result", engine.codex_trigger_result) or engine.codex_trigger_result),
        opencode_fallback_trigger_result=str(existing_index_payload.get("opencode_fallback_trigger_result", engine.opencode_fallback_trigger_result) or engine.opencode_fallback_trigger_result),
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
    payload = engine.read_incident_operator_workflow_payload(incident_dir)
    notes = payload.get("notes", []) if isinstance(payload.get("notes", []), list) else []
    clean_notes = [note for note in notes if isinstance(note, dict)]
    events = payload.get("events", []) if isinstance(payload.get("events", []), list) else []
    clean_events = [event for event in events if isinstance(event, dict)]
    now_iso = engine.now_iso()
    current_owner = str(payload.get("owner", "") or "")
    current_ack = bool(payload.get("acknowledged", False))
    current_ack_by = str(payload.get("acknowledged_by", "") or "")
    if clear_owner and current_owner:
        payload["owner"] = ""
        clean_events.append({"time": now_iso, "type": "owner-unassigned", "by": "", "owner": "", "acknowledged": current_ack, "message": "", "summary": "owner cleared"})
    elif owner is not None:
        next_owner = owner.strip()
        if next_owner != current_owner:
            payload["owner"] = next_owner
            clean_events.append({"time": now_iso, "type": "owner-assigned", "by": next_owner, "owner": next_owner, "acknowledged": current_ack, "message": "", "summary": f"owner -> {next_owner or 'none'}"})
    if clear_ack and current_ack:
        payload["acknowledged"] = False
        payload["acknowledged_at"] = ""
        payload["acknowledged_by"] = ""
        clean_events.append({"time": now_iso, "type": "unacknowledged", "by": "", "owner": str(payload.get("owner", "") or ""), "acknowledged": False, "message": "", "summary": "acknowledgement cleared"})
    elif acknowledged is not None:
        next_ack = bool(acknowledged)
        payload["acknowledged"] = next_ack
        if next_ack:
            ack_by = (acknowledged_by or payload.get("acknowledged_by") or "").strip()
            payload["acknowledged_at"] = now_iso
            payload["acknowledged_by"] = ack_by
            if not current_ack or ack_by != current_ack_by:
                clean_events.append({"time": now_iso, "type": "acknowledged", "by": ack_by, "owner": str(payload.get("owner", "") or ""), "acknowledged": True, "message": "", "summary": f"acknowledged by {ack_by or 'unknown'}"})
    if note_message is not None and note_message.strip():
        note_by_value = (note_by or acknowledged_by or "").strip()
        note_text = note_message.strip()
        clean_notes.append({"time": now_iso, "by": note_by_value, "message": note_text})
        clean_events.append({"time": now_iso, "type": "note", "by": note_by_value, "owner": str(payload.get("owner", "") or ""), "acknowledged": bool(payload.get("acknowledged", False)), "message": note_text, "summary": _compact_text(note_text)})
    payload["incident_id"] = incident_id
    payload["notes"] = clean_notes
    payload["events"] = clean_events
    payload["updated_at"] = now_iso
    engine.incident_operator_workflow_file(incident_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    refresh_incident_index_for(engine, incident_id)
    return incident_detail_payload(engine, incident_id)


def set_incident_owner(engine, incident_id: str, owner: str) -> dict[str, object]:
    return update_incident_operator_workflow(engine, incident_id, owner=owner)


def clear_incident_owner(engine, incident_id: str) -> dict[str, object]:
    return update_incident_operator_workflow(engine, incident_id, clear_owner=True)


def acknowledge_incident(engine, incident_id: str, *, acknowledged_by: str, note: str = "") -> dict[str, object]:
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
