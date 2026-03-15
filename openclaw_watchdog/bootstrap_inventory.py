from __future__ import annotations

from typing import Any

from openclaw_watchdog import detect_executor_runtime
from openclaw_watchdog.openclaw_runtime import adapter as openclaw_runtime_adapter


def detect_first_available(bootstrapper, *candidates: str) -> dict[str, Any]:
    return detect_executor_runtime.detect_first_available(bootstrapper, *candidates)


def detect_codex(bootstrapper) -> dict[str, Any]:
    return detect_executor_runtime.detect_codex(bootstrapper)


def detect_claude_code(bootstrapper) -> dict[str, Any]:
    return detect_executor_runtime.detect_claude_code(bootstrapper)


def detect_gemini_cli(bootstrapper) -> dict[str, Any]:
    return detect_executor_runtime.detect_gemini_cli(bootstrapper)


def detect_litellm(bootstrapper) -> dict[str, Any]:
    return detect_executor_runtime.detect_litellm(bootstrapper)


def populate_opencode_watchdog_status(bootstrapper, payload: dict[str, Any]) -> None:
    detect_executor_runtime.populate_opencode_watchdog_status(bootstrapper, payload)


def detect_opencode(bootstrapper) -> dict[str, Any]:
    return detect_executor_runtime.detect_opencode(bootstrapper)


def detect_openclaw(bootstrapper) -> dict[str, Any]:
    available, detected_binary, detect_result = bootstrapper._detect_openclaw_binary()
    doctor_help_returncode = 1
    doctor_capabilities = openclaw_runtime_adapter.default_adapter().detect_doctor_capabilities('')
    if available:
        help_result = bootstrapper.run_shell('openclaw doctor --help', timeout=30)
        doctor_help_returncode = help_result.returncode
        doctor_capabilities = openclaw_runtime_adapter.default_adapter().detect_doctor_capabilities(help_result.output)
    return {
        'available': available,
        'binary': detected_binary,
        'detect_returncode': detect_result.returncode,
        'doctor_help_returncode': doctor_help_returncode,
        'doctor_capabilities': doctor_capabilities.to_dict(),
    }
