from __future__ import annotations

from typing import Any

from openclaw_watchdog import detect_executor_runtime


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
