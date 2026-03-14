from __future__ import annotations

import fcntl
from datetime import datetime
from pathlib import Path

from openclaw_watchdog import state_store


def prepare_state_dirs(engine) -> None:
    engine.config.watchdog_state_dir.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_rollback_archive_dir.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_incidents_dir.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_log_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_event_history_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_incident_index_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_last_report_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_last_metrics_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_survival_config_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_survival_state_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_guard_manifest_file.parent.mkdir(parents=True, exist_ok=True)
    engine.run_state_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_log_file.touch(exist_ok=True)
    engine.config.watchdog_event_history_file.touch(exist_ok=True)
    if not engine.run_state_file.exists():
        engine.write_run_state({})


def acquire_lock(engine) -> bool:
    engine.config.watchdog_lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = engine.config.watchdog_lock_file.open('a+')
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        engine.lock_handle = None
        return False
    engine.lock_handle = handle
    return True


def release_lock(engine) -> None:
    if engine.lock_handle is None:
        return
    try:
        fcntl.flock(engine.lock_handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    engine.lock_handle.close()
    engine.lock_handle = None


def log(engine, level: str, message: str) -> None:
    line = f"[{datetime.now().astimezone().strftime('%F %T %Z')}] [{level}] {message}\n"
    with engine.config.watchdog_log_file.open('a', encoding='utf-8') as handle:
        handle.write(line)


def notify(engine, message: str) -> None:
    if not engine.config.watchdog_notify_channel or not engine.config.watchdog_notify_target:
        return
    engine.run_command(
        [
            'openclaw',
            'message',
            'send',
            '--account',
            engine.config.watchdog_notify_account,
            '--channel',
            engine.config.watchdog_notify_channel,
            '--target',
            engine.config.watchdog_notify_target,
            '--message',
            message,
        ],
        timeout=engine.config.watchdog_message_timeout_seconds,
    )


def append_rollback_summary(engine, text: str) -> str:
    if engine.ctx.rollback_summary:
        return f'{text}\n\n回退摘要：\n{engine.ctx.rollback_summary}'
    return text


def read_failure_count(engine) -> int:
    try:
        value = engine.config.watchdog_failure_count_file.read_text(encoding='utf-8').strip()
        return int(value)
    except (FileNotFoundError, ValueError):
        return 0


def write_failure_count(engine, count: int) -> None:
    engine.ctx.consecutive_failures = max(0, int(count))
    engine.config.watchdog_failure_count_file.write_text(f'{engine.ctx.consecutive_failures}', encoding='utf-8')


def reset_failure_count(engine) -> None:
    write_failure_count(engine, 0)


def increment_failure_count(engine) -> int:
    count = read_failure_count(engine) + 1
    write_failure_count(engine, count)
    return count


def now_iso(engine) -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def current_mode(*, maintenance: bool, degraded: bool = False, survival: bool = False) -> str:
    if maintenance:
        return 'maintenance'
    if survival:
        return 'survival'
    if degraded:
        return 'degraded'
    return 'normal'


def sibling_json_path(path: Path) -> Path:
    return state_store.sibling_json_path(path)
