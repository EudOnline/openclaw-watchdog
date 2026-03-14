from __future__ import annotations

import json
from pathlib import Path


def sibling_json_path(path: Path) -> Path:
    return path.with_suffix('.json')


def _default_run_state(*, stable_required_runs: int) -> dict[str, object]:
    return {
        'last_status': 'unknown',
        'last_success_summary': '',
        'last_run_started_at': '',
        'last_run_finished_at': '',
        'last_run_duration_ms': 0,
        'last_success_at': '',
        'last_recovered_at': '',
        'last_failed_at': '',
        'last_degraded_at': '',
        'last_backup_result': 'not-run',
        'last_backup_at': '',
        'last_rollback_at': '',
        'last_rollback_summary_archive_file': '',
        'rollback_candidate_used': '',
        'rollback_reason': '',
        'config_drift_detected': False,
        'last_service_probe_at': '',
        'last_service_probe_result': 'not-run',
        'last_service_probe_summary': '',
        'last_service_probe_rc': 0,
        'service_probe_failures': 0,
        'current_mode': 'normal',
        'health_level': 'unknown',
        'survival_mode_active': False,
        'survival_mode_reason': '',
        'survival_mode_since': '',
        'survival_mode_summary': '',
        'survival_mode_actions': [],
        'survival_mode_disabled_features': [],
        'survival_mode_config_file': '',
        'survival_mode_sticky': False,
        'survival_mode_sticky_reason': '',
        'survival_mode_exit_ready': False,
        'survival_mode_exit_policy': 'none',
        'survival_mode_exit_blockers': [],
        'survival_mode_stable_ready_runs': 0,
        'survival_mode_stable_required_runs': stable_required_runs,
        'survival_mode_manual_clear_required': False,
        'survival_mode_config_changed_away': False,
        'survival_mode_last_exit_at': '',
        'survival_mode_last_exit_reason': '',
        'survival_mode_last_exit_kind': '',
        'survival_mode_last_exit_summary': '',
        'conversation_ready': False,
        'minimal_usable_ready': False,
        'conversation_status': 'down',
        'conversation_probe_summary': '',
        'last_recovery_strategy': 'none',
        'last_recovery_path': 'none',
        'last_recovery_action_count': 0,
        'last_recovery_restored_conversation': False,
        'rescue_attempt_count': 0,
        'rescue_executor_selected': '',
        'rescue_plan_generated': False,
        'rescue_plan_source': '',
        'rescue_plan_id': '',
        'rescue_plan_status': 'not-run',
        'rescue_tier': 'none',
        'case_ingest_result': 'not-run',
        'candidate_rule_status': 'none',
        'rescue_attempt_order': [],
        'rescue_rejected_executors': [],
        'rescue_learning_summary': 'not-run / none',
        'rescue_mutation_scope': [],
        'last_good_validated_at': '',
        'last_good_generation_id': '',
        'last_good_generation_count': 0,
        'drift_scope': [],
        'drift_since_last_good': '',
        'drift_summary': '',
        'guard_manifest_file': '',
        'guard_last_operation': '',
        'guard_last_phase': '',
        'guard_last_time': '',
        'guard_last_summary': '',
        'current_incident_id': '',
        'current_incident_state': '',
        'current_incident_age_seconds': 0,
    }


def read_run_state(run_state_file: Path, *, stable_required_runs: int, guard_manifest_file: Path | None = None) -> dict[str, object]:
    default = _default_run_state(stable_required_runs=stable_required_runs)
    if guard_manifest_file is not None:
        default['guard_manifest_file'] = str(guard_manifest_file)
    try:
        data = json.loads(run_state_file.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            default.update(data)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return default


def write_run_state(
    run_state_file: Path,
    updates: dict[str, object],
    *,
    stable_required_runs: int,
    guard_manifest_file: Path | None = None,
) -> dict[str, object]:
    state = read_run_state(
        run_state_file,
        stable_required_runs=stable_required_runs,
        guard_manifest_file=guard_manifest_file,
    )
    state.update(updates)
    run_state_file.parent.mkdir(parents=True, exist_ok=True)
    run_state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return state


def append_event_history(history_file: Path, event_payload: dict[str, object], *, keep: int) -> None:
    lines: list[str] = []
    if history_file.exists():
        lines = [line for line in history_file.read_text(encoding='utf-8').splitlines() if line.strip()]
    lines.append(json.dumps(event_payload, ensure_ascii=False, sort_keys=True))
    history_file.write_text('\n'.join(lines[-max(1, keep):]) + '\n', encoding='utf-8')


def read_event_history(history_file: Path, *, limit: int | None = None) -> list[dict[str, object]]:
    if not history_file.exists():
        return []
    items: list[dict[str, object]] = []
    for line in history_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    if limit is not None and limit > 0:
        return items[-limit:]
    return items
