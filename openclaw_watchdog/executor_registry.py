from __future__ import annotations

import shutil
from typing import Callable, cast

CANONICAL_EXECUTOR_ORDER: tuple[str, ...] = (
    'codex',
    'claude-code',
    'gemini-cli',
    'opencode',
    'litellm',
    'rule-agent',
)

EXECUTOR_SPECS: dict[str, dict[str, object]] = {
    'codex': {
        'display_name': 'Codex',
        'command_candidates': ('codex',),
        'configured_bin_attr': 'watchdog_codex_bin',
        'timeout_attr': 'watchdog_codex_timeout_seconds',
        'workdir_attr': 'watchdog_codex_workdir',
    },
    'claude-code': {
        'display_name': 'Claude Code',
        'command_candidates': ('claude', 'claude-code'),
        'configured_bin_attr': 'watchdog_claude_code_bin',
        'timeout_attr': 'watchdog_claude_code_timeout_seconds',
        'workdir_attr': 'watchdog_claude_code_workdir',
    },
    'gemini-cli': {
        'display_name': 'Gemini CLI',
        'command_candidates': ('gemini', 'gemini-cli'),
        'configured_bin_attr': 'watchdog_gemini_cli_bin',
        'timeout_attr': 'watchdog_gemini_cli_timeout_seconds',
        'workdir_attr': 'watchdog_gemini_cli_workdir',
    },
    'opencode': {
        'display_name': 'OpenCode',
        'command_candidates': ('opencode',),
        'configured_bin_attr': 'watchdog_opencode_bin',
        'timeout_attr': 'watchdog_opencode_timeout_seconds',
        'workdir_attr': 'watchdog_opencode_workdir',
    },
    'litellm': {
        'display_name': 'LiteLLM',
    },
    'rule-agent': {
        'display_name': 'rule-agent',
        'builtin': True,
    },
}


def configured_priority(config) -> tuple[str, ...]:
    return CANONICAL_EXECUTOR_ORDER


def display_name(name: str) -> str:
    spec = EXECUTOR_SPECS.get(name, {})
    return str(spec.get('display_name', name) or name)


def configured_bin(config, name: str) -> str:
    spec = EXECUTOR_SPECS.get(name, {})
    attr = str(spec.get('configured_bin_attr', '') or '')
    if not attr:
        return ''
    return str(getattr(config, attr, '') or '').strip()


def command_candidates(config, name: str) -> tuple[str, ...]:
    spec = EXECUTOR_SPECS.get(name, {})
    candidates: list[str] = []
    configured = configured_bin(config, name)
    if configured:
        candidates.append(configured)
    configured_candidates = cast(tuple[object, ...], spec.get('command_candidates', ()))
    for candidate in configured_candidates:
        candidate_text = str(candidate or '').strip()
        if candidate_text and candidate_text not in candidates:
            candidates.append(candidate_text)
    return tuple(candidates)


def command_available(command: str, *, which: Callable[[str], str | None] = shutil.which) -> bool:
    candidate = str(command or '').strip()
    if not candidate:
        return False
    return bool(which(candidate))


def executor_available(config, name: str, *, which: Callable[[str], str | None] = shutil.which) -> bool:
    if name == 'rule-agent':
        return True
    if name == 'litellm':
        return bool(getattr(config, 'watchdog_litellm_enabled', False)) and bool(
            str(getattr(config, 'watchdog_litellm_model', '') or '')
        )
    return any(command_available(candidate, which=which) for candidate in command_candidates(config, name))


def available_executors(config, *, which: Callable[[str], str | None] = shutil.which) -> tuple[str, ...]:
    available: list[str] = []
    for name in configured_priority(config):
        if executor_available(config, name, which=which):
            available.append(name)
    return tuple(available)


def rescue_command(config, name: str, *, which: Callable[[str], str | None] = shutil.which) -> str:
    candidates = command_candidates(config, name)
    for candidate in candidates:
        if command_available(candidate, which=which):
            return candidate
    if candidates:
        return candidates[0]
    return name


def timeout_seconds(config, name: str, *, default: int) -> int:
    spec = EXECUTOR_SPECS.get(name, {})
    attr = str(spec.get('timeout_attr', '') or '')
    if not attr:
        return int(default)
    return int(getattr(config, attr, default) or default)


def workdir(config, name: str):
    spec = EXECUTOR_SPECS.get(name, {})
    attr = str(spec.get('workdir_attr', '') or '')
    if not attr:
        return None
    return getattr(config, attr, None)
