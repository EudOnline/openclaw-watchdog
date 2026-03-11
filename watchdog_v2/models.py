from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _as_str(value: object, default: str = '') -> str:
    if value is None:
        return default
    return str(value)


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


@dataclass(eq=True)
class ProbeSnapshot:
    service_active: bool = False
    process_layer_healthy: bool = False
    service_layer_healthy: bool = False
    conversation_ready: bool = False
    minimal_usable_ready: bool = False
    conversation_status: str = 'down'
    service_probe_summary: str = 'n/a'
    conversation_probe_summary: str = 'n/a'

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> 'ProbeSnapshot':
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            service_active=_as_bool(raw.get('service_active', False)),
            process_layer_healthy=_as_bool(raw.get('process_layer_healthy', False)),
            service_layer_healthy=_as_bool(raw.get('service_layer_healthy', False)),
            conversation_ready=_as_bool(raw.get('conversation_ready', False)),
            minimal_usable_ready=_as_bool(raw.get('minimal_usable_ready', False)),
            conversation_status=_as_str(raw.get('conversation_status', 'down'), 'down') or 'down',
            service_probe_summary=_as_str(raw.get('service_probe_summary', 'n/a'), 'n/a') or 'n/a',
            conversation_probe_summary=_as_str(raw.get('conversation_probe_summary', 'n/a'), 'n/a') or 'n/a',
        )

    def to_dict(self) -> dict[str, object]:
        return {
            'service_active': self.service_active,
            'process_layer_healthy': self.process_layer_healthy,
            'service_layer_healthy': self.service_layer_healthy,
            'conversation_ready': self.conversation_ready,
            'minimal_usable_ready': self.minimal_usable_ready,
            'conversation_status': self.conversation_status,
            'service_probe_summary': self.service_probe_summary,
            'conversation_probe_summary': self.conversation_probe_summary,
        }


