from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_watchdog import learning_signatures
from openclaw_watchdog.rescue_models import RescueContext, RescuePlan


def _normalized_key_path(value: str) -> str:
    parts = [part.strip() for part in str(value or '').split('.') if part.strip()]
    return '.'.join(parts)


def editable_paths(config) -> tuple[str, ...]:
    seen: set[str] = set()
    values: list[str] = []
    for item in getattr(config, 'watchdog_rescue_editable_paths', ()) or ():
        raw = str(item or '').strip()
        if raw and raw not in seen:
            seen.add(raw)
            values.append(raw)
    return tuple(values)


def editable_keys(config) -> tuple[str, ...]:
    seen: set[str] = set()
    values: list[str] = []
    for item in getattr(config, 'watchdog_rescue_editable_keys', ()) or ():
        normalized = _normalized_key_path(str(item or ''))
        if normalized and normalized not in seen:
            seen.add(normalized)
            values.append(normalized)
    return tuple(values)


def _compare_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def path_allowed(target: str | Path, allowed_paths: tuple[str, ...] | list[str] | None) -> bool:
    target_raw = str(target or '').strip()
    if not target_raw:
        return False
    resolved_target = _compare_path(target)
    for allowed in allowed_paths or ():
        allowed_raw = str(allowed or '').strip()
        if not allowed_raw:
            continue
        allowed_path = _compare_path(allowed_raw)
        if resolved_target == allowed_path:
            return True
        expanded_allowed = Path(allowed_raw).expanduser()
        if expanded_allowed.exists() and expanded_allowed.is_dir() and allowed_path in resolved_target.parents:
            return True
    return False


def key_allowed(dotted_path: str, allowed_keys: tuple[str, ...] | list[str] | None) -> bool:
    normalized = _normalized_key_path(dotted_path)
    if not normalized:
        return False
    for allowed in allowed_keys or ():
        allowed_key = _normalized_key_path(str(allowed or ''))
        if not allowed_key:
            continue
        if normalized == allowed_key or normalized.startswith(f'{allowed_key}.'):
            return True
    return False


def validate_action(
    action: dict[str, Any] | Any,
    *,
    allowed_paths: tuple[str, ...] | list[str] | None,
    allowed_keys: tuple[str, ...] | list[str] | None,
) -> None:
    kind = str(getattr(action, 'kind', '') or '').strip()
    if not kind and isinstance(action, dict):
        kind = str(action.get('kind', '') or '').strip()
    params = getattr(action, 'params', None)
    if not isinstance(params, dict):
        params = action.get('params', {}) if isinstance(action, dict) and isinstance(action.get('params', {}), dict) else {}
    if kind != 'update_openclaw_config':
        return
    target = str(params.get('file', '') or '').strip()
    dotted_path = _normalized_key_path(str(params.get('path', '') or ''))
    if not path_allowed(target, allowed_paths):
        raise PermissionError(f'rescue write not allowed for {Path(target).expanduser()}')
    if not key_allowed(dotted_path, allowed_keys):
        raise PermissionError(f'rescue key not allowed: {dotted_path}')


def validate_plan(context: RescueContext, plan: RescuePlan) -> None:
    for declared_path in plan.editable_paths:
        if not path_allowed(declared_path, context.editable_paths):
            raise PermissionError(f'plan editable path not allowed: {declared_path}')
    for declared_key in plan.editable_keys:
        if not key_allowed(declared_key, context.editable_keys):
            raise PermissionError(f'plan editable key not allowed: {declared_key}')
    for action in plan.actions:
        validate_action(
            action,
            allowed_paths=context.editable_paths,
            allowed_keys=context.editable_keys,
        )


def openclaw_policy_snapshot(config) -> dict[str, object]:
    return {
        'config_path': str(getattr(config, 'openclaw_config', '') or ''),
        'required_channels': list(getattr(config, 'watchdog_survival_required_channels', ()) or ()),
        'editable_paths': list(editable_paths(config)),
        'editable_keys': list(editable_keys(config)),
        'editable_path_policy': 'explicit-allowlist',
        'editable_key_policy': 'exact-or-descendant',
        'config_write_mode': 'atomic-json-replace',
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


def learned_rule_suppression_threshold() -> int:
    return 2


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
    normalized_signature = learning_signatures.normalized_failure_signature(metadata)
    failure_signature = normalized_signature or str(metadata.get('failure_signature', '') or '').strip() or 'unknown-failure'
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
