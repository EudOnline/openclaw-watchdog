from __future__ import annotations

from typing import Any

from openclaw_watchdog import executor_registry


def detect_first_available(bootstrapper, *candidates: str) -> dict[str, Any]:
    for candidate in candidates:
        available, detected_binary, detect_result = bootstrapper.detect_binary(candidate)
        if available:
            return {
                'available': True,
                'detected_binary': detected_binary,
                'detect_returncode': detect_result.returncode,
            }
    candidate = next((item for item in candidates if item), '')
    _, _, detect_result = bootstrapper.detect_binary(candidate) if candidate else (False, '', bootstrapper.empty_shell_result())
    return {
        'available': False,
        'detected_binary': '',
        'detect_returncode': detect_result.returncode,
    }


def detect_codex(bootstrapper) -> dict[str, Any]:
    configured = executor_registry.configured_bin(bootstrapper.config, 'codex') or 'codex'
    configured_available, configured_binary, configured_result = bootstrapper.detect_binary(configured)
    path_available, path_binary, path_result = bootstrapper.detect_binary('codex')
    return {
        'configured_bin': configured,
        'configured_available': configured_available,
        'configured_binary': configured_binary,
        'configured_detect_returncode': configured_result.returncode,
        'path_available': path_available,
        'path_binary': path_binary,
        'path_detect_returncode': path_result.returncode,
        'available': configured_available or path_available,
        'detected_binary': configured_binary or path_binary,
    }


def detect_claude_code(bootstrapper) -> dict[str, Any]:
    return detect_first_available(bootstrapper, *executor_registry.command_candidates(bootstrapper.config, 'claude-code'))


def detect_gemini_cli(bootstrapper) -> dict[str, Any]:
    return detect_first_available(bootstrapper, *executor_registry.command_candidates(bootstrapper.config, 'gemini-cli'))


def detect_litellm(bootstrapper) -> dict[str, Any]:
    enabled = bool(getattr(bootstrapper.config, 'watchdog_litellm_enabled', False))
    model = str(getattr(bootstrapper.config, 'watchdog_litellm_model', '') or '')
    api_base = str(getattr(bootstrapper.config, 'watchdog_litellm_api_base', '') or '')
    configured = enabled and bool(model)
    return {
        'available': configured,
        'enabled': enabled,
        'configured': configured,
        'model': model,
        'api_base': api_base,
    }


def populate_opencode_watchdog_status(bootstrapper, payload: dict[str, Any]) -> None:
    watchdog_bin = executor_registry.configured_bin(bootstrapper.config, 'opencode') or 'opencode'
    payload['watchdog_bin'] = watchdog_bin
    available, detected_binary, _ = bootstrapper.detect_binary(watchdog_bin)
    payload['watchdog_bin_available'] = available
    payload['watchdog_binary'] = detected_binary


def detect_opencode(bootstrapper) -> dict[str, Any]:
    installed, detected_path, detect_result = bootstrapper.detect_binary('opencode')
    payload: dict[str, Any] = {
        'available': installed,
        'detected_binary': detected_path,
        'detect_returncode': detect_result.returncode,
        'watchdog_bin': executor_registry.configured_bin(bootstrapper.config, 'opencode') or 'opencode',
        'watchdog_bin_available': False,
        'watchdog_binary': '',
        'config': bootstrapper.inspect_opencode_config(),
        'config_ready': False,
    }
    populate_opencode_watchdog_status(bootstrapper, payload)
    payload['config_ready'] = bool(payload['config'].get('ready', False)) if isinstance(payload.get('config'), dict) else False
    return payload