@dataclass(eq=True)
class RunStateSnapshot:
    health_level: str = 'unknown'
    current_mode: str = 'unknown'
    conversation_ready: bool = False
    minimal_usable_ready: bool = False
    conversation_status: str = 'down'
    conversation_probe_summary: str = ''
    last_recovery_strategy: str = 'none'
    last_recovery_path: str = 'none'
    last_recovery_action_count: int = 0
    last_recovery_restored_conversation: bool = False
    rescue_attempt_count: int = 0
    rescue_executor_selected: str = ''
    rescue_plan_generated: bool = False
    rescue_plan_source: str = ''
    rescue_plan_id: str = ''
    rescue_plan_status: str = 'not-run'
    rescue_tier: str = 'none'
    case_ingest_result: str = 'not-run'
    candidate_rule_status: str = 'none'
    rescue_attempt_order: list[str] = field(default_factory=list)
    rescue_rejected_executors: list[str] = field(default_factory=list)
    rescue_learning_summary: str = 'not-run / none'
    rescue_mutation_scope: list[str] = field(default_factory=list)
    last_good_validated_at: str = ''
    last_good_generation_id: str = ''
    last_good_generation_count: int = 0
    rollback_candidate_used: str = ''
    rollback_reason: str = ''
    config_drift_detected: bool = False
    drift_scope: list[str] = field(default_factory=list)
    drift_since_last_good: str = ''
    drift_summary: str = ''
    guard_manifest_file: str = ''
    guard_last_operation: str = ''
    guard_last_phase: str = ''
    guard_last_time: str = ''
    guard_last_summary: str = ''
    current_incident_id: str = ''
    current_incident_state: str = ''
    current_incident_age_seconds: int = 0

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> 'RunStateSnapshot':
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            health_level=_as_str(raw.get('health_level', 'unknown'), 'unknown') or 'unknown',
            current_mode=_as_str(raw.get('current_mode', 'unknown'), 'unknown') or 'unknown',
            conversation_ready=_as_bool(raw.get('conversation_ready', False)),
            minimal_usable_ready=_as_bool(raw.get('minimal_usable_ready', False)),
            conversation_status=_as_str(raw.get('conversation_status', 'down'), 'down') or 'down',
            conversation_probe_summary=_as_str(raw.get('conversation_probe_summary', ''), ''),
            last_recovery_strategy=_as_str(raw.get('last_recovery_strategy', 'none'), 'none') or 'none',
            last_recovery_path=_as_str(raw.get('last_recovery_path', 'none'), 'none') or 'none',
            last_recovery_action_count=_as_int(raw.get('last_recovery_action_count', 0)),
            last_recovery_restored_conversation=_as_bool(raw.get('last_recovery_restored_conversation', False)),
            rescue_attempt_count=_as_int(raw.get('rescue_attempt_count', 0)),
            rescue_executor_selected=_as_str(raw.get('rescue_executor_selected', ''), ''),
            rescue_plan_generated=_as_bool(raw.get('rescue_plan_generated', False)),
            rescue_plan_source=_as_str(raw.get('rescue_plan_source', ''), ''),
            rescue_plan_id=_as_str(raw.get('rescue_plan_id', ''), ''),
            rescue_plan_status=_as_str(raw.get('rescue_plan_status', 'not-run'), 'not-run') or 'not-run',
            rescue_tier=_as_str(raw.get('rescue_tier', 'none'), 'none') or 'none',
            case_ingest_result=_as_str(raw.get('case_ingest_result', 'not-run'), 'not-run') or 'not-run',
            candidate_rule_status=_as_str(raw.get('candidate_rule_status', 'none'), 'none') or 'none',
            rescue_attempt_order=_as_str_list(raw.get('rescue_attempt_order', [])),
            rescue_rejected_executors=_as_str_list(raw.get('rescue_rejected_executors', [])),
            rescue_learning_summary=_as_str(raw.get('rescue_learning_summary', 'not-run / none'), 'not-run / none') or 'not-run / none',
            rescue_mutation_scope=_as_str_list(raw.get('rescue_mutation_scope', [])),
            last_good_validated_at=_as_str(raw.get('last_good_validated_at', ''), ''),
            last_good_generation_id=_as_str(raw.get('last_good_generation_id', ''), ''),
            last_good_generation_count=_as_int(raw.get('last_good_generation_count', 0)),
            rollback_candidate_used=_as_str(raw.get('rollback_candidate_used', ''), ''),
            rollback_reason=_as_str(raw.get('rollback_reason', ''), ''),
            config_drift_detected=_as_bool(raw.get('config_drift_detected', False)),
            drift_scope=_as_str_list(raw.get('drift_scope', [])),
            drift_since_last_good=_as_str(raw.get('drift_since_last_good', ''), ''),
            drift_summary=_as_str(raw.get('drift_summary', ''), ''),
            guard_manifest_file=_as_str(raw.get('guard_manifest_file', ''), ''),
            guard_last_operation=_as_str(raw.get('guard_last_operation', ''), ''),
            guard_last_phase=_as_str(raw.get('guard_last_phase', ''), ''),
            guard_last_time=_as_str(raw.get('guard_last_time', ''), ''),
            guard_last_summary=_as_str(raw.get('guard_last_summary', ''), ''),
            current_incident_id=_as_str(raw.get('current_incident_id', ''), ''),
            current_incident_state=_as_str(raw.get('current_incident_state', ''), ''),
            current_incident_age_seconds=_as_int(raw.get('current_incident_age_seconds', 0)),
        )


    def to_dict(self) -> dict[str, object]:
        return {
            'health_level': self.health_level,
            'current_mode': self.current_mode,
            'conversation_ready': self.conversation_ready,
            'minimal_usable_ready': self.minimal_usable_ready,
            'conversation_status': self.conversation_status,
            'conversation_probe_summary': self.conversation_probe_summary,
            'last_recovery_strategy': self.last_recovery_strategy,
            'last_recovery_path': self.last_recovery_path,
            'last_recovery_action_count': self.last_recovery_action_count,
            'last_recovery_restored_conversation': self.last_recovery_restored_conversation,
            'rescue_attempt_count': self.rescue_attempt_count,
            'rescue_executor_selected': self.rescue_executor_selected,
            'rescue_plan_generated': self.rescue_plan_generated,
            'rescue_plan_source': self.rescue_plan_source,
            'rescue_plan_id': self.rescue_plan_id,
            'rescue_plan_status': self.rescue_plan_status,
            'rescue_tier': self.rescue_tier,
            'case_ingest_result': self.case_ingest_result,
            'candidate_rule_status': self.candidate_rule_status,
            'rescue_attempt_order': list(self.rescue_attempt_order),
            'rescue_rejected_executors': list(self.rescue_rejected_executors),
            'rescue_learning_summary': self.rescue_learning_summary,
            'rescue_mutation_scope': list(self.rescue_mutation_scope),
            'last_good_validated_at': self.last_good_validated_at,
            'last_good_generation_id': self.last_good_generation_id,
            'last_good_generation_count': self.last_good_generation_count,
            'rollback_candidate_used': self.rollback_candidate_used,
            'rollback_reason': self.rollback_reason,
            'config_drift_detected': self.config_drift_detected,
            'drift_scope': list(self.drift_scope),
            'drift_since_last_good': self.drift_since_last_good,
            'drift_summary': self.drift_summary,
            'guard_manifest_file': self.guard_manifest_file,
            'guard_last_operation': self.guard_last_operation,
            'guard_last_phase': self.guard_last_phase,
            'guard_last_time': self.guard_last_time,
            'guard_last_summary': self.guard_last_summary,
            'current_incident_id': self.current_incident_id,
            'current_incident_state': self.current_incident_state,
            'current_incident_age_seconds': self.current_incident_age_seconds,
        }


