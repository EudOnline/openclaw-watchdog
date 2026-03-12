from __future__ import annotations

import difflib
import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import tempfile
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from watchdog_v2 import events as event_ops
from watchdog_v2 import health as health_ops
from watchdog_v2 import incident_service as incident_service_ops
from watchdog_v2 import incidents as incident_ops
from watchdog_v2 import learning_signatures
from watchdog_v2 import repair as repair_ops
from watchdog_v2 import reporting as reporting_ops
from watchdog_v2 import recovery_tracking
from watchdog_v2 import run_state_service
from watchdog_v2 import survival as survival_ops
from watchdog_v2.config import Config
from watchdog_v2.runtime import CommandResult, run_capture_to_file, run_command
from watchdog_v2 import state_store
from watchdog_v2.run_context import RunContext


@dataclass
class RunOutcome:
    exit_code: int
    state: str
    summary: str


class WatchdogEngine:
    def __init__(self, config: Config):
        self.config = config
        self.last_status_file = self.config.watchdog_state_dir / "last-status"
        self.run_state_file = self.config.watchdog_run_state_file
        self.incident_backup_marker = self.config.watchdog_state_dir / "incident-backup-done"
        self.current_incident_marker = self.config.watchdog_state_dir / "current-incident-id"
        self.tmpdir_obj: tempfile.TemporaryDirectory[str] | None = None
        self.tmpdir: Path | None = None
        self.lock_handle = None
        self.ctx = RunContext.initial(stable_required_runs=self.config.watchdog_survival_stable_ready_runs)
        self._prepare_state_dirs()

    def __enter__(self) -> "WatchdogEngine":
        self.tmpdir_obj = tempfile.TemporaryDirectory(prefix="openclaw-watchdog-")
        self.tmpdir = Path(self.tmpdir_obj.name)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release_lock()
        if self.tmpdir_obj is not None:
            self.tmpdir_obj.cleanup()

    def _prepare_state_dirs(self) -> None:
        self.config.watchdog_state_dir.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_rollback_archive_dir.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_incidents_dir.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_log_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_event_history_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_incident_index_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_last_report_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_last_metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_survival_config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_survival_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_guard_manifest_file.parent.mkdir(parents=True, exist_ok=True)
        self.run_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_log_file.touch(exist_ok=True)
        self.config.watchdog_event_history_file.touch(exist_ok=True)
        if not self.run_state_file.exists():
            self.write_run_state({})

    def acquire_lock(self) -> bool:
        self.config.watchdog_lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_handle = self.config.watchdog_lock_file.open("a+")
        try:
            fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def release_lock(self) -> None:
        if self.lock_handle is None:
            return
        try:
            fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.lock_handle.close()
        self.lock_handle = None

    def log(self, level: str, message: str) -> None:
        line = f"[{datetime.now().astimezone().strftime('%F %T %Z')}] [{level}] {message}\n"
        with self.config.watchdog_log_file.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def run_command(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
        cwd: Path | None = None,
        merge_stderr: bool = False,
        input_text: str | None = None,
    ) -> CommandResult:
        return run_command(args, timeout=timeout, cwd=cwd, merge_stderr=merge_stderr, input_text=input_text)

    def run_capture_to_file(self, args: list[str], destination: Path, *, timeout: int | None = None) -> None:
        run_capture_to_file(args, destination, timeout=timeout)

    def notify(self, message: str) -> None:
        if not self.config.watchdog_notify_channel or not self.config.watchdog_notify_target:
            return
        self.run_command(
            [
                "openclaw",
                "message",
                "send",
                "--account",
                self.config.watchdog_notify_account,
                "--channel",
                self.config.watchdog_notify_channel,
                "--target",
                self.config.watchdog_notify_target,
                "--message",
                message,
            ],
            timeout=self.config.watchdog_message_timeout_seconds,
        )

    def append_rollback_summary(self, text: str) -> str:
        if self.ctx.rollback_summary:
            return f"{text}\n\n回退摘要：\n{self.ctx.rollback_summary}"
        return text

    def reset_recovery_tracking(self) -> None:
        recovery_tracking.reset(
            self.ctx,
            stable_required_runs=self.config.watchdog_survival_stable_ready_runs,
        )

    def record_recovery_step(self, step: str, outcome: str, detail: str = "") -> None:
        recovery_tracking.record_step(self.ctx, step, outcome, detail)

    def recovery_path_text(self) -> str:
        return recovery_tracking.path_text(self.ctx)

    def finalize_recovery_tracking(self, *, strategy: str, restored_conversation: bool) -> None:
        recovery_tracking.finalize(
            self.ctx,
            strategy=strategy,
            restored_conversation=restored_conversation,
        )

    def read_failure_count(self) -> int:
        try:
            value = self.config.watchdog_failure_count_file.read_text(encoding="utf-8").strip()
            return int(value)
        except (FileNotFoundError, ValueError):
            return 0

    def write_failure_count(self, count: int) -> None:
        self.ctx.consecutive_failures = max(0, int(count))
        self.config.watchdog_failure_count_file.write_text(f"{self.ctx.consecutive_failures}", encoding="utf-8")

    def reset_failure_count(self) -> None:
        self.write_failure_count(0)

    def increment_failure_count(self) -> int:
        count = self.read_failure_count() + 1
        self.write_failure_count(count)
        return count

    def now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def read_run_state(self) -> dict[str, object]:
        default = {
            "service_probe_failures": 0,
            "last_run_started_at": "",
            "last_run_finished_at": "",
            "last_run_duration_ms": 0,
            "last_success_at": "",
            "last_recovered_at": "",
            "last_failed_at": "",
            "last_degraded_at": "",
            "last_backup_result": "not-run",
            "last_backup_at": "",
            "last_rollback_at": "",
            "last_rollback_summary_archive_file": "",
            "rollback_candidate_used": "",
            "rollback_reason": "",
            "config_drift_detected": False,
            "last_service_probe_at": "",
            "last_service_probe_result": "not-run",
            "last_service_probe_summary": "",
            "last_service_probe_rc": 0,
            "current_mode": "normal",
            "health_level": "unknown",
            "survival_mode_active": False,
            "survival_mode_reason": "",
            "survival_mode_since": "",
            "survival_mode_summary": "",
            "survival_mode_actions": [],
            "survival_mode_disabled_features": [],
            "survival_mode_config_file": "",
            "survival_mode_sticky": False,
            "survival_mode_sticky_reason": "",
            "survival_mode_exit_ready": False,
            "survival_mode_exit_policy": "none",
            "survival_mode_exit_blockers": [],
            "survival_mode_stable_ready_runs": 0,
            "survival_mode_stable_required_runs": self.config.watchdog_survival_stable_ready_runs,
            "survival_mode_manual_clear_required": False,
            "survival_mode_config_changed_away": False,
            "survival_mode_last_exit_at": "",
            "survival_mode_last_exit_reason": "",
            "survival_mode_last_exit_kind": "",
            "survival_mode_last_exit_summary": "",
            "conversation_ready": False,
            "minimal_usable_ready": False,
            "conversation_status": "down",
            "conversation_probe_summary": "",
            "last_recovery_strategy": "none",
            "last_recovery_path": "none",
            "last_recovery_action_count": 0,
            "last_recovery_restored_conversation": False,
            "rescue_attempt_count": 0,
            "rescue_executor_selected": "",
            "rescue_plan_generated": False,
            "rescue_plan_source": "",
            "rescue_plan_id": "",
            "rescue_plan_status": "not-run",
            "rescue_tier": "none",
            "case_ingest_result": "not-run",
            "candidate_rule_status": "none",
            "rescue_attempt_order": [],
            "rescue_rejected_executors": [],
            "rescue_learning_summary": "not-run / none",
            "rescue_mutation_scope": [],
            "last_good_validated_at": "",
            "last_good_generation_id": "",
            "last_good_generation_count": 0,
            "drift_scope": [],
            "drift_since_last_good": "",
            "drift_summary": "",
            "guard_manifest_file": str(self.config.watchdog_guard_manifest_file),
            "guard_last_operation": "",
            "guard_last_phase": "",
            "guard_last_time": "",
            "guard_last_summary": "",
            "current_incident_id": "",
            "current_incident_state": "",
            "current_incident_age_seconds": 0,
        }
        try:
            data = json.loads(self.run_state_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                default.update(data)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return default

    def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
        state = self.read_run_state()
        state.update(updates)
        self.run_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.run_state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return state

    def current_mode(self, *, maintenance: bool, degraded: bool = False, survival: bool = False) -> str:
        if maintenance:
            return "maintenance"
        if survival:
            return "survival"
        if degraded:
            return "degraded"
        return "normal"

    def incident_state_file(self, incident_dir: Path) -> Path:
        return incident_dir / "incident-state.json"

    def event_severity(self, status: str, health_level: str, summary: str) -> str:
        return event_ops.event_severity(status, health_level, summary)

    def event_human_summary(self, status: str, health_level: str, summary: str) -> str:
        return event_ops.event_human_summary(status, health_level, summary)

    def append_event_history(self, event_payload: dict[str, object]) -> None:
        state_store.append_event_history(
            self.config.watchdog_event_history_file,
            event_payload,
            keep=self.config.watchdog_event_history_limit,
        )

    def read_event_history(self, limit: int | None = None) -> list[dict[str, object]]:
        return state_store.read_event_history(self.config.watchdog_event_history_file, limit=limit)

    def event_time(self, event: dict[str, object]) -> datetime | None:
        raw = event.get("time")
        if not isinstance(raw, str) or not raw:
            return None
        local_tz = datetime.now().astimezone().tzinfo
        for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.astimezone() if dt.tzinfo else dt.replace(tzinfo=local_tz)
            except ValueError:
                continue
        if len(raw) >= 19:
            try:
                return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=local_tz)
            except ValueError:
                pass
        try:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=local_tz)
        except ValueError:
            return None

    def recent_event_stats(self, *, hours: int = 24) -> dict[str, object]:
        now = datetime.now().astimezone()
        cutoff = now - timedelta(hours=max(1, hours))
        events = self.read_event_history()
        window: list[dict[str, object]] = []
        for event in events:
            when = self.event_time(event)
            if when is None or when >= cutoff:
                window.append(event)
        counts = {
            "ok": 0,
            "info": 0,
            "warning": 0,
            "success": 0,
            "critical": 0,
            "healthy": 0,
            "degraded": 0,
            "recovered": 0,
            "failed": 0,
        }
        last_recovered_at = ""
        healthy_streak_start = ""
        last_nonhealthy_at = ""
        current_streak = 0
        max_streak = 0
        current_streak_duration_seconds = 0
        longest_healthy_gap_seconds = 0
        recovery_durations_seconds: list[int] = []
        failed_started_at: datetime | None = None
        previous_healthy_time: datetime | None = None
        for event in window:
            severity = str(event.get("severity", "info"))
            status = str(event.get("status", "unknown"))
            counts[severity] = counts.get(severity, 0) + 1
            counts[status] = counts.get(status, 0) + 1
            when = self.event_time(event)
            when_text = str(event.get("time", ""))
            if status == "failed" and when is not None and failed_started_at is None:
                failed_started_at = when
            elif status == "recovered" and when is not None:
                last_recovered_at = when_text
                if failed_started_at is not None:
                    recovery_durations_seconds.append(max(0, int((when - failed_started_at).total_seconds())))
                    failed_started_at = None
            if status == "healthy":
                if previous_healthy_time is not None and when is not None:
                    longest_healthy_gap_seconds = max(longest_healthy_gap_seconds, max(0, int((when - previous_healthy_time).total_seconds())))
                previous_healthy_time = when
                current_streak += 1
                if current_streak == 1:
                    healthy_streak_start = when_text
                if when is not None:
                    streak_start_dt = self.event_time({"time": healthy_streak_start}) if healthy_streak_start else None
                    if streak_start_dt is not None:
                        current_streak_duration_seconds = max(0, int((when - streak_start_dt).total_seconds()))
            else:
                current_streak = 0
                current_streak_duration_seconds = 0
                previous_healthy_time = None
                if when_text:
                    last_nonhealthy_at = when_text
                    healthy_streak_start = ""
            max_streak = max(max_streak, current_streak)
        last_recovery_duration_seconds = recovery_durations_seconds[-1] if recovery_durations_seconds else 0
        return {
            "window_hours": max(1, hours),
            "total": len(window),
            "counts": counts,
            "last_recovered_at": last_recovered_at,
            "last_nonhealthy_at": last_nonhealthy_at,
            "healthy_streak_events": current_streak,
            "healthy_streak_start": healthy_streak_start,
            "healthy_streak_best": max_streak,
            "healthy_streak_duration_seconds": current_streak_duration_seconds,
            "longest_healthy_gap_seconds": longest_healthy_gap_seconds,
            "last_recovery_duration_seconds": last_recovery_duration_seconds,
        }

    def _incident_bool(self, value: object) -> bool:
        return incident_service_ops.incident_bool(value)

    def read_json_dict(self, path: Path) -> dict[str, object]:
        return incident_service_ops.read_json_dict(path)

    def read_incident_state_payload(self, incident_dir: Path) -> dict[str, object]:
        return incident_service_ops.read_incident_state_payload(self, incident_dir)

    def read_incident_operator_summary_payload(self, incident_dir: Path) -> dict[str, object]:
        return incident_service_ops.read_incident_operator_summary_payload(self, incident_dir)

    def incident_operator_workflow_file(self, incident_dir: Path) -> Path:
        return incident_service_ops.incident_operator_workflow_file(self, incident_dir)

    def read_incident_operator_workflow_payload(self, incident_dir: Path) -> dict[str, object]:
        return incident_service_ops.read_incident_operator_workflow_payload(self, incident_dir)

    def incident_snapshot(self, incident_dir: Path) -> dict[str, object]:
        return incident_ops.incident_snapshot(self, incident_dir)

    def list_incident_snapshots(
        self,
        *,
        limit: int | None = None,
        state: str = "all",
        owner: str = "",
        acknowledged: bool | None = None,
        has_notes: bool | None = None,
        attention_needed: bool | None = None,
    ) -> list[dict[str, object]]:
        return incident_ops.list_incident_snapshots(self, limit=limit, state=state, owner=owner, acknowledged=acknowledged, has_notes=has_notes, attention_needed=attention_needed)

    def incident_detail_payload(self, incident_id: str) -> dict[str, object]:
        return incident_ops.incident_detail_payload(self, incident_id)

    def incident_timeline_payload(self, incident_id: str, *, limit: int | None = None) -> dict[str, object]:
        return incident_ops.incident_timeline_payload(self, incident_id, limit=limit)

    def current_incident_payload(self) -> dict[str, object]:
        return incident_ops.current_incident_payload(self)

    def incident_queue_payload(self, *, limit: int | None = None) -> dict[str, object]:
        return incident_ops.incident_queue_payload(self, limit=limit)

    def incident_operator_summary(self, *, summary: str, active: str, main_pid: str, listeners: str) -> str:
        return incident_service_ops.incident_operator_summary(self, summary=summary, active=active, main_pid=main_pid, listeners=listeners)

    def incident_index_entry(
        self,
        *,
        summary: str,
        active: str,
        main_pid: str,
        listeners: str,
        health_level: str | None = None,
        pre_repair_backup_result: str | None = None,
        rollback_occurred: bool | None = None,
        rollback_summary_archive_file: str | None = None,
        incident_id: str | None = None,
        incident_dir: Path | None = None,
    ) -> dict[str, object]:
        return incident_service_ops.incident_index_entry(
            self,
            summary=summary,
            active=active,
            main_pid=main_pid,
            listeners=listeners,
            health_level=health_level,
            pre_repair_backup_result=pre_repair_backup_result,
            rollback_occurred=rollback_occurred,
            rollback_summary_archive_file=rollback_summary_archive_file,
            incident_id=incident_id,
            incident_dir=incident_dir,
        )

    def update_incident_index(
        self,
        *,
        summary: str,
        active: str,
        main_pid: str,
        listeners: str,
        health_level: str | None = None,
        pre_repair_backup_result: str | None = None,
        rollback_occurred: bool | None = None,
        rollback_summary_archive_file: str | None = None,
        incident_id: str | None = None,
        incident_dir: Path | None = None,
    ) -> None:
        incident_service_ops.update_incident_index(
            self,
            summary=summary,
            active=active,
            main_pid=main_pid,
            listeners=listeners,
            health_level=health_level,
            pre_repair_backup_result=pre_repair_backup_result,
            rollback_occurred=rollback_occurred,
            rollback_summary_archive_file=rollback_summary_archive_file,
            incident_id=incident_id,
            incident_dir=incident_dir,
        )

    def read_incident_index(self, limit: int | None = None) -> list[dict[str, object]]:
        return incident_service_ops.read_incident_index(self, limit=limit)

    def refresh_current_incident_index(self, *, summary: str | None = None, health_level: str | None = None) -> None:
        incident_service_ops.refresh_current_incident_index(self, summary=summary, health_level=health_level)

    def refresh_incident_index_for(self, incident_id: str, *, summary: str | None = None, health_level: str | None = None) -> None:
        incident_ops.refresh_incident_index_for(self, incident_id, summary=summary, health_level=health_level)

    def update_incident_operator_workflow(
        self,
        incident_id: str,
        *,
        owner: str | None = None,
        acknowledged: bool | None = None,
        acknowledged_by: str | None = None,
        note_by: str | None = None,
        note_message: str | None = None,
        clear_owner: bool = False,
        clear_ack: bool = False,
    ) -> dict[str, object]:
        return incident_ops.update_incident_operator_workflow(
            self,
            incident_id,
            owner=owner,
            acknowledged=acknowledged,
            acknowledged_by=acknowledged_by,
            note_by=note_by,
            note_message=note_message,
            clear_owner=clear_owner,
            clear_ack=clear_ack,
        )

    def set_incident_owner(self, incident_id: str, owner: str) -> dict[str, object]:
        return incident_ops.set_incident_owner(self, incident_id, owner)

    def clear_incident_owner(self, incident_id: str) -> dict[str, object]:
        return incident_ops.clear_incident_owner(self, incident_id)

    def acknowledge_incident(self, incident_id: str, *, acknowledged_by: str, note: str = "") -> dict[str, object]:
        return incident_ops.acknowledge_incident(self, incident_id, acknowledged_by=acknowledged_by, note=note)

    def clear_incident_acknowledgement(self, incident_id: str) -> dict[str, object]:
        return incident_ops.clear_incident_acknowledgement(self, incident_id)

    def add_incident_note(self, incident_id: str, *, note_by: str, message: str) -> dict[str, object]:
        return incident_ops.add_incident_note(self, incident_id, note_by=note_by, message=message)

    def write_incident_operator_summary(self, *, summary: str, active: str, main_pid: str, listeners: str) -> None:
        incident_service_ops.write_incident_operator_summary(self, summary=summary, active=active, main_pid=main_pid, listeners=listeners)

    def update_incident_state(self, state: str, summary: str, *, resolved: bool = False) -> None:
        incident_service_ops.update_incident_state(self, state, summary, resolved=resolved)

    def codex_bin_available(self) -> bool:
        candidate = self.config.watchdog_codex_bin
        if "/" in candidate:
            return os.access(candidate, os.X_OK)
        return shutil.which(candidate) is not None

    def opencode_fallback_bin_available(self) -> bool:
        candidate = self.config.watchdog_opencode_fallback_bin
        if "/" in candidate:
            return os.access(candidate, os.X_OK)
        return shutil.which(candidate) is not None

    def load_existing_incident_context(self, incident_id: str) -> bool:
        return incident_service_ops.load_existing_incident_context(self, incident_id)

    def attach_current_incident_if_any(self) -> bool:
        return incident_service_ops.attach_current_incident_if_any(self)

    def reset_incident_state(self) -> None:
        incident_service_ops.reset_incident_state(self)

    def sibling_json_path(self, path: Path) -> Path:
        if path.suffix:
            return path.with_suffix(".json")
        return path.with_name(f"{path.name}.json")

    def write_event(self, status: str, summary: str) -> None:
        run_state = self.read_run_state()
        event_payload = event_ops.build_event_payload(
            run_ts=self.ctx.run_ts,
            status=status,
            summary=summary,
            run_state=run_state,
            rollback_occurred=self.ctx.rollback_occurred,
            rollback_summary_file=str(self.config.watchdog_last_rollback_summary_file),
            rollback_summary_archive_file=self.ctx.rollback_summary_archive_file,
            rollback_broken_config_file=self.ctx.rollback_broken_config_file,
            pre_repair_backup_result=self.ctx.pre_repair_backup_result,
            consecutive_failures=self.ctx.consecutive_failures,
            incident_id=self.ctx.incident_id,
            incident_dir=str(self.ctx.incident_dir) if self.ctx.incident_dir else '',
        )
        self.config.watchdog_event_file.write_text(event_ops.render_event_text(event_payload), encoding='utf-8')
        self.sibling_json_path(self.config.watchdog_event_file).write_text(
            json.dumps(event_payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )
        self.append_event_history(event_payload)

    def set_state(self, new_state: str, summary: str, *, health_level_override: str | None = None) -> None:
        if new_state in {"healthy", "recovered"}:
            self.attach_current_incident_if_any()
        old_state = "unknown"
        if self.last_status_file.exists():
            old_state = self.last_status_file.read_text(encoding="utf-8").strip() or "unknown"
        self.last_status_file.write_text(new_state, encoding="utf-8")

        health_level = health_level_override or (
            "healthy" if new_state in {"healthy", "recovered"} else "degraded" if new_state == "degraded" else "failed"
        )
        guard_info = repair_ops.guard_status(self.config)
        run_state_updates: dict[str, object] = {
            "current_mode": self.current_mode(
                maintenance=self.config.watchdog_maintenance_file.exists(),
                degraded=new_state == "degraded",
                survival=self.ctx.survival_mode_active,
            ),
            "health_level": health_level,
            "last_backup_result": self.ctx.pre_repair_backup_result,
            "last_rollback_summary_archive_file": self.ctx.rollback_summary_archive_file,
            "rollback_candidate_used": self.ctx.rollback_candidate_used,
            "rollback_reason": self.ctx.rollback_reason,
            "config_drift_detected": self.ctx.config_drift_detected,
            "last_recovery_strategy": self.ctx.last_recovery_strategy,
            "last_recovery_path": self.recovery_path_text(),
            "last_recovery_action_count": self.ctx.last_recovery_action_count,
            "last_recovery_restored_conversation": self.ctx.last_recovery_restored_conversation,
            "rescue_attempt_count": self.ctx.rescue_attempt_count,
            "rescue_executor_selected": self.ctx.rescue_executor_selected,
            "rescue_plan_generated": self.ctx.rescue_plan_generated,
            "rescue_plan_source": self.ctx.rescue_plan_source,
            "rescue_plan_id": self.ctx.rescue_plan_id,
            "rescue_plan_status": self.ctx.rescue_plan_status,
            "rescue_tier": self.ctx.rescue_tier,
            "case_ingest_result": self.ctx.case_ingest_result,
            "candidate_rule_status": self.ctx.candidate_rule_status,
            "rescue_attempt_order": list(self.ctx.rescue_attempt_order),
            "rescue_rejected_executors": list(self.ctx.rescue_rejected_executors),
            "rescue_learning_summary": self.ctx.rescue_learning_summary,
            "rescue_mutation_scope": list(self.ctx.rescue_mutation_scope),
            **survival_ops.run_state_fields(self),
            "last_good_validated_at": self.ctx.last_good_validated_at,
            "last_good_generation_id": self.ctx.last_good_generation_id,
            "last_good_generation_count": self.ctx.last_good_generation_count,
            "drift_scope": list(self.ctx.drift_scope),
            "drift_since_last_good": self.ctx.drift_since_last_good,
            "drift_summary": self.ctx.drift_summary,
            **guard_info,
        }
        if self.ctx.latest_probe:
            run_state_updates.update(
                {
                    "conversation_ready": bool(self.ctx.latest_probe.get("conversation_ready", False)),
                    "minimal_usable_ready": bool(self.ctx.latest_probe.get("minimal_usable_ready", False)),
                    "conversation_status": str(self.ctx.latest_probe.get("conversation_status", "down") or "down"),
                    "conversation_probe_summary": str(self.ctx.latest_probe.get("conversation_probe_summary", "") or ""),
                }
            )
        should_refresh_incident_index = False
        should_clear_incident_context = False
        if self.ctx.pre_repair_backup_result != "not-run":
            run_state_updates["last_backup_at"] = self.ctx.run_ts
        if self.ctx.rollback_occurred:
            run_state_updates["last_rollback_at"] = self.ctx.run_ts
            run_state_updates["last_rollback_summary_archive_file"] = self.ctx.rollback_summary_archive_file
        if new_state == "healthy":
            self.reset_failure_count()
            self.incident_backup_marker.unlink(missing_ok=True)
            self.ctx.pre_repair_backup_result = "not-run"
            if self.ctx.incident_dir is not None:
                self.update_incident_state("resolved", summary, resolved=True)
                should_refresh_incident_index = True
                should_clear_incident_context = True
            run_state_updates["last_success_at"] = self.ctx.run_ts
            run_state_updates["current_incident_id"] = ""
            run_state_updates["current_incident_state"] = ""
            run_state_updates["current_incident_age_seconds"] = 0
        elif new_state == "recovered":
            self.reset_failure_count()
            if self.ctx.incident_dir is not None:
                self.update_incident_state("resolved", summary, resolved=True)
                run_state_updates["current_incident_id"] = self.ctx.incident_id
                run_state_updates["current_incident_state"] = "resolved"
                should_refresh_incident_index = True
            run_state_updates["last_success_at"] = self.ctx.run_ts
            run_state_updates["last_recovered_at"] = self.ctx.run_ts
        elif new_state == "degraded":
            run_state_updates["last_degraded_at"] = self.ctx.run_ts
        elif new_state == "failed":
            if self.ctx.incident_dir is not None:
                self.update_incident_state("open", summary)
                run_state_updates["current_incident_id"] = self.ctx.incident_id
                run_state_updates["current_incident_state"] = "open"
                should_refresh_incident_index = True
            run_state_updates["last_failed_at"] = self.ctx.run_ts
        self.write_run_state(run_state_updates)
        if should_refresh_incident_index:
            self.refresh_current_incident_index(summary=summary, health_level=health_level)
        if should_clear_incident_context:
            self.reset_incident_state()
        self.write_event(new_state, summary)
        transition_report = self.report_payload(incident_limit=5)
        if new_state == "healthy":
            return
        report_text = self.append_rollback_summary(str(transition_report.get("message_text", "")))
        if new_state == "degraded" and old_state != "degraded" and self.config.watchdog_notify_on_degraded:
            self.notify(f"⚠️ OpenClaw watchdog 状态变化\n时间：{self.ctx.run_ts}\n{report_text}")
        elif new_state == "recovered" and old_state != "recovered" and self.config.watchdog_notify_on_recovery:
            self.notify(f"✅ OpenClaw watchdog 状态变化\n时间：{self.ctx.run_ts}\n{report_text}")
        elif new_state == "failed" and old_state != "failed" and self.config.watchdog_notify_on_failure:
            self.notify(
                f"❌ OpenClaw watchdog 状态变化\n时间：{self.ctx.run_ts}\n{report_text}\n日志：{self.config.watchdog_log_file}"
            )

    def service_active(self) -> bool:
        result = self.run_command(["systemctl", "--user", "is-active", "--quiet", self.config.openclaw_gateway_service], timeout=15)
        return result.returncode == 0

    def service_main_pid(self) -> str:
        result = self.run_command(
            ["systemctl", "--user", "show", "-p", "MainPID", "--value", self.config.openclaw_gateway_service],
            timeout=15,
        )
        value = (result.stdout or result.output).strip()
        return value if value.isdigit() else "0"

    def listener_pids(self) -> list[str]:
        result = self.run_command(["ss", "-tlnp"], timeout=15)
        if result.returncode != 0 and not result.stdout and not result.stderr:
            return []
        pattern = re.compile(rf":{self.config.openclaw_gateway_port}\b.*pid=(\d+)")
        pids = {match.group(1) for match in pattern.finditer(result.output)}
        return sorted(pids, key=int)

    def listener_count(self) -> int:
        return len(self.listener_pids())

    def listener_contains_pid(self, needle: str) -> bool:
        return needle.isdigit() and needle != "0" and needle in self.listener_pids()

    def pid_descends_from(self, pid: str, ancestor_pid: str) -> bool:
        if not pid.isdigit() or not ancestor_pid.isdigit() or pid == "0" or ancestor_pid == "0":
            return False
        current = pid
        seen: set[str] = set()
        while current.isdigit() and current != "0" and current not in seen:
            if current == ancestor_pid:
                return True
            seen.add(current)
            result = self.run_command(["ps", "-o", "ppid=", "-p", current], timeout=15)
            parent = (result.stdout or result.output).strip()
            parent = re.sub(r"\s+", "", parent)
            if not parent.isdigit() or parent == "0":
                return False
            current = parent
        return False

    def listener_matches_service_tree(self, main_pid: str) -> tuple[bool, str, str]:
        if not main_pid.isdigit() or main_pid == "0":
            return False, "none", ""
        for listener_pid in self.listener_pids():
            if listener_pid == main_pid:
                return True, "direct", listener_pid
            if self.pid_descends_from(listener_pid, main_pid):
                return True, "child", listener_pid
        return False, "none", ""

    def service_level_probe(self) -> dict[str, object]:
        return health_ops.service_level_probe(self)

    def run_doctor(self) -> tuple[int, str]:
        return repair_ops.run_doctor(self)

    def config_invalid(self, doctor_output: str) -> bool:
        return repair_ops.config_invalid(self, doctor_output)

    def backup_last_good(self, *, validation: dict[str, object] | None = None) -> None:
        repair_ops.backup_last_good(self, validation=validation)

    def capture_rollback_summary(self, current: Path, baseline: Path) -> None:
        repair_ops.capture_rollback_summary(self, current, baseline)

    def _walk_json_diff(self, current, baseline, path: str, out: list[str], *, limit: int) -> None:
        repair_ops.walk_json_diff(current, baseline, path, out, limit=limit)

    def prune_rollback_archives(self) -> None:
        repair_ops.prune_rollback_archives(self)

    def run_pre_repair_backup(self) -> None:
        repair_ops.run_pre_repair_backup(self)

    def restore_last_good(self, *, reason: str = "") -> bool:
        return repair_ops.restore_last_good(self, reason=reason)

    def last_good_status(self) -> dict[str, object]:
        return repair_ops.last_good_status(self)

    def drift_context(self) -> dict[str, object]:
        return repair_ops.drift_context(self)

    def guard_status(self) -> dict[str, object]:
        return repair_ops.guard_status(self.config)

    def sync_survival_mode(self, *, probe: dict[str, object], config_invalid: bool) -> dict[str, object]:
        return survival_ops.sync_survival_mode(self, probe=probe, config_invalid=config_invalid)

    def enter_survival_mode(self, *, reason: str) -> dict[str, object]:
        return survival_ops.enter_survival_mode(self, reason=reason)

    def kill_stray_listeners(self, main_pid: str) -> None:
        repair_ops.kill_stray_listeners(self, main_pid)

    def restart_service(self) -> bool:
        return repair_ops.restart_service(self)

    def raw_live_probe(self) -> dict[str, object]:
        return health_ops.raw_live_probe(self)

    def live_probe(self, *, include_doctor: bool, apply_grace: bool = True) -> dict[str, object]:
        return health_ops.live_probe(self, include_doctor=include_doctor, apply_grace=apply_grace)

    def healthy_now(self) -> bool:
        return health_ops.healthy_now(self)

    def run_doctor_repair(self) -> None:
        repair_ops.run_doctor_repair(self)

    def read_last_event(self) -> dict[str, object]:
        return health_ops.read_last_event(self)

    def message_report_text(self, report: dict[str, object]) -> str:
        return reporting_ops.message_report_text(report)

    def write_report_snapshot(self, report: dict[str, object]) -> None:
        reporting_ops.write_report_snapshot(self, report)

    def _unix_timestamp(self, value: object) -> int:
        return reporting_ops.unix_timestamp(value)

    def prometheus_metrics_text(self, metrics: dict[str, object]) -> str:
        return reporting_ops.prometheus_metrics_text(metrics)

    def write_metrics_snapshot(self, metrics: dict[str, object]) -> None:
        reporting_ops.write_metrics_snapshot(self, metrics)

    def metrics_payload(self) -> dict[str, object]:
        return reporting_ops.metrics_payload(self)

    def report_payload(self, *, incident_limit: int = 5) -> dict[str, object]:
        return reporting_ops.report_payload(self, incident_limit=incident_limit)

    def status_payload(self) -> dict[str, object]:
        return health_ops.status_payload(self)

    def maintenance_status_payload(self) -> dict[str, object]:
        return health_ops.maintenance_status_payload(self)

    def maintenance_on(self, reason: str = "") -> dict[str, object]:
        lines = [f"enabled_at={datetime.now().astimezone().strftime('%F %T %Z')}"]
        if reason:
            lines.append(f"reason={reason}")
        self.config.watchdog_maintenance_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_maintenance_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log("INFO", f"maintenance mode enabled file={self.config.watchdog_maintenance_file}")
        return self.maintenance_status_payload()

    def maintenance_off(self) -> dict[str, object]:
        self.config.watchdog_maintenance_file.unlink(missing_ok=True)
        self.log("INFO", f"maintenance mode disabled file={self.config.watchdog_maintenance_file}")
        return self.maintenance_status_payload()

    def _rescue_failure_signature(self, probe: dict[str, object]) -> str:
        if bool(probe.get("config_invalid", False)):
            return "config-invalid"
        if not bool(probe.get("process_layer_healthy", False)):
            return "process-down"
        if bool(probe.get("service_layer_healthy", True)) and not bool(probe.get("minimal_usable_ready", False)):
            return "conversation-down"
        if not bool(probe.get("service_layer_healthy", True)):
            return "service-layer-degraded"
        return "unknown-failure"

    def _rescue_available_executors(self) -> tuple[str, ...]:
        priority = list(getattr(self.config, "watchdog_rescue_executor_priority", [])) or [
            "codex",
            "claude-code",
            "gemini-cli",
            "opencode",
            "litellm",
            "rule-agent",
        ]
        available: list[str] = []
        command_map = {
            "codex": ("codex",),
            "claude-code": ("claude", "claude-code"),
            "gemini-cli": ("gemini", "gemini-cli"),
            "opencode": ("opencode",),
        }
        for name in priority:
            if name == "rule-agent":
                available.append(name)
                continue
            if name == "litellm":
                litellm_enabled = bool(getattr(self.config, "watchdog_litellm_enabled", False))
                litellm_model = str(getattr(self.config, "watchdog_litellm_model", "") or "")
                if litellm_enabled and litellm_model:
                    available.append(name)
                continue
            for command in command_map.get(name, (name,)):
                if shutil.which(command):
                    available.append(name)
                    break
        if "rule-agent" not in available:
            available.append("rule-agent")
        return tuple(available)

    def _rescue_command(self, name: str) -> str:
        if name == "codex":
            configured = str(getattr(self.config, "watchdog_codex_bin", "codex") or "codex")
            return configured if shutil.which(configured) else "codex"
        if name == "opencode":
            configured = str(getattr(self.config, "watchdog_opencode_fallback_bin", "opencode") or "opencode")
            return configured if shutil.which(configured) else "opencode"
        candidates = {
            "claude-code": ("claude", "claude-code"),
            "gemini-cli": ("gemini", "gemini-cli"),
        }
        for candidate in candidates.get(name, (name,)):
            if shutil.which(candidate):
                return candidate
        return name


    def build_rescue_context(self, probe: dict[str, object]):
        from watchdog_v2.learning import LearningStore
        from watchdog_v2.rescue_models import RescueContext

        failure_signature = self._rescue_failure_signature(probe)
        normalized_failure_signature = learning_signatures.normalized_failure_signature(
            {
                'failure_signature': failure_signature,
                'config_invalid': bool(probe.get('config_invalid', False)),
                'process_layer_healthy': bool(probe.get('process_layer_healthy', False)),
                'service_layer_healthy': bool(probe.get('service_layer_healthy', False)),
                'minimal_usable_ready': bool(probe.get('minimal_usable_ready', False)),
                'conversation_ready': bool(probe.get('conversation_ready', False)),
                'config_drift_detected': bool(probe.get('config_drift_detected', False)),
                'drift_scope': list(probe.get('drift_scope', [])) if isinstance(probe.get('drift_scope', []), list) else [],
            }
        )
        store = LearningStore(root=self.config.watchdog_rescue_knowledge_root)
        recent_case_criteria = {
            'failure_signature': failure_signature,
            'normalized_failure_signature': normalized_failure_signature,
            'config_invalid': bool(probe.get('config_invalid', False)),
            'process_layer_healthy': bool(probe.get('process_layer_healthy', False)),
            'service_layer_healthy': bool(probe.get('service_layer_healthy', False)),
            'minimal_usable_ready': bool(probe.get('minimal_usable_ready', False)),
            'conversation_ready': bool(probe.get('conversation_ready', False)),
            'config_drift_detected': bool(probe.get('config_drift_detected', False)),
            'drift_scope': list(probe.get('drift_scope', [])) if isinstance(probe.get('drift_scope', []), list) else [],
        }
        recent_cases = [
            {
                'case_id': str(case.get('case_id', '') or ''),
                'executor': str(case.get('executor', '') or ''),
                'strategy': str(case.get('strategy', '') or ''),
                'status': str(case.get('status', '') or ''),
            }
            for case in store.similar_cases(recent_case_criteria)[-3:]
        ]
        known_rules = [
            {
                'rule_id': str(rule.get('rule_id', '') or ''),
                'match': dict(rule.get('match', {})) if isinstance(rule.get('match', {}), dict) else {},
                'diagnosis': str(rule.get('diagnosis', '') or ''),
            }
            for rule in store.load_rules()[-5:]
        ]
        metadata = {
            "config_invalid": bool(probe.get("config_invalid", False)),
            "failure_signature": failure_signature,
            "normalized_failure_signature": normalized_failure_signature,
            "conversation_status": str(probe.get("conversation_status", "down") or "down"),
            "process_layer_healthy": bool(probe.get("process_layer_healthy", False)),
            "service_layer_healthy": bool(probe.get("service_layer_healthy", False)),
            "minimal_usable_ready": bool(probe.get("minimal_usable_ready", False)),
            "service_active": bool(probe.get("service_active", False)),
            "recent_cases": recent_cases,
            "known_rules": known_rules,
        }
        incident_id = self.ctx.incident_id or f"incident-{datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}"
        self.ctx.incident_id = incident_id
        return RescueContext(
            incident_id=incident_id,
            health_level=str(self.read_run_state().get("health_level", "failed") or "failed"),
            conversation_status=str(probe.get("conversation_status", "down") or "down"),
            available_executors=self._rescue_available_executors(),
            editable_paths=tuple(str(item) for item in getattr(self.config, "watchdog_rescue_editable_paths", [])),
            editable_keys=tuple(str(item) for item in getattr(self.config, "watchdog_rescue_editable_keys", [])),
            probe=dict(probe),
            metadata=metadata,
        )

    def _build_litellm_client(self):
        if not bool(getattr(self.config, "watchdog_litellm_enabled", False)):
            return None
        model = str(getattr(self.config, "watchdog_litellm_model", "") or "")
        if not model:
            return None
        try:
            import litellm  # type: ignore
        except ImportError:
            return None

        engine = self
        config = self.config

        class _LiteLLMClient:
            def generate_plan(self, payload: dict[str, object]) -> dict[str, object]:
                api_key_env = str(getattr(config, "watchdog_litellm_api_key_env", "") or "")
                api_key = os.environ.get(api_key_env, "") if api_key_env else ""
                response = litellm.completion(
                    model=model,
                    api_base=str(getattr(config, "watchdog_litellm_api_base", "") or "") or None,
                    api_key=api_key or None,
                    timeout=int(getattr(config, "watchdog_litellm_timeout_seconds", 60) or 60),
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are the OpenClaw rescue planner. Return JSON only with plan_id, diagnosis, actions, validations, rollback_strategy, risk_level, and rationale. "
                                "Never emit shell commands or arbitrary execution."
                            ),
                        },
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                )
                content = ""
                choices = getattr(response, "choices", None)
                if choices:
                    first = choices[0]
                    message = getattr(first, "message", None)
                    content = getattr(message, "content", "") if message is not None else ""
                elif isinstance(response, dict):
                    try:
                        content = response["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError):
                        content = ""
                if isinstance(content, list):
                    content = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("LiteLLM did not return structured JSON content")
                payload = json.loads(content)
                if not isinstance(payload, dict):
                    raise ValueError("LiteLLM response must be a JSON object")
                return payload

        return _LiteLLMClient()

    def dispatch_rescue(self, context):
        from watchdog_v2.learning import LearningStore
        from watchdog_v2.rescue_agents.claude_code_adapter import ClaudeCodeAdapter
        from watchdog_v2.rescue_agents.codex_adapter import CodexAdapter
        from watchdog_v2.rescue_agents.gemini_cli_adapter import GeminiCliAdapter
        from watchdog_v2.rescue_agents.litellm_agent import LiteLLMSpecialistAgent
        from watchdog_v2.rescue_agents.opencode_adapter import OpenCodeAdapter
        from watchdog_v2.rescue_agents.rule_agent import RuleBasedRescueAgent
        from watchdog_v2.rescue_dispatch import RescueDispatcher

        available = set(context.available_executors)
        learning_store = LearningStore(root=self.config.watchdog_rescue_knowledge_root)
        adapters_by_name = {
            "codex": CodexAdapter(
                available="codex" in available,
                command=self._rescue_command("codex"),
                runner=self.run_command,
                timeout_seconds=int(getattr(self.config, "watchdog_codex_timeout_seconds", 120) or 120),
                cwd=getattr(self.config, "watchdog_codex_workdir", None),
            ),
            "claude-code": ClaudeCodeAdapter(
                available="claude-code" in available,
                command=self._rescue_command("claude-code"),
                runner=self.run_command,
                timeout_seconds=int(getattr(self.config, "watchdog_codex_timeout_seconds", 120) or 120),
                cwd=getattr(self.config, "watchdog_codex_workdir", None),
            ),
            "gemini-cli": GeminiCliAdapter(
                available="gemini-cli" in available,
                command=self._rescue_command("gemini-cli"),
                runner=self.run_command,
                timeout_seconds=int(getattr(self.config, "watchdog_codex_timeout_seconds", 120) or 120),
                cwd=getattr(self.config, "watchdog_codex_workdir", None),
            ),
            "opencode": OpenCodeAdapter(
                available="opencode" in available,
                command=self._rescue_command("opencode"),
                runner=self.run_command,
                timeout_seconds=int(getattr(self.config, "watchdog_opencode_fallback_timeout_seconds", 120) or 120),
                cwd=getattr(self.config, "watchdog_opencode_fallback_workdir", None),
            ),
            "litellm": LiteLLMSpecialistAgent(config=self.config, client=self._build_litellm_client()),
            "rule-agent": RuleBasedRescueAgent(rule_store=learning_store),
        }
        priority = list(getattr(self.config, "watchdog_rescue_executor_priority", [])) or [
            "codex",
            "claude-code",
            "gemini-cli",
            "opencode",
            "litellm",
            "rule-agent",
        ]
        adapters = [adapters_by_name[name] for name in priority if name in adapters_by_name]
        return RescueDispatcher(adapters=adapters).dispatch(context)

    def execute_rescue_plan(self, plan, *, executor: str):
        from watchdog_v2.rescue_actions import RescueActionExecutor
        from watchdog_v2.rescue_models import RescueResult

        result = RescueActionExecutor(config=self.config, engine=self).apply_plan(plan)
        return RescueResult(
            status=result.status,
            executor=executor,
            plan_id=plan.plan_id,
            rollback_performed=result.rollback_performed,
            details=dict(result.details),
        )

    def record_learning_from_recovery(
        self,
        *,
        strategy: str,
        recovery_kind: str,
        probe: dict[str, object],
        context=None,
        dispatch_result=None,
        plan_result=None,
    ) -> dict[str, object]:
        from watchdog_v2.learning import LearningStore

        store = LearningStore(root=self.config.watchdog_rescue_knowledge_root)
        metadata = context.metadata if context is not None and isinstance(getattr(context, 'metadata', None), dict) else {}
        failure_signature = str(metadata.get("failure_signature", "") or self._rescue_failure_signature(probe))
        normalized_failure_signature = str(
            metadata.get('normalized_failure_signature', '')
            or learning_signatures.normalized_failure_signature(
                {
                    'failure_signature': failure_signature,
                    'config_invalid': bool(metadata.get('config_invalid', False) or probe.get('config_invalid', False)),
                    'process_layer_healthy': bool(metadata.get('process_layer_healthy', probe.get('process_layer_healthy', False))),
                    'service_layer_healthy': bool(metadata.get('service_layer_healthy', probe.get('service_layer_healthy', False))),
                    'minimal_usable_ready': bool(metadata.get('minimal_usable_ready', probe.get('minimal_usable_ready', False))),
                    'conversation_ready': bool(metadata.get('conversation_ready', probe.get('conversation_ready', False))),
                    'config_drift_detected': bool(metadata.get('config_drift_detected', False) or probe.get('config_drift_detected', False)),
                    'drift_scope': list(metadata.get('drift_scope', [])) if isinstance(metadata.get('drift_scope', []), list) else [],
                }
            )
        )
        rule_slug = re.sub(r"[^a-z0-9-]+", "-", normalized_failure_signature.lower()).strip("-") or "rescue-rule"
        plan = getattr(dispatch_result, 'plan', None) if dispatch_result is not None else None
        final_executor = str(getattr(dispatch_result, 'final_executor', '') or strategy)
        candidate_rule = None
        if plan is not None:
            match = {"normalized_failure_signature": normalized_failure_signature}
            if bool(metadata.get("config_invalid", False)):
                match["config_invalid"] = True
            candidate_rule = {
                "rule_id": f"{rule_slug}-{final_executor or 'rescue'}",
                "match": match,
                "diagnosis": plan.diagnosis,
                "actions": [action.to_dict() for action in plan.actions],
                "validations": list(plan.validations),
            }
        risk_level = plan.risk_level if plan is not None else 'low'
        payload = {
            "case_id": f"{self.ctx.incident_id or 'incident'}-{final_executor or strategy}-{datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}",
            "incident_id": self.ctx.incident_id,
            "failure_signature": failure_signature,
            "normalized_failure_signature": normalized_failure_signature,
            "status": "recovered",
            "executor": final_executor or strategy,
            "strategy": strategy,
            "recovery_kind": recovery_kind,
            "plan_id": plan.plan_id if plan is not None else '',
            "risk_level": risk_level,
            "candidate_rule": candidate_rule,
            "recovered_at": datetime.now().astimezone().isoformat(timespec='seconds'),
        }
        case_path = store.record_successful_case(payload)
        promotion = store.promote_candidates()
        candidate_rule_status = 'none'
        if candidate_rule is not None:
            if promotion.pending_review > 0:
                candidate_rule_status = 'pending-review'
            elif promotion.auto_promoted > 0:
                candidate_rule_status = 'auto-promoted'
            else:
                candidate_rule_status = 'candidate-recorded'
        return {
            'case_ingest_result': f'recorded:{case_path.name}',
            'candidate_rule_status': candidate_rule_status,
        }

    def record_learning_from_rescue(self, *, context, dispatch_result, plan_result) -> dict[str, object]:
        return self.record_learning_from_recovery(
            strategy=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'),
            recovery_kind='rescue',
            probe=context.probe if context is not None else {},
            context=context,
            dispatch_result=dispatch_result,
            plan_result=plan_result,
        )

    def _service_probe_failures_for(self, probe: dict[str, object], previous_failures: int) -> int:
        process_layer_healthy = bool(probe.get("process_layer_healthy", False))
        service_layer_healthy = bool(probe.get("service_layer_healthy", True))
        if self.config.watchdog_enable_service_level_probe and process_layer_healthy and not service_layer_healthy:
            return previous_failures + 1
        return 0

    def _write_probe_run_state(self, probe: dict[str, object], *, config_invalid: bool, service_probe_failures: int) -> str:
        self.ctx.latest_probe = dict(probe)
        process_layer_healthy = bool(probe.get("process_layer_healthy", False))
        service_layer_healthy = bool(probe.get("service_layer_healthy", True))
        conversation_ready = bool(probe.get("conversation_ready", False))
        minimal_usable_ready = bool(probe.get("minimal_usable_ready", False))
        initial_health_level = "healthy"
        if config_invalid or not process_layer_healthy:
            initial_health_level = "failed"
        elif conversation_ready:
            initial_health_level = "healthy"
        elif minimal_usable_ready:
            initial_health_level = "degraded"
        else:
            initial_health_level = "failed"
        self.write_run_state(
            {
                "service_probe_failures": service_probe_failures,
                "last_service_probe_at": str(probe.get("service_probe_checked_at", self.now_iso())),
                "last_service_probe_result": "healthy" if service_layer_healthy else "degraded",
                "last_service_probe_summary": str(probe.get("service_probe_summary", "")),
                "last_service_probe_rc": int(probe.get("service_probe_rc", 0) or 0),
                "health_level": initial_health_level,
                "current_mode": self.current_mode(
                    maintenance=self.config.watchdog_maintenance_file.exists(),
                    degraded=initial_health_level == "degraded",
                    survival=self.ctx.survival_mode_active,
                ),
                    "conversation_ready": conversation_ready,
                "minimal_usable_ready": minimal_usable_ready,
                "conversation_status": str(probe.get("conversation_status", "down") or "down"),
                "conversation_probe_summary": str(probe.get("conversation_probe_summary", "") or ""),
                **survival_ops.run_state_fields(self),
            }
        )
        return initial_health_level

    def run_once(self) -> RunOutcome:
        from watchdog_v2.flows import rescue_run

        return rescue_run.run(self, self.ctx)
