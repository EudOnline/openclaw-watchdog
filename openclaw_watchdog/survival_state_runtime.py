from __future__ import annotations

import json


def stable_required_runs(engine) -> int:
    return max(1, int(engine.config.watchdog_survival_stable_ready_runs))


def default_state(engine) -> dict[str, object]:
    return {
        'active': False,
        'entered_at': '',
        'exited_at': '',
        'exit_reason': '',
        'reason': '',
        'summary': '',
        'actions': [],
        'disabled_features': [],
        'required_channels': list(engine.config.watchdog_survival_required_channels),
        'config_path': str(engine.config.watchdog_survival_config_file),
        'source_config_path': '',
        'source_config_fingerprint': '',
        'applied_config_fingerprint': '',
        'previous_config_backup_path': '',
        'sticky': False,
        'sticky_reason': '',
        'exit_ready': False,
        'exit_policy': 'manual-clear-or-reconfig',
        'exit_blockers': [],
        'stable_ready_runs': 0,
        'stable_required_runs': stable_required_runs(engine),
        'stable_ready_since': '',
        'manual_clear_required': False,
        'config_changed_away': False,
        'last_exit_at': '',
        'last_exit_reason': '',
        'last_exit_kind': '',
        'last_exit_summary': '',
    }


def read_survival_state(engine) -> dict[str, object]:
    state = default_state(engine)
    try:
        payload = json.loads(engine.config.watchdog_survival_state_file.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return state
    if isinstance(payload, dict):
        state.update(payload)
    return state


def write_survival_state(engine, state: dict[str, object]) -> dict[str, object]:
    payload = default_state(engine)
    payload.update(state)
    engine.config.watchdog_survival_state_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_survival_state_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    return payload


def apply_state_to_engine(engine, state: dict[str, object]) -> None:
    ctx = engine.ctx
    ctx.survival_mode_active = bool(state.get('active', False))
    ctx.survival_mode_reason = str(state.get('reason', '') or '') if ctx.survival_mode_active else ''
    ctx.survival_mode_since = str(state.get('entered_at', '') or '') if ctx.survival_mode_active else ''
    ctx.survival_mode_summary = str(state.get('summary', '') or '') if ctx.survival_mode_active else ''
    ctx.survival_mode_actions = [str(item) for item in state.get('actions', []) if str(item).strip()] if ctx.survival_mode_active else []
    ctx.survival_mode_disabled_features = [
        str(item) for item in state.get('disabled_features', []) if str(item).strip()
    ] if ctx.survival_mode_active else []
    ctx.survival_mode_config_file = (
        str(state.get('config_path', engine.config.watchdog_survival_config_file) or engine.config.watchdog_survival_config_file)
        if ctx.survival_mode_active
        else ''
    )
    ctx.survival_mode_sticky = bool(state.get('sticky', False)) if ctx.survival_mode_active else False
    ctx.survival_mode_sticky_reason = str(state.get('sticky_reason', '') or '') if ctx.survival_mode_active else ''
    ctx.survival_mode_exit_ready = bool(state.get('exit_ready', False)) if ctx.survival_mode_active else False
    ctx.survival_mode_exit_policy = str(state.get('exit_policy', '') or '') if ctx.survival_mode_active else 'none'
    ctx.survival_mode_exit_blockers = [
        str(item) for item in state.get('exit_blockers', []) if str(item).strip()
    ] if ctx.survival_mode_active else []
    ctx.survival_mode_stable_ready_runs = int(state.get('stable_ready_runs', 0) or 0) if ctx.survival_mode_active else 0
    ctx.survival_mode_stable_required_runs = int(state.get('stable_required_runs', stable_required_runs(engine)) or stable_required_runs(engine))
    ctx.survival_mode_manual_clear_required = bool(state.get('manual_clear_required', False)) if ctx.survival_mode_active else False
    ctx.survival_mode_config_changed_away = bool(state.get('config_changed_away', False)) if ctx.survival_mode_active else False
    ctx.survival_mode_last_exit_at = str(state.get('last_exit_at', '') or '')
    ctx.survival_mode_last_exit_reason = str(state.get('last_exit_reason', '') or '')
    ctx.survival_mode_last_exit_kind = str(state.get('last_exit_kind', '') or '')
    ctx.survival_mode_last_exit_summary = str(state.get('last_exit_summary', '') or '')


def run_state_fields(engine) -> dict[str, object]:
    ctx = engine.ctx
    return {
        'survival_mode_active': ctx.survival_mode_active,
        'survival_mode_reason': ctx.survival_mode_reason,
        'survival_mode_since': ctx.survival_mode_since,
        'survival_mode_summary': ctx.survival_mode_summary,
        'survival_mode_actions': list(ctx.survival_mode_actions),
        'survival_mode_disabled_features': list(ctx.survival_mode_disabled_features),
        'survival_mode_config_file': ctx.survival_mode_config_file,
        'survival_mode_sticky': ctx.survival_mode_sticky,
        'survival_mode_sticky_reason': ctx.survival_mode_sticky_reason,
        'survival_mode_exit_ready': ctx.survival_mode_exit_ready,
        'survival_mode_exit_policy': ctx.survival_mode_exit_policy,
        'survival_mode_exit_blockers': list(ctx.survival_mode_exit_blockers),
        'survival_mode_stable_ready_runs': ctx.survival_mode_stable_ready_runs,
        'survival_mode_stable_required_runs': ctx.survival_mode_stable_required_runs,
        'survival_mode_manual_clear_required': ctx.survival_mode_manual_clear_required,
        'survival_mode_config_changed_away': ctx.survival_mode_config_changed_away,
        'survival_mode_last_exit_at': ctx.survival_mode_last_exit_at,
        'survival_mode_last_exit_reason': ctx.survival_mode_last_exit_reason,
        'survival_mode_last_exit_kind': ctx.survival_mode_last_exit_kind,
        'survival_mode_last_exit_summary': ctx.survival_mode_last_exit_summary,
    }
