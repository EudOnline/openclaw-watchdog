from __future__ import annotations

from typing import Any


_OPERATOR_SNAPSHOT_DEFAULTS: dict[str, object] = {
    'conversation_ready': False,
    'minimal_usable_ready': False,
    'conversation_status': 'down',
    'conversation_probe_summary': '',
    'model_http_error_count': 0,
    'model_http_error_latest_at': '',
    'model_http_error_latest_status': 0,
    'model_failover_last_applied_at': '',
    'model_failover_last_from_model': '',
    'model_failover_last_to_model': '',
    'model_failover_last_status': 'not-run',
    'model_failover_last_summary': '',
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
    'rollback_candidate_used': '',
    'rollback_reason': '',
    'config_drift_detected': False,
    'drift_scope': [],
    'drift_since_last_good': '',
    'drift_summary': '',
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
    'survival_mode_stable_required_runs': 1,
    'survival_mode_manual_clear_required': False,
    'survival_mode_config_changed_away': False,
    'survival_mode_last_exit_at': '',
    'survival_mode_last_exit_reason': '',
    'survival_mode_last_exit_kind': '',
    'survival_mode_last_exit_summary': '',
    'last_good_validated_at': '',
    'last_good_generation_id': '',
    'last_good_generation_count': 0,
    'guard_manifest_file': '',
    'guard_last_operation': '',
    'guard_last_phase': '',
    'guard_last_time': '',
    'guard_last_summary': '',
}

OPERATOR_SNAPSHOT_KEYS = frozenset(_OPERATOR_SNAPSHOT_DEFAULTS.keys())


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    return []


def build_operator_snapshot(
    payload: dict[str, Any] | None,
    *,
    stable_required_runs: int = 1,
    guard_manifest_file: str = '',
) -> dict[str, object]:
    source = payload if isinstance(payload, dict) else {}
    defaults = dict(_OPERATOR_SNAPSHOT_DEFAULTS)
    defaults['survival_mode_stable_required_runs'] = max(1, int(stable_required_runs or 1))
    defaults['guard_manifest_file'] = str(guard_manifest_file or source.get('guard_manifest_file', '') or '')
    snapshot: dict[str, object] = {}
    for key, default in defaults.items():
        value = source.get(key, default)
        if isinstance(default, list):
            snapshot[key] = _as_list(value)
        elif isinstance(default, bool):
            snapshot[key] = bool(value)
        elif isinstance(default, int):
            snapshot[key] = int(value or 0)
        else:
            snapshot[key] = str(value or '') if isinstance(default, str) else value
    return snapshot


def to_payload(snapshot: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key in OPERATOR_SNAPSHOT_KEYS:
        value = snapshot.get(key)
        normalized[key] = list(value) if isinstance(value, list) else value
    return normalized


def list_text(value: object, *, joiner: str, fallback: str = 'none') -> str:
    if isinstance(value, list) and value:
        rendered = joiner.join(str(item) for item in value if str(item))
        return rendered or fallback
    return fallback
