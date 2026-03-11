from __future__ import annotations

from typing import Any

from watchdog_v2.rescue_models import RescueContext


def openclaw_policy_snapshot(config) -> dict[str, object]:
    return {
        'config_path': str(getattr(config, 'openclaw_config', '') or ''),
        'required_channels': list(getattr(config, 'watchdog_survival_required_channels', ()) or ()),
        'editable_paths': list(getattr(config, 'watchdog_rescue_editable_paths', ()) or ()),
        'editable_keys': list(getattr(config, 'watchdog_rescue_editable_keys', ()) or ()),
    }


def mutation_scope(actions: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[str]:
    scope: list[str] = []
    for item in actions or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get('kind', '') or '').strip()
        if kind and kind not in scope:
            scope.append(kind)
    return scope


def confidence_label(*, evidence_count: int, risk_level: str) -> str:
    if risk_level == 'high':
        return 'review-required'
    if evidence_count >= 5:
        return 'high'
    if evidence_count >= 3:
        return 'medium'
    return 'low'


def heuristic_plan(context: RescueContext) -> dict[str, Any] | None:
    metadata = context.metadata if isinstance(context.metadata, dict) else {}
    failure_signature = str(metadata.get('failure_signature', '') or '').strip() or 'unknown-failure'
    recent_cases = metadata.get('recent_cases', []) if isinstance(metadata.get('recent_cases', []), list) else []
    rationale_parts = ['heuristic']
    if recent_cases:
        first_case = recent_cases[-1]
        if isinstance(first_case, dict) and first_case.get('case_id'):
            rationale_parts.append(f"recent-case:{first_case.get('case_id')}")

    if bool(metadata.get('config_invalid', False)) or failure_signature == 'config-invalid':
        return {
            'plan_id': f'heuristic-{failure_signature}-restore-last-good',
            'diagnosis': 'detected invalid OpenClaw configuration; restore the last known good snapshot',
            'actions': [{'kind': 'restore_last_good', 'params': {}}],
            'validations': ['minimal_usable_ready'],
            'rollback_strategy': 'auto',
            'risk_level': 'low',
            'rationale': ', '.join(rationale_parts + ['restore-last-good']),
        }

    if failure_signature == 'process-down' or not bool(metadata.get('service_active', True)) or not bool(metadata.get('process_layer_healthy', True)):
        return {
            'plan_id': f'heuristic-{failure_signature}-restart-service',
            'diagnosis': 'the OpenClaw process appears down; restart the gateway before broader mutation',
            'actions': [{'kind': 'restart_service', 'params': {}}],
            'validations': ['minimal_usable_ready'],
            'rollback_strategy': 'auto',
            'risk_level': 'low',
            'rationale': ', '.join(rationale_parts + ['restart-service']),
        }

    return None
