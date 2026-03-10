from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root() / path


def path_from_env(name: str, default: str) -> Path:
    return resolve_repo_path(os.environ.get(name, default))


def runtime_root() -> Path:
    return repo_root() / "rehearsal" / "runtime"


def state_file() -> Path:
    return path_from_env("REHEARSAL_SHIM_STATE_FILE", "rehearsal/runtime/shim-state.json")


def journal_log_path() -> Path:
    return path_from_env("REHEARSAL_JOURNAL_LOG", "rehearsal/runtime/logs/journal.log")


def messages_log_path() -> Path:
    return path_from_env("REHEARSAL_MESSAGES_LOG", "rehearsal/runtime/logs/messages.log")


def openclaw_runtime_log_path() -> Path:
    return path_from_env("OPENCLAW_BOOTSTRAP_LOG_FILE", "rehearsal/runtime/logs/openclaw-runtime.log")


def opencode_log_path() -> Path:
    return path_from_env("REHEARSAL_OPENCODE_LOG", "rehearsal/runtime/logs/opencode.log")


def codex_log_path() -> Path:
    return path_from_env("REHEARSAL_CODEX_LOG", "rehearsal/runtime/logs/codex.log")


def backup_dir() -> Path:
    return path_from_env("OPENCLAW_BACKUP_DEST", "rehearsal/runtime/backups")


def openclaw_config_path() -> Path:
    return path_from_env("OPENCLAW_CONFIG", "rehearsal/runtime/home/.openclaw/openclaw.json")


def gateway_port() -> int:
    raw = os.environ.get("OPENCLAW_GATEWAY_PORT", "18789").strip()
    try:
        return int(raw)
    except ValueError:
        return 18789


def gateway_service() -> str:
    return os.environ.get("OPENCLAW_GATEWAY_SERVICE", "openclaw-gateway.service").strip() or "openclaw-gateway.service"


def now_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def default_state() -> dict[str, Any]:
    return {
        "next_pid": 4200,
        "service_active": False,
        "main_pid": "0",
        "listener_pids": [],
        "plugins": [],
        "restart_mode": "healthy",
        "plugin_install_fails": False,
        "doctor_ok_message": "Doctor OK",
        "doctor_fail_message": "",
        "repair_message": "Applied simulated repair steps",
        "repair_fixes_invalid_config": False,
    }


def ensure_runtime_layout() -> None:
    directories = [
        runtime_root(),
        runtime_root() / "bin",
        runtime_root() / "logs",
        runtime_root() / "home",
        runtime_root() / "watchdog",
        runtime_root() / "backups",
        runtime_root() / "scenario-output",
        openclaw_config_path().parent,
        state_file().parent,
        journal_log_path().parent,
        messages_log_path().parent,
        openclaw_runtime_log_path().parent,
        opencode_log_path().parent,
        codex_log_path().parent,
        backup_dir(),
    ]
    for path in directories:
        path.mkdir(parents=True, exist_ok=True)
    for path in [journal_log_path(), messages_log_path(), openclaw_runtime_log_path(), opencode_log_path(), codex_log_path()]:
        path.touch(exist_ok=True)
    if not state_file().exists():
        save_state(default_state())


def load_state() -> dict[str, Any]:
    ensure_runtime_layout()
    current = default_state()
    try:
        loaded = json.loads(state_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        save_state(current)
        return current
    if isinstance(loaded, dict):
        current.update(loaded)
    save_state(current)
    return current


def save_state(state: dict[str, Any]) -> None:
    ensure_runtime_layout.__defaults__
    state_file().parent.mkdir(parents=True, exist_ok=True)
    state_file().write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def allocate_pid(state: dict[str, Any]) -> str:
    next_pid = int(state.get("next_pid", 4200))
    state["next_pid"] = next_pid + 1
    return str(next_pid)


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")


def append_journal(message: str) -> None:
    append_line(journal_log_path(), f"[{now_stamp()}] {message}")


def append_runtime_log(message: str) -> None:
    append_line(openclaw_runtime_log_path(), message)


def render_service_status(state: dict[str, Any]) -> str:
    active_label = "active (running)" if state.get("service_active") else "inactive (dead)"
    main_pid = state.get("main_pid", "0")
    return "\n".join(
        [
            f"● {gateway_service()} - Rehearsal OpenClaw gateway",
            f"     Loaded: loaded ({gateway_service()}; enabled; preset: enabled)",
            f"     Active: {active_label}",
            f"   Main PID: {main_pid}",
        ]
    )

