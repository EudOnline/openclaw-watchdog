from __future__ import annotations

import json
from pathlib import Path

from openclaw_watchdog import generation_runtime
from openclaw_watchdog import guard_runtime
from openclaw_watchdog import survival_state_runtime


def sync_state_updates(engine, *, state: dict[str, object], probe: dict[str, object], config_invalid: bool) -> dict[str, object]:
    applied_fingerprint = str(state.get('applied_config_fingerprint', '') or '')
    current_fingerprint = guard_runtime.fingerprint_path(engine.config.openclaw_config)
    config_changed_away = bool(applied_fingerprint and current_fingerprint and applied_fingerprint != current_fingerprint)
    conversation_ready = bool(probe.get('conversation_ready', False))
    minimal_usable_ready = bool(probe.get('minimal_usable_ready', conversation_ready))
    stable_required = max(
        1,
        int(state.get('stable_required_runs', survival_state_runtime.stable_required_runs(engine)) or survival_state_runtime.stable_required_runs(engine)),
    )
    stable_ready_runs = int(state.get('stable_ready_runs', 0) or 0)
    stable_ready_since = str(state.get('stable_ready_since', '') or '')

    if conversation_ready and not config_invalid:
        stable_ready_runs += 1
        if not stable_ready_since:
            stable_ready_since = engine.now_iso()
    else:
        stable_ready_runs = 0
        stable_ready_since = ''

    exit_ready = conversation_ready and not config_invalid and stable_ready_runs >= stable_required
    exit_policy = 'automatic' if config_changed_away else 'manual-clear-or-reconfig'

    blockers: list[str] = []
    if config_invalid:
        blockers.append('config invalid')
    if not minimal_usable_ready:
        blockers.append('minimal conversation not yet usable')
    elif not conversation_ready:
        blockers.append('full conversation not yet ready')
    if stable_ready_runs < stable_required:
        blockers.append(f'waiting for stable full-ready window {stable_ready_runs}/{stable_required}')
    if exit_ready and not config_changed_away:
        blockers.append('still running survival config; manual-clear-or-reconfig required')

    return {
        'sticky': not (exit_ready and config_changed_away),
        'sticky_reason': blockers[0] if blockers else '',
        'exit_ready': exit_ready,
        'exit_policy': exit_policy,
        'exit_blockers': blockers,
        'stable_ready_runs': stable_ready_runs,
        'stable_required_runs': stable_required,
        'stable_ready_since': stable_ready_since,
        'manual_clear_required': bool(exit_ready and not config_changed_away),
        'config_changed_away': config_changed_away,
    }


def load_candidate_config(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def select_source_config(engine) -> tuple[dict[str, object] | None, str, str]:
    current = load_candidate_config(engine.config.openclaw_config)
    if current is not None:
        return current, str(engine.config.openclaw_config), guard_runtime.fingerprint_path(engine.config.openclaw_config)
    for candidate in generation_runtime.last_good_candidates(engine):
        path = Path(str(candidate.get('path', '') or ''))
        payload = load_candidate_config(path)
        if payload is not None:
            return payload, str(path), guard_runtime.fingerprint_path(path)
    return None, '', ''


def normalize_channels(raw: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw, dict):
        return {}
    channels: dict[str, dict[str, object]] = {}
    for name, details in raw.items():
        if isinstance(details, dict):
            channels[str(name)] = details
    return channels


def build_survival_plan(engine, *, reason: str) -> dict[str, object] | None:
    source_config, source_path, source_fingerprint = select_source_config(engine)
    if source_config is None:
        return None

    plan_config = json.loads(json.dumps(source_config, ensure_ascii=False))
    channels = normalize_channels(plan_config.get('channels', {}))
    if not channels:
        return None
    plan_config['channels'] = channels

    requested = [channel for channel in engine.config.watchdog_survival_required_channels if channel in channels]
    enabled = [name for name, details in channels.items() if bool(details.get('enabled', False))]
    kept = requested or enabled[:1] or list(channels.keys())[:1]
    if not kept:
        return None

    actions: list[str] = []
    disabled_features: list[str] = []
    for name, details in channels.items():
        should_enable = name in kept
        if bool(details.get('enabled', False)) != should_enable:
            details['enabled'] = should_enable
            if should_enable:
                actions.append(f'enabled required channel {name}')
            else:
                actions.append(f'disabled optional channel {name}')
        if not should_enable:
            disabled_features.append(f'channel:{name}')

    if engine.config.watchdog_survival_disable_optional_extensions:
        for key in ('extensions', 'mcpServers', 'services', 'workers', 'schedules'):
            if key not in plan_config:
                continue
            current = plan_config.get(key)
            if isinstance(current, dict) and current:
                plan_config[key] = {}
                actions.append(f'cleared optional section {key}')
                disabled_features.append(f'section:{key}')
            elif isinstance(current, list) and current:
                plan_config[key] = []
                actions.append(f'cleared optional section {key}')
                disabled_features.append(f'section:{key}')

    kept_channels = [name for name in channels if name in kept]
    disabled_channels = [name for name in channels if name not in kept]
    summary = f"kept channels={','.join(kept_channels)}; disabled={','.join(disabled_channels) if disabled_channels else 'none'}"
    if not actions:
        actions.append('reused existing minimal channel-only config')

    return {
        'config': plan_config,
        'summary': summary,
        'reason': reason,
        'actions': actions,
        'disabled_features': disabled_features,
        'required_channels': kept_channels,
        'source_config_path': source_path,
        'source_config_fingerprint': source_fingerprint,
    }
