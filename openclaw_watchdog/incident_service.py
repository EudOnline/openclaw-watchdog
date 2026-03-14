from __future__ import annotations

from pathlib import Path

from openclaw_watchdog import incident_read_runtime
from openclaw_watchdog import incident_write_runtime


def incident_bool(value: object) -> bool:
    return incident_read_runtime.incident_bool(value)


def incident_state_file(engine, incident_dir: Path) -> Path:
    return incident_read_runtime.incident_state_file(engine, incident_dir)


def read_json_dict(path: Path) -> dict[str, object]:
    return incident_read_runtime.read_json_dict(path)


def read_incident_state_payload(engine, incident_dir: Path) -> dict[str, object]:
    return incident_read_runtime.read_incident_state_payload(engine, incident_dir)


def read_incident_operator_summary_payload(engine, incident_dir: Path) -> dict[str, object]:
    return incident_read_runtime.read_incident_operator_summary_payload(engine, incident_dir)


def incident_operator_workflow_file(engine, incident_dir: Path) -> Path:
    return incident_read_runtime.incident_operator_workflow_file(engine, incident_dir)


def read_incident_operator_workflow_payload(engine, incident_dir: Path) -> dict[str, object]:
    return incident_read_runtime.read_incident_operator_workflow_payload(engine, incident_dir)


def incident_operator_summary(engine, *, summary: str, active: str, main_pid: str, listeners: str) -> str:
    return incident_write_runtime.incident_operator_summary(
        engine,
        summary=summary,
        active=active,
        main_pid=main_pid,
        listeners=listeners,
    )


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
    return incident_write_runtime.incident_index_entry(
        engine,
        summary=summary,
        active=active,
        main_pid=main_pid,
        listeners=listeners,
        health_level=health_level,
        pre_repair_backup_result=pre_repair_backup_result,
        rollback_occurred=rollback_occurred,
        rollback_summary_archive_file=rollback_summary_archive_file,
        incident_id=incident_id,
        incident_dir=incident_dir,
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
    incident_write_runtime.update_incident_index(
        engine,
        summary=summary,
        active=active,
        main_pid=main_pid,
        listeners=listeners,
        health_level=health_level,
        pre_repair_backup_result=pre_repair_backup_result,
        rollback_occurred=rollback_occurred,
        rollback_summary_archive_file=rollback_summary_archive_file,
        incident_id=incident_id,
        incident_dir=incident_dir,
    )


def read_incident_index(engine, limit: int | None = None) -> list[dict[str, object]]:
    return incident_read_runtime.read_incident_index(engine, limit=limit)


def refresh_current_incident_index(engine, *, summary: str | None = None, health_level: str | None = None) -> None:
    incident_write_runtime.refresh_current_incident_index(engine, summary=summary, health_level=health_level)


def write_incident_operator_summary(engine, *, summary: str, active: str, main_pid: str, listeners: str) -> None:
    incident_write_runtime.write_incident_operator_summary(
        engine,
        summary=summary,
        active=active,
        main_pid=main_pid,
        listeners=listeners,
    )


def update_incident_state(engine, state: str, summary: str, *, resolved: bool = False) -> None:
    incident_write_runtime.update_incident_state(engine, state, summary, resolved=resolved)


def load_existing_incident_context(engine, incident_id: str) -> bool:
    return incident_write_runtime.load_existing_incident_context(engine, incident_id)


def attach_current_incident_if_any(engine) -> bool:
    return incident_write_runtime.attach_current_incident_if_any(engine)


def reset_incident_state(engine) -> None:
    incident_write_runtime.reset_incident_state(engine)
