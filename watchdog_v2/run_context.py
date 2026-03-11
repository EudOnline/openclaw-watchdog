from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path


@dataclass
class RunContext:
    run_ts: str = ''
    rollback_summary: str = ''
    rollback_occurred: bool = False
    rollback_summary_archive_file: str = ''
    rollback_broken_config_file: str = ''
    rollback_candidate_used: str = ''
    rollback_reason: str = ''
    config_drift_detected: bool = False
    pre_repair_backup_result: str = 'not-run'
    consecutive_failures: int = 0
    recovery_steps: list[str] = field(default_factory=list)
    last_recovery_strategy: str = 'none'
    last_recovery_action_count: int = 0
    last_recovery_restored_conversation: bool = False
    last_good_validated_at: str = ''
    last_good_generation_id: str = ''
    last_good_generation_count: int = 0
    survival_mode_active: bool = False
    survival_mode_reason: str = ''
    survival_mode_since: str = ''
    survival_mode_summary: str = ''
    survival_mode_actions: list[str] = field(default_factory=list)
    survival_mode_disabled_features: list[str] = field(default_factory=list)
    survival_mode_config_file: str = ''
    survival_mode_sticky: bool = False
    survival_mode_sticky_reason: str = ''
    survival_mode_exit_ready: bool = False
    survival_mode_exit_policy: str = 'none'
    survival_mode_exit_blockers: list[str] = field(default_factory=list)
    survival_mode_stable_ready_runs: int = 0
    survival_mode_stable_required_runs: int = 0
    survival_mode_manual_clear_required: bool = False
    survival_mode_config_changed_away: bool = False
    survival_mode_last_exit_at: str = ''
    survival_mode_last_exit_reason: str = ''
    survival_mode_last_exit_kind: str = ''
    survival_mode_last_exit_summary: str = ''
    drift_scope: list[str] = field(default_factory=list)
    drift_since_last_good: str = ''
    drift_summary: str = ''
    latest_probe: dict[str, object] = field(default_factory=dict)
    incident_id: str = ''
    incident_dir: Path | None = None
    codex_prompt_file: Path | None = None
    codex_handoff_file: Path | None = None
    codex_runner_file: Path | None = None
    codex_run_log_file: Path | None = None
    codex_run_pid: str = ''
    codex_trigger_result: str = 'not-run'
    codex_autorun_ready: bool = False
    last_run_started_at: datetime | None = None
    last_run_finished_at: datetime | None = None
    opencode_fallback_handoff_file: Path | None = None
    opencode_fallback_runner_file: Path | None = None
    opencode_fallback_run_log_file: Path | None = None
    opencode_fallback_run_pid: str = ''
    opencode_fallback_trigger_result: str = 'not-run'

    @classmethod
    def initial(cls, *, stable_required_runs: int) -> 'RunContext':
        now = datetime.now().astimezone()
        return cls(
            run_ts=now.strftime('%F %T %Z'),
            survival_mode_stable_required_runs=max(1, int(stable_required_runs or 1)),
            last_run_started_at=now,
            last_run_finished_at=now,
        )


RUN_CONTEXT_FIELDS = frozenset(field_info.name for field_info in fields(RunContext))
