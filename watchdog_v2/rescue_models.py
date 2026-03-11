from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_ACTIONS: tuple[str, ...] = (
    'restart_service',
    'run_doctor',
    'restore_last_good',
    'enter_survival_mode',
    'update_openclaw_config',
)

MUTATING_ACTIONS: tuple[str, ...] = (
    'restart_service',
    'restore_last_good',
    'enter_survival_mode',
    'update_openclaw_config',
)


@dataclass(eq=True)
class ConfigMutation:
    file: str
    path: str
    value: Any
    previous_value: Any = None
    reason: str = ''
    reversible: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> 'ConfigMutation':
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            file=str(raw.get('file', '') or ''),
            path=str(raw.get('path', '') or ''),
            value=raw.get('value'),
            previous_value=raw.get('previous_value'),
            reason=str(raw.get('reason', '') or ''),
            reversible=bool(raw.get('reversible', True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'file': self.file,
            'path': self.path,
            'value': self.value,
            'previous_value': self.previous_value,
            'reason': self.reason,
            'reversible': self.reversible,
        }


@dataclass(eq=True)
class RescueAction:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in ALLOWED_ACTIONS:
            raise ValueError(f'unsupported rescue action: {self.kind}')
        if not isinstance(self.params, dict):
            raise ValueError('action params must be a dict')

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> 'RescueAction':
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            kind=str(raw.get('kind', '') or ''),
            params=dict(raw.get('params', {})) if isinstance(raw.get('params', {}), dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'kind': self.kind,
            'params': dict(self.params),
        }


@dataclass(eq=True)
class RescueContext:
    incident_id: str = ''
    health_level: str = 'unknown'
    conversation_status: str = 'down'
    available_executors: tuple[str, ...] = field(default_factory=tuple)
    editable_paths: tuple[str, ...] = field(default_factory=tuple)
    editable_keys: tuple[str, ...] = field(default_factory=tuple)
    probe: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> 'RescueContext':
        raw = payload if isinstance(payload, dict) else {}
        executors = raw.get('available_executors', [])
        paths = raw.get('editable_paths', [])
        keys = raw.get('editable_keys', [])
        return cls(
            incident_id=str(raw.get('incident_id', '') or ''),
            health_level=str(raw.get('health_level', 'unknown') or 'unknown'),
            conversation_status=str(raw.get('conversation_status', 'down') or 'down'),
            available_executors=tuple(str(item) for item in executors) if isinstance(executors, (list, tuple)) else tuple(),
            editable_paths=tuple(str(item) for item in paths) if isinstance(paths, (list, tuple)) else tuple(),
            editable_keys=tuple(str(item) for item in keys) if isinstance(keys, (list, tuple)) else tuple(),
            probe=dict(raw.get('probe', {})) if isinstance(raw.get('probe', {}), dict) else {},
            metadata=dict(raw.get('metadata', {})) if isinstance(raw.get('metadata', {}), dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'incident_id': self.incident_id,
            'health_level': self.health_level,
            'conversation_status': self.conversation_status,
            'available_executors': list(self.available_executors),
            'editable_paths': list(self.editable_paths),
            'editable_keys': list(self.editable_keys),
            'probe': dict(self.probe),
            'metadata': dict(self.metadata),
        }


@dataclass(eq=True)
class RescuePlan:
    plan_id: str
    diagnosis: str
    actions: list[RescueAction] = field(default_factory=list)
    validations: list[str] = field(default_factory=list)
    rollback_strategy: str = 'auto'
    risk_level: str = 'medium'
    rationale: str = ''
    editable_paths: tuple[str, ...] = field(default_factory=tuple)
    editable_keys: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.actions = [action if isinstance(action, RescueAction) else RescueAction.from_dict(action) for action in self.actions]
        self.validations = [str(item) for item in self.validations if str(item)]
        if any(action.kind in MUTATING_ACTIONS for action in self.actions) and not self.validations:
            raise ValueError('mutating rescue plans require validation steps')

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> 'RescuePlan':
        raw = payload if isinstance(payload, dict) else {}
        actions = raw.get('actions', [])
        validations = raw.get('validations', [])
        paths = raw.get('editable_paths', [])
        keys = raw.get('editable_keys', [])
        return cls(
            plan_id=str(raw.get('plan_id', '') or ''),
            diagnosis=str(raw.get('diagnosis', '') or ''),
            actions=[RescueAction.from_dict(item) if isinstance(item, dict) else RescueAction(kind=str(item), params={}) for item in actions] if isinstance(actions, list) else [],
            validations=[str(item) for item in validations] if isinstance(validations, list) else [],
            rollback_strategy=str(raw.get('rollback_strategy', 'auto') or 'auto'),
            risk_level=str(raw.get('risk_level', 'medium') or 'medium'),
            rationale=str(raw.get('rationale', '') or ''),
            editable_paths=tuple(str(item) for item in paths) if isinstance(paths, (list, tuple)) else tuple(),
            editable_keys=tuple(str(item) for item in keys) if isinstance(keys, (list, tuple)) else tuple(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'plan_id': self.plan_id,
            'diagnosis': self.diagnosis,
            'actions': [action.to_dict() for action in self.actions],
            'validations': list(self.validations),
            'rollback_strategy': self.rollback_strategy,
            'risk_level': self.risk_level,
            'rationale': self.rationale,
            'editable_paths': list(self.editable_paths),
            'editable_keys': list(self.editable_keys),
        }


@dataclass(eq=True)
class RescueAttempt:
    executor: str = ''
    status: str = 'unknown'
    error: str = ''
    plan_id: str = ''

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> 'RescueAttempt':
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            executor=str(raw.get('executor', '') or ''),
            status=str(raw.get('status', 'unknown') or 'unknown'),
            error=str(raw.get('error', '') or ''),
            plan_id=str(raw.get('plan_id', '') or ''),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'executor': self.executor,
            'status': self.status,
            'error': self.error,
            'plan_id': self.plan_id,
        }


@dataclass(eq=True)
class RescueResult:
    status: str = 'unknown'
    executor: str = ''
    plan_id: str = ''
    rollback_performed: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> 'RescueResult':
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            status=str(raw.get('status', 'unknown') or 'unknown'),
            executor=str(raw.get('executor', '') or ''),
            plan_id=str(raw.get('plan_id', '') or ''),
            rollback_performed=bool(raw.get('rollback_performed', False)),
            details=dict(raw.get('details', {})) if isinstance(raw.get('details', {}), dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.status,
            'executor': self.executor,
            'plan_id': self.plan_id,
            'rollback_performed': self.rollback_performed,
            'details': dict(self.details),
        }