@dataclass(eq=True)
class IncidentSummary:
    incident_id: str = ''
    state: str = 'unknown'
    health_level: str = 'unknown'
    owner: str = ''
    acknowledged: bool = False
    notes_count: int = 0
    summary: str = ''
    latest_note: str = ''
    attention_summary: str = ''
    created_at: str = ''
    resolved_at: str = ''
    conversation_status: str = 'down'
    latest_note_by: str = ''
    latest_note_at: str = ''

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> 'IncidentSummary':
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            incident_id=_as_str(raw.get('incident_id', ''), ''),
            state=_as_str(raw.get('state', 'unknown'), 'unknown') or 'unknown',
            health_level=_as_str(raw.get('health_level', 'unknown'), 'unknown') or 'unknown',
            owner=_as_str(raw.get('owner', ''), ''),
            acknowledged=_as_bool(raw.get('acknowledged', False)),
            notes_count=_as_int(raw.get('notes_count', 0)),
            summary=_as_str(raw.get('summary', ''), ''),
            latest_note=_as_str(raw.get('latest_note', ''), ''),
            attention_summary=_as_str(raw.get('attention_summary', ''), ''),
            created_at=_as_str(raw.get('created_at', ''), ''),
            resolved_at=_as_str(raw.get('resolved_at', ''), ''),
            conversation_status=_as_str(raw.get('conversation_status', 'down'), 'down') or 'down',
            latest_note_by=_as_str(raw.get('latest_note_by', ''), ''),
            latest_note_at=_as_str(raw.get('latest_note_at', ''), ''),
        )


    def to_dict(self) -> dict[str, object]:
        return {
            'incident_id': self.incident_id,
            'state': self.state,
            'health_level': self.health_level,
            'owner': self.owner,
            'acknowledged': self.acknowledged,
            'notes_count': self.notes_count,
            'summary': self.summary,
            'latest_note': self.latest_note,
            'attention_summary': self.attention_summary,
            'created_at': self.created_at,
            'resolved_at': self.resolved_at,
            'conversation_status': self.conversation_status,
            'latest_note_by': self.latest_note_by,
            'latest_note_at': self.latest_note_at,
        }


