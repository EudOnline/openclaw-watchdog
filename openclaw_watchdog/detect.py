from __future__ import annotations

from pathlib import Path

from openclaw_watchdog import detect_executor_runtime
from openclaw_watchdog import detect_health_runtime
from openclaw_watchdog import detect_service_runtime


CORE_COMMANDS = detect_executor_runtime.CORE_COMMANDS


def _now_iso() -> str:
    return detect_health_runtime.now_iso()


def _extract_json(text: str) -> dict[str, object] | None:
    return detect_health_runtime.extract_json(text)


def _run_json(engine, command: list[str], *, timeout: int = 20) -> dict[str, object] | None:
    return detect_health_runtime.run_json(engine, command, timeout=timeout)


def _parse_kv_output(text: str) -> dict[str, str]:
    return detect_service_runtime.parse_kv_output(text)


def _coerce_bool(value: object) -> bool | None:
    return detect_service_runtime.coerce_bool(value)


def _path_probe(path: Path) -> dict[str, object]:
    return detect_health_runtime.path_probe(path)


def _detect_commands() -> dict[str, dict[str, object]]:
    return detect_executor_runtime.detect_commands()


def _executor_inventory(engine, commands: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    return detect_executor_runtime.executor_inventory(engine, commands)


def _gateway_probe(engine, status_payload: dict[str, object] | None) -> dict[str, object]:
    return detect_service_runtime.gateway_probe(engine, status_payload)


def _channel_probe(health_payload: dict[str, object] | None) -> dict[str, object]:
    return detect_service_runtime.channel_probe(health_payload)


def render_suggested_env(payload: dict[str, object]) -> str:
    return detect_health_runtime.render_suggested_env(payload)


def write_suggested_env(payload: dict[str, object], target: Path) -> Path:
    return detect_health_runtime.write_suggested_env(payload, target)


def detect_payload(engine) -> dict[str, object]:
    return detect_health_runtime.detect_payload(engine)


def print_detect(payload: dict[str, object]) -> None:
    detect_health_runtime.print_detect(payload)
