from __future__ import annotations

import json
import shutil

from openclaw_watchdog import guard_runtime
from openclaw_watchdog import survival_policy_runtime
from openclaw_watchdog import survival_state_runtime


def clear_survival_mode(engine, *, reason: str, exit_kind: str = 'automatic') -> dict[str, object]:
    previous = survival_state_runtime.read_survival_state(engine)
    exited_at = engine.now_iso()
    state = survival_state_runtime.default_state(engine)
    state.update(
        {
            'active': False,
            'required_channels': [],
            'config_path': '',
            'source_config_path': '',
            'source_config_fingerprint': '',
            'applied_config_fingerprint': '',
            'previous_config_backup_path': '',
            'exited_at': exited_at,
            'exit_reason': reason,
            'last_exit_at': exited_at,
            'last_exit_reason': reason,
            'last_exit_kind': exit_kind,
            'last_exit_summary': str(previous.get('summary', '') or ''),
        }
    )
    state = survival_state_runtime.write_survival_state(engine, state)
    survival_state_runtime.apply_state_to_engine(engine, state)
    engine.log('INFO', f'survival mode cleared kind={exit_kind} reason={reason}')
    return state


def sync_survival_mode(engine, *, probe: dict[str, object], config_invalid: bool) -> dict[str, object]:
    state = survival_state_runtime.read_survival_state(engine)
    if not bool(state.get('active', False)):
        survival_state_runtime.apply_state_to_engine(engine, state)
        return state

    state.update(
        survival_policy_runtime.sync_state_updates(
            engine,
            state=state,
            probe=probe,
            config_invalid=config_invalid,
        )
    )

    if bool(state.get('exit_ready', False)) and bool(state.get('config_changed_away', False)):
        return clear_survival_mode(engine, reason='stable-ready-config-recovered', exit_kind='automatic')

    state = survival_state_runtime.write_survival_state(engine, state)
    survival_state_runtime.apply_state_to_engine(engine, state)
    return state


def enter_survival_mode(engine, *, reason: str) -> dict[str, object]:
    if not engine.config.watchdog_enable_survival_mode:
        return {'applied': False, 'detail': 'disabled'}

    state = survival_state_runtime.read_survival_state(engine)
    if bool(state.get('active', False)):
        survival_state_runtime.apply_state_to_engine(engine, state)
        return {'applied': False, 'detail': 'already-active', 'state': state}

    plan = survival_policy_runtime.build_survival_plan(engine, reason=reason)
    if plan is None:
        return {'applied': False, 'detail': 'no-usable-config-basis'}

    rendered = json.dumps(plan['config'], ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    json.loads(rendered)

    guard_before = guard_runtime.protected_paths_snapshot(engine.config)
    guard_runtime.record_guard_event(
        engine.config,
        operation='survival-mode-apply',
        phase='before',
        before=guard_before,
        context={
            'reason': reason,
            'source_config_path': plan.get('source_config_path', ''),
        },
    )

    previous_backup_path = ''
    if engine.config.openclaw_config.exists():
        backup_path = engine.config.watchdog_rollback_archive_dir / f"survival-preapply.{engine.now_iso().replace(':', '').replace('+', '_')}.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(engine.config.openclaw_config, backup_path)
        previous_backup_path = str(backup_path)

    engine.config.watchdog_survival_config_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_survival_config_file.write_text(rendered, encoding='utf-8')
    engine.config.openclaw_config.parent.mkdir(parents=True, exist_ok=True)
    engine.config.openclaw_config.write_text(rendered, encoding='utf-8')

    guard_after = guard_runtime.protected_paths_snapshot(engine.config)
    guard_runtime.record_guard_event(
        engine.config,
        operation='survival-mode-apply',
        phase='after',
        before=guard_before,
        after=guard_after,
        validation='survival-config-json-valid',
        context={
            'reason': reason,
            'summary': plan.get('summary', ''),
            'required_channels': list(plan.get('required_channels', [])),
        },
    )

    stable_required = survival_state_runtime.stable_required_runs(engine)
    state = survival_state_runtime.write_survival_state(
        engine,
        {
            'active': True,
            'entered_at': engine.now_iso(),
            'exited_at': '',
            'exit_reason': '',
            'reason': reason,
            'summary': str(plan.get('summary', '') or ''),
            'actions': list(plan.get('actions', [])),
            'disabled_features': list(plan.get('disabled_features', [])),
            'required_channels': list(plan.get('required_channels', [])),
            'config_path': str(engine.config.watchdog_survival_config_file),
            'source_config_path': str(plan.get('source_config_path', '') or ''),
            'source_config_fingerprint': str(plan.get('source_config_fingerprint', '') or ''),
            'applied_config_fingerprint': guard_runtime.fingerprint_path(engine.config.openclaw_config),
            'previous_config_backup_path': previous_backup_path,
            'sticky': True,
            'sticky_reason': f'waiting for stable full-ready window 0/{stable_required}',
            'exit_ready': False,
            'exit_policy': 'manual-clear-or-reconfig',
            'exit_blockers': [f'waiting for stable full-ready window 0/{stable_required}'],
            'stable_ready_runs': 0,
            'stable_required_runs': stable_required,
            'stable_ready_since': '',
            'manual_clear_required': False,
            'config_changed_away': False,
            'last_exit_at': '',
            'last_exit_reason': '',
            'last_exit_kind': '',
            'last_exit_summary': '',
        },
    )
    survival_state_runtime.apply_state_to_engine(engine, state)
    engine.log(
        'WARN',
        f"survival mode activated reason={reason} summary={state.get('summary', '')} actions={'; '.join(engine.ctx.survival_mode_actions) or 'none'}",
    )
    return {'applied': True, 'detail': 'applied', 'state': state}