@dataclass(eq=True)
class BootstrapSummary:
    state: str = 'unknown'
    summary: str = ''
    exit_code: int = 0
    dry_run: bool = False
    default_channels: list[str] = field(default_factory=lambda: ['qqbot', 'feishu'])
    flow: list[str] = field(
        default_factory=lambda: [
            'detect-opencode',
            'detect-codex',
            'detect-claude-code',
            'detect-gemini-cli',
            'detect-litellm',
            'detect-openclaw',
            'inspect-qq-plugin',
            'inspect-openclaw-channel-config',
            'scan-feishu-runtime-markers',
        ]
    )
    executors: dict[str, Any] = field(default_factory=dict)
    opencode: dict[str, Any] = field(default_factory=lambda: {'config': {}})
    codex: dict[str, Any] = field(default_factory=dict)
    openclaw: dict[str, Any] = field(default_factory=dict)
    qq_plugin: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    feishu_runtime: dict[str, Any] = field(default_factory=dict)
    next_steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    backup_files: list[str] = field(default_factory=list)

    @classmethod
    def initial(cls, *, config_path: str, dry_run: bool) -> 'BootstrapSummary':
        return cls(
            dry_run=dry_run,
            executors={},
            opencode={'config': {}},
            qq_plugin={'package': '@sliverp/qqbot@latest', 'command': 'openclaw plugins install @sliverp/qqbot@latest'},
            config={'path': config_path},
        )

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> 'BootstrapSummary':
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            state=_as_str(raw.get('state', 'unknown'), 'unknown') or 'unknown',
            summary=_as_str(raw.get('summary', ''), ''),
            exit_code=_as_int(raw.get('exit_code', 0)),
            dry_run=_as_bool(raw.get('dry_run', False)),
            default_channels=_as_str_list(raw.get('default_channels', ['qqbot', 'feishu'])) or ['qqbot', 'feishu'],
            flow=_as_str_list(raw.get('flow', [])) or cls().flow,
            executors=dict(raw.get('executors', {})) if isinstance(raw.get('executors', {}), dict) else {},
            opencode=dict(raw.get('opencode', {})) if isinstance(raw.get('opencode', {}), dict) else {'config': {}},
            codex=dict(raw.get('codex', {})) if isinstance(raw.get('codex', {}), dict) else {},
            openclaw=dict(raw.get('openclaw', {})) if isinstance(raw.get('openclaw', {}), dict) else {},
            qq_plugin=dict(raw.get('qq_plugin', {})) if isinstance(raw.get('qq_plugin', {}), dict) else {},
            config=dict(raw.get('config', {})) if isinstance(raw.get('config', {}), dict) else {},
            feishu_runtime=dict(raw.get('feishu_runtime', {})) if isinstance(raw.get('feishu_runtime', {}), dict) else {},
            next_steps=_as_str_list(raw.get('next_steps', [])),
            warnings=_as_str_list(raw.get('warnings', [])),
            files_changed=_as_str_list(raw.get('files_changed', [])),
            backup_files=_as_str_list(raw.get('backup_files', [])),
        )

    def to_dict(self) -> dict[str, object]:
        payload = {
            'state': self.state,
            'summary': self.summary,
            'exit_code': self.exit_code,
            'dry_run': self.dry_run,
            'default_channels': list(self.default_channels),
            'flow': list(self.flow),
            'executors': dict(self.executors),
            'opencode': dict(self.opencode),
            'codex': dict(self.codex),
            'openclaw': dict(self.openclaw),
            'qq_plugin': dict(self.qq_plugin),
            'config': dict(self.config),
            'feishu_runtime': dict(self.feishu_runtime),
            'next_steps': list(self.next_steps),
            'warnings': list(self.warnings),
            'files_changed': list(self.files_changed),
            'backup_files': list(self.backup_files),
        }
        return payload
