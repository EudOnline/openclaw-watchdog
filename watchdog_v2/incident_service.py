from __future__ import annotations

import json
from pathlib import Path

from watchdog_v2 import incident_context as incident_context_ops
from watchdog_v2.config import parse_env_file


def incident_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def read_json_dict(path: Path) -> dict[str, object]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_incident_state_payload(engine, incident_dir: Path) -> dict[str, object]:
    return read_json_dict(engine.incident_state_file(incident_dir))


def read_incident_operator_summary_payload(engine, incident_dir: Path) -> dict[str, object]:
    return parse_env_file(incident_dir / "operator-summary.txt")


def incident_operator_workflow_file(engine, incident_dir: Path) -> Path:
    return incident_dir / "operator-workflow.json"


def read_incident_operator_workflow_payload(engine, incident_dir: Path) -> dict[str, object]:
    payload = read_json_dict(incident_operator_workflow_file(engine, incident_dir))
    notes = payload.get("notes", []) if isinstance(payload, dict) else []
    if not isinstance(notes, list):
        notes = []
    clean_notes: list[dict[str, object]] = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        clean_notes.append(
            {
                "time": str(note.get("time", "") or ""),
                "by": str(note.get("by", "") or ""),
                "message": str(note.get("message", "") or ""),
            }
        )
    events = payload.get("events", []) if isinstance(payload, dict) else []
    if not isinstance(events, list):
        events = []
    clean_events: list[dict[str, object]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        clean_events.append(
            {
                "time": str(event.get("time", "") or ""),
                "type": str(event.get("type", "") or ""),
                "by": str(event.get("by", "") or ""),
                "owner": str(event.get("owner", "") or ""),
                "acknowledged": bool(event.get("acknowledged", False)),
                "message": str(event.get("message", "") or ""),
                "summary": str(event.get("summary", "") or ""),
            }
        )
    return {
        "incident_id": str(payload.get("incident_id", incident_dir.name) or incident_dir.name),
        "owner": str(payload.get("owner", "") or ""),
        "acknowledged": bool(payload.get("acknowledged", False)),
        "acknowledged_by": str(payload.get("acknowledged_by", "") or ""),
        "acknowledged_at": str(payload.get("acknowledged_at", "") or ""),
        "updated_at": str(payload.get("updated_at", "") or ""),
        "notes": clean_notes,
        "events": clean_events,
    }


def incident_operator_summary(engine, *, summary: str, active: str, main_pid: str, listeners: str) -> str:
    run_state = engine.read_run_state()
    lines = [
        f"incident_id={engine.ctx.incident_id}",
        f"time={engine.ctx.run_ts}",
        f"summary={summary}",
        f"health_level={run_state.get('health_level', 'unknown')}",
        f"conversation_status={run_state.get('conversation_status', 'down')}",
        f"active={active}",
        f"main_pid={main_pid}",
        f"listeners={listeners}",
        f"pre_repair_backup_result={engine.ctx.pre_repair_backup_result}",
        f"rollback_occurred={'true' if engine.ctx.rollback_occurred else 'false'}",
        f"rollback_summary_archive_file={engine.ctx.rollback_summary_archive_file or 'none'}",
        f"rollback_candidate_used={engine.ctx.rollback_candidate_used or 'none'}",
        f"rollback_reason={engine.ctx.rollback_reason or 'none'}",
        f"last_recovery_strategy={engine.ctx.last_recovery_strategy}",
        f"last_recovery_path={engine.recovery_path_text()}",
    ]
    return "\n".join(lines) + "\n"


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
        incident_dir=str(target_incident_dir) if target_incident_dir else "",
        summary=summary,
        state_payload=read_incident_state_payload(engine, target_incident_dir) if target_incident_dir is not None else {},
        workflow_payload=read_incident_operator_workflow_payload(engine, target_incident_dir) if target_incident_dir is not None else {},
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
            data = json.loads(index_file.read_text(encoding="utf-8"))
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
    items = [item for item in items if str(item.get("incident_id", "")) != target_incident_id]
    items.append(entry)
    items = sorted(items, key=lambda item: str(item.get("incident_id", "")))
    keep = max(1, engine.config.watchdog_incident_index_limit)
    index_file.write_text(json.dumps(items[-keep:], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_incident_index(engine, limit: int | None = None) -> list[dict[str, object]]:
    index_file = engine.config.watchdog_incident_index_file
    if not index_file.exists():
        return []
    try:
        data = json.loads(index_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    items = [item for item in data if isinstance(item, dict)]
    if limit is not None and limit > 0:
        return items[-limit:]
    return items


def refresh_current_incident_index(engine, *, summary: str | None = None, health_level: str | None = None) -> None:
    if engine.ctx.incident_dir is None:
        return
    operator_payload = read_incident_operator_summary_payload(engine, engine.ctx.incident_dir)
    existing_index_payload = next(
        (
            item
            for item in reversed(read_incident_index(engine))
            if str(item.get("incident_id", "")) == engine.ctx.incident_id
        ),
        {},
    )
    current_summary = summary or str(operator_payload.get("summary", existing_index_payload.get("summary", "")) or "")
    update_incident_index(
        engine,
        summary=current_summary,
        active=str(operator_payload.get("active", existing_index_payload.get("active", "unknown")) or "unknown"),
        main_pid=str(operator_payload.get("main_pid", existing_index_payload.get("main_pid", "0")) or "0"),
        listeners=str(operator_payload.get("listeners", existing_index_payload.get("listeners", "none")) or "none"),
        health_level=health_level,
        pre_repair_backup_result=str(existing_index_payload.get("pre_repair_backup_result", engine.ctx.pre_repair_backup_result) or engine.ctx.pre_repair_backup_result),
        rollback_occurred=bool(existing_index_payload.get("rollback_occurred", engine.ctx.rollback_occurred)),
        rollback_summary_archive_file=str(existing_index_payload.get("rollback_summary_archive_file", engine.ctx.rollback_summary_archive_file) or engine.ctx.rollback_summary_archive_file),
    )


def write_incident_operator_summary(engine, *, summary: str, active: str, main_pid: str, listeners: str) -> None:
    if engine.ctx.incident_dir is None:
        return
    (engine.ctx.incident_dir / "operator-summary.txt").write_text(
        incident_operator_summary(engine, summary=summary, active=active, main_pid=main_pid, listeners=listeners),
        encoding="utf-8",
    )
    update_incident_index(engine, summary=summary, active=active, main_pid=main_pid, listeners=listeners)


def update_incident_state(engine, state: str, summary: str, *, resolved: bool = False) -> None:
    if engine.ctx.incident_dir is None:
        return
    incident_state_file = engine.incident_state_file(engine.ctx.incident_dir)
    payload: dict[str, object] = {
        "incident_id": engine.ctx.incident_id,
        "state": state,
        "summary": summary,
    }
    if incident_state_file.exists():
        try:
            existing = json.loads(incident_state_file.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                payload = {**existing, **payload}
        except json.JSONDecodeError:
            pass
    payload.setdefault("created_at", engine.now_iso())
    if state == "open" and summary != "incident created":
        if not str(payload.get("opened_summary", "") or "") or str(payload.get("opened_summary", "") or "") == "incident created":
            payload["opened_summary"] = summary
    elif not str(payload.get("opened_summary", "") or ""):
        payload["opened_summary"] = summary
    if resolved:
        payload["resolved_at"] = engine.now_iso()
        payload["resolution_summary"] = summary
    incident_state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_existing_incident_context(engine, incident_id: str) -> bool:
    incident_id = incident_id.strip()
    if not incident_id:
        return False
    incident_dir = engine.config.watchdog_incidents_dir / incident_id
    if not incident_dir.exists() or not incident_dir.is_dir():
        return False
    engine.ctx.incident_id = incident_id
    engine.ctx.incident_dir = incident_dir
    engine.current_incident_marker.write_text(f"{incident_id}\n", encoding="utf-8")
    return True


def attach_current_incident_if_any(engine) -> bool:
    if engine.ctx.incident_dir is not None and engine.ctx.incident_id:
        return True
    if not engine.current_incident_marker.exists():
        return False
    incident_id = engine.current_incident_marker.read_text(encoding="utf-8").strip()
    return load_existing_incident_context(engine, incident_id)


def reset_incident_state(engine) -> None:
    engine.current_incident_marker.unlink(missing_ok=True)
    engine.ctx.incident_id = ""
    engine.ctx.incident_dir = None
