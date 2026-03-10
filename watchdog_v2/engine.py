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
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from watchdog_v2 import events as event_ops
from watchdog_v2 import handoff as handoff_ops
from watchdog_v2 import health as health_ops
from watchdog_v2 import incident_context as incident_context_ops
from watchdog_v2 import incidents as incident_ops
from watchdog_v2 import repair as repair_ops
from watchdog_v2 import reporting as reporting_ops
from watchdog_v2 import survival as survival_ops
from watchdog_v2.config import Config, parse_env_file
from watchdog_v2.runtime import CommandResult, run_capture_to_file, run_command
from watchdog_v2 import state_store


@dataclass
class RunOutcome:
    exit_code: int
    state: str
    summary: str


class WatchdogEngine:
    def __init__(self, config: Config):
        self.config = config
        self.run_ts = datetime.now().astimezone().strftime("%F %T %Z")
        self.last_status_file = self.config.watchdog_state_dir / "last-status"
        self.run_state_file = self.config.watchdog_run_state_file
        self.incident_backup_marker = self.config.watchdog_state_dir / "incident-backup-done"
        self.current_incident_marker = self.config.watchdog_state_dir / "current-incident-id"
        self.tmpdir_obj: tempfile.TemporaryDirectory[str] | None = None
        self.tmpdir: Path | None = None
        self.lock_handle = None
        self.rollback_summary = ""
        self.rollback_occurred = False
        self.rollback_summary_archive_file = ""
        self.rollback_broken_config_file = ""
        self.rollback_candidate_used = ""
        self.rollback_reason = ""
        self.config_drift_detected = False
        self.pre_repair_backup_result = "not-run"
        self.consecutive_failures = 0
        self.recovery_steps: list[str] = []
        self.last_recovery_strategy = "none"
        self.last_recovery_action_count = 0
        self.last_recovery_restored_conversation = False
        self.last_good_validated_at = ""
        self.last_good_generation_id = ""
        self.last_good_generation_count = 0
        self.survival_mode_active = False
        self.survival_mode_reason = ""
        self.survival_mode_since = ""
        self.survival_mode_summary = ""
        self.survival_mode_actions: list[str] = []
        self.survival_mode_disabled_features: list[str] = []
        self.survival_mode_config_file = ""
        self.survival_mode_sticky = False
        self.survival_mode_sticky_reason = ""
        self.survival_mode_exit_ready = False
        self.survival_mode_exit_policy = "none"
        self.survival_mode_exit_blockers: list[str] = []
        self.survival_mode_stable_ready_runs = 0
        self.survival_mode_stable_required_runs = self.config.watchdog_survival_stable_ready_runs
        self.survival_mode_manual_clear_required = False
        self.survival_mode_config_changed_away = False
        self.survival_mode_last_exit_at = ""
        self.survival_mode_last_exit_reason = ""
        self.survival_mode_last_exit_kind = ""
        self.survival_mode_last_exit_summary = ""
        self.drift_scope: list[str] = []
        self.drift_since_last_good = ""
        self.drift_summary = ""
        self.latest_probe: dict[str, object] = {}
        self.incident_id = ""
        self.incident_dir: Path | None = None
        self.codex_prompt_file: Path | None = None
        self.codex_handoff_file: Path | None = None
        self.codex_runner_file: Path | None = None
        self.codex_run_log_file: Path | None = None
        self.codex_run_pid = ""
        self.codex_trigger_result = "not-run"
        self.codex_autorun_ready = False
        self.last_run_started_at = datetime.now().astimezone()
        self.last_run_finished_at = self.last_run_started_at
        self.opencode_fallback_handoff_file: Path | None = None
        self.opencode_fallback_runner_file: Path | None = None
        self.opencode_fallback_run_log_file: Path | None = None
        self.opencode_fallback_run_pid = ""
        self.opencode_fallback_trigger_result = "not-run"
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
        if self.rollback_summary:
            return f"{text}\n\n回退摘要：\n{self.rollback_summary}"
        return text

    def reset_recovery_tracking(self) -> None:
        self.recovery_steps = []
        self.last_recovery_strategy = "none"
        self.last_recovery_action_count = 0
        self.last_recovery_restored_conversation = False
        self.rollback_candidate_used = ""
        self.rollback_reason = ""
        self.config_drift_detected = False
        self.survival_mode_active = False
        self.survival_mode_reason = ""
        self.survival_mode_since = ""
        self.survival_mode_summary = ""
        self.survival_mode_actions = []
        self.survival_mode_disabled_features = []
        self.survival_mode_config_file = ""
        self.survival_mode_sticky = False
        self.survival_mode_sticky_reason = ""
        self.survival_mode_exit_ready = False
        self.survival_mode_exit_policy = "none"
        self.survival_mode_exit_blockers = []
        self.survival_mode_stable_ready_runs = 0
        self.survival_mode_stable_required_runs = self.config.watchdog_survival_stable_ready_runs
        self.survival_mode_manual_clear_required = False
        self.survival_mode_config_changed_away = False
        self.survival_mode_last_exit_at = ""
        self.survival_mode_last_exit_reason = ""
        self.survival_mode_last_exit_kind = ""
        self.survival_mode_last_exit_summary = ""
        self.drift_scope = []
        self.drift_since_last_good = ""
        self.drift_summary = ""
        self.latest_probe = {}

    def record_recovery_step(self, step: str, outcome: str, detail: str = "") -> None:
        token = f"{step}:{outcome}"
        if detail:
            token = f"{token}({detail})"
        self.recovery_steps.append(token)
        if outcome not in {"skipped", "diagnosed", "not-applicable"}:
            self.last_recovery_action_count += 1

    def recovery_path_text(self) -> str:
        return " -> ".join(self.recovery_steps) if self.recovery_steps else "none"

    def finalize_recovery_tracking(self, *, strategy: str, restored_conversation: bool) -> None:
        self.last_recovery_strategy = strategy or "none"
        self.last_recovery_restored_conversation = bool(restored_conversation)

    def write_codex_trigger_status(self, file_path: Path, final_result: str, detail: str) -> None:
        file_path.write_text(
            textwrap.dedent(
                f"""\
                primary=codex
                fallback=opencode
                final_result={final_result}
                detail={detail}
                codex_bin={self.config.watchdog_codex_bin}
                opencode_fallback_bin={self.config.watchdog_opencode_fallback_bin}
                incident_id={self.incident_id}
                incident_dir={self.incident_dir or ''}
                """
            ),
            encoding="utf-8",
        )

    def write_opencode_fallback_status(self, file_path: Path, final_result: str, detail: str) -> None:
        file_path.write_text(
            textwrap.dedent(
                f"""\
                primary=opencode-fallback
                final_result={final_result}
                detail={detail}
                opencode_fallback_bin={self.config.watchdog_opencode_fallback_bin}
                incident_id={self.incident_id}
                incident_dir={self.incident_dir or ''}
                """
            ),
            encoding="utf-8",
        )

    def read_failure_count(self) -> int:
        try:
            value = self.config.watchdog_failure_count_file.read_text(encoding="utf-8").strip()
            return int(value)
        except (FileNotFoundError, ValueError):
            return 0

    def write_failure_count(self, count: int) -> None:
        self.consecutive_failures = max(0, int(count))
        self.config.watchdog_failure_count_file.write_text(f"{self.consecutive_failures}", encoding="utf-8")

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
            "cooldown_remaining_seconds": 0,
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
            "autorun_primary": "codex",
            "autorun_fallback": "opencode",
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

    def codex_cooldown_remaining(self) -> int:
        cooldown = self.config.watchdog_codex_cooldown_seconds
        if cooldown <= 0:
            return 0
        try:
            last_trigger = int(self.config.watchdog_codex_last_trigger_file.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            return 0
        return max(0, cooldown - (int(time.time()) - last_trigger))

    def current_mode(self, *, maintenance: bool, degraded: bool = False, survival: bool = False) -> str:
        if maintenance:
            return "maintenance"
        if survival:
            return "survival"
        cooldown_remaining = self.codex_cooldown_remaining()
        if degraded:
            return "degraded"
        if cooldown_remaining > 0:
            return "cooldown"
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
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def read_json_dict(self, path: Path) -> dict[str, object]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def read_incident_state_payload(self, incident_dir: Path) -> dict[str, object]:
        return self.read_json_dict(self.incident_state_file(incident_dir))

    def read_incident_operator_summary_payload(self, incident_dir: Path) -> dict[str, object]:
        return parse_env_file(incident_dir / "operator-summary.txt")

    def incident_operator_workflow_file(self, incident_dir: Path) -> Path:
        return incident_dir / "operator-workflow.json"

    def read_incident_operator_workflow_payload(self, incident_dir: Path) -> dict[str, object]:
        payload = self.read_json_dict(self.incident_operator_workflow_file(incident_dir))
        notes = payload.get("notes", []) if isinstance(payload, dict) else []
        if not isinstance(notes, list):
            notes = []
        clean_notes: list[dict[str, object]] = []
        for note in notes:
            if not isinstance(note, dict):
                continue
            clean_notes.append(
                {
                    "time": str(note.get("time", "") or ""),
                    "by": str(note.get("by", "") or ""),
                    "message": str(note.get("message", "") or ""),
                }
            )
        events = payload.get("events", []) if isinstance(payload, dict) else []
        if not isinstance(events, list):
            events = []
        clean_events: list[dict[str, object]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            clean_events.append(
                {
                    "time": str(event.get("time", "") or ""),
                    "type": str(event.get("type", "") or ""),
                    "by": str(event.get("by", "") or ""),
                    "owner": str(event.get("owner", "") or ""),
                    "acknowledged": bool(event.get("acknowledged", False)),
                    "message": str(event.get("message", "") or ""),
                    "summary": str(event.get("summary", "") or ""),
                }
            )
        return {
            "incident_id": str(payload.get("incident_id", incident_dir.name) or incident_dir.name),
            "owner": str(payload.get("owner", "") or ""),
            "acknowledged": bool(payload.get("acknowledged", False)),
            "acknowledged_by": str(payload.get("acknowledged_by", "") or ""),
            "acknowledged_at": str(payload.get("acknowledged_at", "") or ""),
            "updated_at": str(payload.get("updated_at", "") or ""),
            "notes": clean_notes,
            "events": clean_events,
        }

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
        run_state = self.read_run_state()
        lines = [
            f"incident_id={self.incident_id}",
            f"time={self.run_ts}",
            f"summary={summary}",
            f"health_level={run_state.get('health_level', 'unknown')}",
            f"conversation_status={run_state.get('conversation_status', 'down')}",
            f"active={active}",
            f"main_pid={main_pid}",
            f"listeners={listeners}",
            f"pre_repair_backup_result={self.pre_repair_backup_result}",
            f"rollback_occurred={'true' if self.rollback_occurred else 'false'}",
            f"rollback_summary_archive_file={self.rollback_summary_archive_file or 'none'}",
            f"rollback_candidate_used={self.rollback_candidate_used or 'none'}",
            f"rollback_reason={self.rollback_reason or 'none'}",
            f"last_recovery_strategy={self.last_recovery_strategy}",
            f"last_recovery_path={self.recovery_path_text()}",
            f"codex_trigger_result={self.codex_trigger_result}",
            f"opencode_fallback_trigger_result={self.opencode_fallback_trigger_result}",
        ]
        return "\n".join(lines) + "\n"

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
        codex_trigger_result: str | None = None,
        opencode_fallback_trigger_result: str | None = None,
        incident_id: str | None = None,
        incident_dir: Path | None = None,
    ) -> dict[str, object]:
        target_incident_id = incident_id or self.incident_id
        target_incident_dir = incident_dir or self.incident_dir
        return incident_context_ops.build_incident_index_entry(
            run_ts=self.run_ts,
            incident_id=target_incident_id,
            incident_dir=str(target_incident_dir) if target_incident_dir else "",
            summary=summary,
            state_payload=self.read_incident_state_payload(target_incident_dir) if target_incident_dir is not None else {},
            workflow_payload=self.read_incident_operator_workflow_payload(target_incident_dir) if target_incident_dir is not None else {},
            run_state={
                **self.read_run_state(),
                'health_level': health_level or str(self.read_run_state().get('health_level', 'unknown') or 'unknown'),
            },
            active=active,
            main_pid=main_pid,
            listeners=listeners,
            pre_repair_backup_result=pre_repair_backup_result or self.pre_repair_backup_result,
            rollback_occurred=self.rollback_occurred if rollback_occurred is None else rollback_occurred,
            rollback_summary_archive_file=rollback_summary_archive_file if rollback_summary_archive_file is not None else self.rollback_summary_archive_file,
            rollback_candidate_used=self.rollback_candidate_used,
            rollback_reason=self.rollback_reason,
            last_recovery_strategy=self.last_recovery_strategy,
            last_recovery_path=self.recovery_path_text(),
            codex_trigger_result=codex_trigger_result or self.codex_trigger_result,
            opencode_fallback_trigger_result=opencode_fallback_trigger_result or self.opencode_fallback_trigger_result,
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
        codex_trigger_result: str | None = None,
        opencode_fallback_trigger_result: str | None = None,
        incident_id: str | None = None,
        incident_dir: Path | None = None,
    ) -> None:
        index_file = self.config.watchdog_incident_index_file
        items: list[dict[str, object]] = []
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    items = [item for item in data if isinstance(item, dict)]
            except json.JSONDecodeError:
                items = []
        target_incident_id = incident_id or self.incident_id
        entry = self.incident_index_entry(
            summary=summary,
            active=active,
            main_pid=main_pid,
            listeners=listeners,
            health_level=health_level,
            pre_repair_backup_result=pre_repair_backup_result,
            rollback_occurred=rollback_occurred,
            rollback_summary_archive_file=rollback_summary_archive_file,
            codex_trigger_result=codex_trigger_result,
            opencode_fallback_trigger_result=opencode_fallback_trigger_result,
            incident_id=target_incident_id,
            incident_dir=incident_dir,
        )
        items = [item for item in items if str(item.get("incident_id", "")) != target_incident_id]
        items.append(entry)
        items = sorted(items, key=lambda item: str(item.get("incident_id", "")))
        keep = max(1, self.config.watchdog_incident_index_limit)
        index_file.write_text(json.dumps(items[-keep:], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def read_incident_index(self, limit: int | None = None) -> list[dict[str, object]]:
        index_file = self.config.watchdog_incident_index_file
        if not index_file.exists():
            return []
        try:
            data = json.loads(index_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        items = [item for item in data if isinstance(item, dict)]
        if limit is not None and limit > 0:
            return items[-limit:]
        return items

    def refresh_current_incident_index(self, *, summary: str | None = None, health_level: str | None = None) -> None:
        if self.incident_dir is None:
            return
        operator_payload = self.read_incident_operator_summary_payload(self.incident_dir)
        existing_index_payload = next(
            (
                item
                for item in reversed(self.read_incident_index())
                if str(item.get("incident_id", "")) == self.incident_id
            ),
            {},
        )
        current_summary = summary or str(operator_payload.get("summary", existing_index_payload.get("summary", "")) or "")
        self.update_incident_index(
            summary=current_summary,
            active=str(operator_payload.get("active", existing_index_payload.get("active", "unknown")) or "unknown"),
            main_pid=str(operator_payload.get("main_pid", existing_index_payload.get("main_pid", "0")) or "0"),
            listeners=str(operator_payload.get("listeners", existing_index_payload.get("listeners", "none")) or "none"),
            health_level=health_level,
            pre_repair_backup_result=str(existing_index_payload.get("pre_repair_backup_result", self.pre_repair_backup_result) or self.pre_repair_backup_result),
            rollback_occurred=bool(existing_index_payload.get("rollback_occurred", self.rollback_occurred)),
            rollback_summary_archive_file=str(existing_index_payload.get("rollback_summary_archive_file", self.rollback_summary_archive_file) or self.rollback_summary_archive_file),
            codex_trigger_result=str(existing_index_payload.get("codex_trigger_result", self.codex_trigger_result) or self.codex_trigger_result),
            opencode_fallback_trigger_result=str(
                existing_index_payload.get("opencode_fallback_trigger_result", self.opencode_fallback_trigger_result)
                or self.opencode_fallback_trigger_result
            ),
        )

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
        if self.incident_dir is None:
            return
        (self.incident_dir / "operator-summary.txt").write_text(
            self.incident_operator_summary(summary=summary, active=active, main_pid=main_pid, listeners=listeners),
            encoding="utf-8",
        )
        self.update_incident_index(summary=summary, active=active, main_pid=main_pid, listeners=listeners)

    def update_incident_state(self, state: str, summary: str, *, resolved: bool = False) -> None:
        if self.incident_dir is None:
            return
        incident_state_file = self.incident_state_file(self.incident_dir)
        payload: dict[str, object] = {
            "incident_id": self.incident_id,
            "state": state,
            "summary": summary,
        }
        if incident_state_file.exists():
            try:
                existing = json.loads(incident_state_file.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    payload = {**existing, **payload}
            except json.JSONDecodeError:
                pass
        payload.setdefault("created_at", self.now_iso())
        if state == "open" and summary != "incident created":
            if not str(payload.get("opened_summary", "") or "") or str(payload.get("opened_summary", "") or "") == "incident created":
                payload["opened_summary"] = summary
        elif not str(payload.get("opened_summary", "") or ""):
            payload["opened_summary"] = summary
        if resolved:
            payload["resolved_at"] = self.now_iso()
            payload["resolution_summary"] = summary
        incident_state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

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
        incident_id = incident_id.strip()
        if not incident_id:
            return False
        incident_dir = self.config.watchdog_incidents_dir / incident_id
        if not incident_dir.exists() or not incident_dir.is_dir():
            return False
        self.incident_id = incident_id
        self.incident_dir = incident_dir
        self.current_incident_marker.write_text(f"{incident_id}\n", encoding="utf-8")
        self.codex_prompt_file = self.incident_dir / "codex-prompt.md"
        self.codex_handoff_file = self.incident_dir / "run-codex.sh"
        self.codex_runner_file = self.incident_dir / "codex-runner.sh"
        self.codex_run_log_file = self.incident_dir / "codex-run.log"
        self.codex_autorun_ready = self.codex_handoff_file.exists()
        self.opencode_fallback_handoff_file = self.incident_dir / "run-opencode-fallback.sh"
        self.opencode_fallback_runner_file = self.incident_dir / "opencode-fallback-runner.sh"
        self.opencode_fallback_run_log_file = self.incident_dir / "opencode-fallback.log"
        return True

    def attach_current_incident_if_any(self) -> bool:
        if self.incident_dir is not None and self.incident_id:
            return True
        if not self.current_incident_marker.exists():
            return False
        incident_id = self.current_incident_marker.read_text(encoding="utf-8").strip()
        return self.load_existing_incident_context(incident_id)

    def reset_incident_state(self) -> None:
        self.current_incident_marker.unlink(missing_ok=True)
        self.incident_id = ""
        self.incident_dir = None
        self.codex_prompt_file = None
        self.codex_handoff_file = None
        self.codex_runner_file = None
        self.codex_run_log_file = None
        self.codex_run_pid = ""
        self.codex_trigger_result = "not-run"
        self.codex_autorun_ready = False
        self.opencode_fallback_handoff_file = None
        self.opencode_fallback_runner_file = None
        self.opencode_fallback_run_log_file = None
        self.opencode_fallback_run_pid = ""
        self.opencode_fallback_trigger_result = "not-run"

    def sibling_json_path(self, path: Path) -> Path:
        if path.suffix:
            return path.with_suffix(".json")
        return path.with_name(f"{path.name}.json")

    def write_event(self, status: str, summary: str) -> None:
        run_state = self.read_run_state()
        event_payload = event_ops.build_event_payload(
            run_ts=self.run_ts,
            status=status,
            summary=summary,
            run_state=run_state,
            rollback_occurred=self.rollback_occurred,
            rollback_summary_file=str(self.config.watchdog_last_rollback_summary_file),
            rollback_summary_archive_file=self.rollback_summary_archive_file,
            rollback_broken_config_file=self.rollback_broken_config_file,
            pre_repair_backup_result=self.pre_repair_backup_result,
            consecutive_failures=self.consecutive_failures,
            incident_id=self.incident_id,
            incident_dir=str(self.incident_dir) if self.incident_dir else '',
            codex_context={
                'prompt_file': str(self.codex_prompt_file) if self.codex_prompt_file else '',
                'handoff_file': str(self.codex_handoff_file) if self.codex_handoff_file else '',
                'runner_file': str(self.codex_runner_file) if self.codex_runner_file else '',
                'run_log_file': str(self.codex_run_log_file) if self.codex_run_log_file else '',
                'run_pid': self.codex_run_pid,
                'trigger_result': self.codex_trigger_result,
                'autorun_ready': self.codex_autorun_ready,
            },
            opencode_fallback_context={
                'handoff_file': str(self.opencode_fallback_handoff_file) if self.opencode_fallback_handoff_file else '',
                'runner_file': str(self.opencode_fallback_runner_file) if self.opencode_fallback_runner_file else '',
                'run_log_file': str(self.opencode_fallback_run_log_file) if self.opencode_fallback_run_log_file else '',
                'run_pid': self.opencode_fallback_run_pid,
                'trigger_result': self.opencode_fallback_trigger_result,
            },
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
                survival=self.survival_mode_active,
            ),
            "health_level": health_level,
            "last_backup_result": self.pre_repair_backup_result,
            "last_rollback_summary_archive_file": self.rollback_summary_archive_file,
            "rollback_candidate_used": self.rollback_candidate_used,
            "rollback_reason": self.rollback_reason,
            "config_drift_detected": self.config_drift_detected,
            "last_recovery_strategy": self.last_recovery_strategy,
            "last_recovery_path": self.recovery_path_text(),
            "last_recovery_action_count": self.last_recovery_action_count,
            "last_recovery_restored_conversation": self.last_recovery_restored_conversation,
            **survival_ops.run_state_fields(self),
            "last_good_validated_at": self.last_good_validated_at,
            "last_good_generation_id": self.last_good_generation_id,
            "last_good_generation_count": self.last_good_generation_count,
            "drift_scope": list(self.drift_scope),
            "drift_since_last_good": self.drift_since_last_good,
            "drift_summary": self.drift_summary,
            "cooldown_remaining_seconds": self.codex_cooldown_remaining(),
            **guard_info,
        }
        if self.latest_probe:
            run_state_updates.update(
                {
                    "conversation_ready": bool(self.latest_probe.get("conversation_ready", False)),
                    "minimal_usable_ready": bool(self.latest_probe.get("minimal_usable_ready", False)),
                    "conversation_status": str(self.latest_probe.get("conversation_status", "down") or "down"),
                    "conversation_probe_summary": str(self.latest_probe.get("conversation_probe_summary", "") or ""),
                }
            )
        should_refresh_incident_index = False
        should_clear_incident_context = False
        if self.pre_repair_backup_result != "not-run":
            run_state_updates["last_backup_at"] = self.run_ts
        if self.rollback_occurred:
            run_state_updates["last_rollback_at"] = self.run_ts
            run_state_updates["last_rollback_summary_archive_file"] = self.rollback_summary_archive_file
        if new_state == "healthy":
            self.reset_failure_count()
            self.incident_backup_marker.unlink(missing_ok=True)
            self.pre_repair_backup_result = "not-run"
            if self.incident_dir is not None:
                self.update_incident_state("resolved", summary, resolved=True)
                should_refresh_incident_index = True
                should_clear_incident_context = True
            run_state_updates["last_success_at"] = self.run_ts
            run_state_updates["current_incident_id"] = ""
            run_state_updates["current_incident_state"] = ""
            run_state_updates["current_incident_age_seconds"] = 0
        elif new_state == "recovered":
            self.reset_failure_count()
            if self.incident_dir is not None:
                self.update_incident_state("resolved", summary, resolved=True)
                run_state_updates["current_incident_id"] = self.incident_id
                run_state_updates["current_incident_state"] = "resolved"
                should_refresh_incident_index = True
            run_state_updates["last_success_at"] = self.run_ts
            run_state_updates["last_recovered_at"] = self.run_ts
        elif new_state == "degraded":
            run_state_updates["last_degraded_at"] = self.run_ts
        elif new_state == "failed":
            if self.incident_dir is not None:
                self.update_incident_state("open", summary)
                run_state_updates["current_incident_id"] = self.incident_id
                run_state_updates["current_incident_state"] = "open"
                should_refresh_incident_index = True
            run_state_updates["last_failed_at"] = self.run_ts
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
            self.notify(f"⚠️ OpenClaw watchdog 状态变化\n时间：{self.run_ts}\n{report_text}")
        elif new_state == "recovered" and old_state != "recovered" and self.config.watchdog_notify_on_recovery:
            self.notify(f"✅ OpenClaw watchdog 状态变化\n时间：{self.run_ts}\n{report_text}")
        elif new_state == "failed" and old_state != "failed" and self.config.watchdog_notify_on_failure:
            self.notify(
                f"❌ OpenClaw watchdog 状态变化\n时间：{self.run_ts}\n{report_text}\n日志：{self.config.watchdog_log_file}"
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

    def prune_incident_archives(self) -> None:
        handoff_ops.prune_incident_archives(self)

    def ensure_incident_context(self) -> None:
        handoff_ops.ensure_incident_context(self)

    def copy_if_exists(self, src: Path, dest: Path) -> None:
        handoff_ops.copy_if_exists(self, src, dest)

    def render_codex_prompt(self, summary: str) -> None:
        handoff_ops.render_codex_prompt(self, summary)

    def pid_is_alive(self, pid: str) -> bool:
        return handoff_ops.pid_is_alive(self, pid)

    def trigger_opencode_fallback(self, reason: str) -> None:
        handoff_ops.trigger_opencode_fallback(self, reason)

    def trigger_codex_autorun(self) -> None:
        handoff_ops.trigger_codex_autorun(self)

    def collect_incident_bundle(
        self,
        summary: str,
        doctor_output: str,
        active: str,
        main_pid: str,
        listeners: str,
    ) -> None:
        handoff_ops.collect_incident_bundle(self, summary, doctor_output, active, main_pid, listeners)

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

    def _run_once_legacy(self) -> RunOutcome:
        start_ts = datetime.now().astimezone()
        self.last_run_started_at = start_ts
        self.run_ts = start_ts.strftime("%F %T %Z")
        self.write_run_state({"last_run_started_at": start_ts.isoformat(timespec="seconds")})
        self.log("INFO", "watchdog tick start")

        try:
            probe = self.live_probe(include_doctor=True, apply_grace=True)
            doctor_output = str(probe.get("doctor_output", ""))
            config_invalid = bool(probe.get("config_invalid", False))
            process_layer_healthy = bool(probe.get("process_layer_healthy", False))
            service_layer_healthy = bool(probe.get("service_layer_healthy", True))
            active = "true" if probe.get("service_active") else "false"
            main_pid = str(probe.get("service_main_pid", "0"))
            listeners = [str(item) for item in probe.get("listener_pids", [])]
            listeners_str = " ".join(listeners) if listeners else "none"
            self.log(
                "INFO",
                f"precheck active={active} main_pid={main_pid or '0'} listeners={listeners_str} "
                f"doctor_rc={probe.get('doctor_rc', 0)} service_probe={probe.get('service_probe_summary', 'n/a')}",
            )

            run_state = self.read_run_state()
            previous_service_probe_failures = int(run_state.get("service_probe_failures", 0) or 0)
            if self.config.watchdog_enable_service_level_probe and process_layer_healthy and not service_layer_healthy:
                service_probe_failures = previous_service_probe_failures + 1
            else:
                service_probe_failures = 0
            service_probe_threshold_met = (
                self.config.watchdog_enable_service_level_probe
                and process_layer_healthy
                and not service_layer_healthy
                and service_probe_failures >= self.config.watchdog_service_level_failure_threshold
            )
            initial_health_level = "healthy"
            if config_invalid or not process_layer_healthy:
                initial_health_level = "failed"
            elif process_layer_healthy and not service_layer_healthy:
                initial_health_level = "degraded"
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
                    ),
                    "cooldown_remaining_seconds": self.codex_cooldown_remaining(),
                }
            )

            need_remediation = config_invalid or not process_layer_healthy or service_probe_threshold_met
            if need_remediation:
                self.run_pre_repair_backup()

            if config_invalid:
                self.log("WARN", "detected invalid OpenClaw config")
                if self.restore_last_good():
                    self.restart_service()
                    probe = self.live_probe(include_doctor=True, apply_grace=True)
                    doctor_output = str(probe.get("doctor_output", doctor_output))
                    config_invalid = bool(probe.get("config_invalid", False))
                    process_layer_healthy = bool(probe.get("process_layer_healthy", False))
                    service_layer_healthy = bool(probe.get("service_layer_healthy", True))
                    active = "true" if probe.get("service_active") else "false"
                    main_pid = str(probe.get("service_main_pid", "0"))
                    listeners = [str(item) for item in probe.get("listener_pids", [])]
                    listeners_str = " ".join(listeners) if listeners else "none"
                    if self.config.watchdog_enable_service_level_probe and process_layer_healthy and not service_layer_healthy:
                        service_probe_failures += 1
                        self.write_run_state(
                            {
                                "service_probe_failures": service_probe_failures,
                                "last_service_probe_at": str(probe.get("service_probe_checked_at", self.now_iso())),
                                "last_service_probe_result": "healthy" if service_layer_healthy else "degraded",
                                "last_service_probe_summary": str(probe.get("service_probe_summary", "")),
                                "last_service_probe_rc": int(probe.get("service_probe_rc", 0) or 0),
                            }
                        )
                else:
                    self.increment_failure_count()
                    self.collect_incident_bundle("配置无效，且没有 last-good 备份可恢复", doctor_output, active, main_pid, listeners_str)
                    self.trigger_codex_autorun()
                    self.write_incident_operator_summary(
                        summary="配置无效，且没有 last-good 备份可恢复",
                        active=active,
                        main_pid=main_pid,
                        listeners=listeners_str,
                    )
                    summary = (
                        f"配置无效，且没有 last-good；incident={self.incident_dir or 'none'}；"
                        f"codex_handoff={self.codex_handoff_file or 'none'}；codex_result={self.codex_trigger_result or 'not-run'}"
                    )
                    self.set_state("failed", summary)
                    return RunOutcome(exit_code=1, state="failed", summary=summary)

            if process_layer_healthy and service_layer_healthy:
                self.backup_last_good()
                self.write_run_state({"service_probe_failures": 0})
                summary = "service active and listener matches service process tree"
                self.set_state("healthy", summary)
                self.log("INFO", "watchdog tick healthy")
                return RunOutcome(exit_code=0, state="healthy", summary=summary)

            if process_layer_healthy and not service_layer_healthy and not service_probe_threshold_met:
                summary = (
                    f"service layer degraded: {probe.get('service_probe_summary', 'status probe failed')} "
                    f"({service_probe_failures}/{self.config.watchdog_service_level_failure_threshold})"
                )
                self.set_state("degraded", summary)
                self.log("WARN", f"watchdog degraded without remediation: {summary}")
                return RunOutcome(exit_code=0, state="degraded", summary=summary)

            if active != "true" and self.listener_count() > 0:
                self.kill_stray_listeners(main_pid)

            self.run_doctor_repair()
            self.restart_service()

            final_probe = self.live_probe(include_doctor=False, apply_grace=True)
            final_process_layer_healthy = bool(final_probe.get("process_layer_healthy", False))
            final_service_layer_healthy = bool(final_probe.get("service_layer_healthy", True))
            if final_process_layer_healthy and final_service_layer_healthy:
                self.backup_last_good()
                self.write_run_state(
                    {
                        "service_probe_failures": 0,
                        "last_service_probe_at": str(final_probe.get("service_probe_checked_at", self.now_iso())),
                        "last_service_probe_result": "healthy",
                        "last_service_probe_summary": str(final_probe.get("service_probe_summary", "")),
                        "last_service_probe_rc": int(final_probe.get("service_probe_rc", 0) or 0),
                    }
                )
                summary = "watchdog restarted gateway successfully"
                self.set_state("recovered", summary)
                self.log("INFO", "watchdog recovered service")
                return RunOutcome(exit_code=0, state="recovered", summary=summary)

            final_active = "true" if final_probe.get("service_active") else "false"
            final_pid = str(final_probe.get("service_main_pid", "0"))
            final_listeners = [str(item) for item in final_probe.get("listener_pids", [])]
            final_listeners_str = " ".join(final_listeners) if final_listeners else "none"
            final_summary = (
                f"active={final_active} main_pid={final_pid or '0'} listeners={final_listeners_str} "
                f"service_probe={final_probe.get('service_probe_summary', 'n/a')}"
            )

            self.increment_failure_count()
            self.write_run_state(
                {
                    "service_probe_failures": service_probe_failures if final_process_layer_healthy and not final_service_layer_healthy else 0,
                    "last_service_probe_at": str(final_probe.get("service_probe_checked_at", self.now_iso())),
                    "last_service_probe_result": "healthy" if final_service_layer_healthy else "degraded",
                    "last_service_probe_summary": str(final_probe.get("service_probe_summary", "")),
                    "last_service_probe_rc": int(final_probe.get("service_probe_rc", 0) or 0),
                    "health_level": "failed",
                    "current_mode": self.current_mode(maintenance=self.config.watchdog_maintenance_file.exists()),
                    "cooldown_remaining_seconds": self.codex_cooldown_remaining(),
                }
            )
            self.collect_incident_bundle(
                f"deterministic remediation failed: {final_summary}",
                doctor_output,
                final_active,
                final_pid,
                final_listeners_str,
            )
            self.trigger_codex_autorun()
            self.write_incident_operator_summary(
                summary=f"deterministic remediation failed: {final_summary}",
                active=final_active,
                main_pid=final_pid,
                listeners=final_listeners_str,
            )
            summary = (
                f"{final_summary}；incident={self.incident_dir or 'none'}；"
                f"codex_handoff={self.codex_handoff_file or 'none'}；codex_result={self.codex_trigger_result or 'not-run'}"
            )
            self.set_state("failed", summary)
            self.log(
                "ERROR",
                f"watchdog failed to recover: {final_summary} incident={self.incident_dir or 'none'} codex={self.codex_trigger_result or 'not-run'}",
            )
            return RunOutcome(exit_code=1, state="failed", summary=summary)
        finally:
            finish_ts = datetime.now().astimezone()
            self.last_run_finished_at = finish_ts
            duration_ms = max(0, int((finish_ts - start_ts).total_seconds() * 1000))
            self.write_run_state(
                {
                    "last_run_finished_at": finish_ts.isoformat(timespec="seconds"),
                    "last_run_duration_ms": duration_ms,
                }
            )

    def _service_probe_failures_for(self, probe: dict[str, object], previous_failures: int) -> int:
        process_layer_healthy = bool(probe.get("process_layer_healthy", False))
        service_layer_healthy = bool(probe.get("service_layer_healthy", True))
        if self.config.watchdog_enable_service_level_probe and process_layer_healthy and not service_layer_healthy:
            return previous_failures + 1
        return 0

    def _write_probe_run_state(self, probe: dict[str, object], *, config_invalid: bool, service_probe_failures: int) -> str:
        self.latest_probe = dict(probe)
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
        elif process_layer_healthy and not service_layer_healthy and not self.config.watchdog_enable_survivability_flow:
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
                    survival=self.survival_mode_active,
                ),
                "cooldown_remaining_seconds": self.codex_cooldown_remaining(),
                "conversation_ready": conversation_ready,
                "minimal_usable_ready": minimal_usable_ready,
                "conversation_status": str(probe.get("conversation_status", "down") or "down"),
                "conversation_probe_summary": str(probe.get("conversation_probe_summary", "") or ""),
                **survival_ops.run_state_fields(self),
            }
        )
        return initial_health_level

    def _run_once_survivability(self) -> RunOutcome:
        start_ts = datetime.now().astimezone()
        self.last_run_started_at = start_ts
        self.run_ts = start_ts.strftime("%F %T %Z")
        self.write_run_state({"last_run_started_at": start_ts.isoformat(timespec="seconds")})
        self.log("INFO", "watchdog tick start (survivability flow)")
        self.reset_recovery_tracking()
        last_good = self.last_good_status()
        self.last_good_validated_at = str(last_good.get("last_good_validated_at", "") or "")
        self.last_good_generation_id = str(last_good.get("last_good_generation_id", "") or "")
        self.last_good_generation_count = int(last_good.get("last_good_generation_count", 0) or 0)

        try:
            probe = self.live_probe(include_doctor=True, apply_grace=True)
            self.latest_probe = dict(probe)
            doctor_output = str(probe.get("doctor_output", ""))
            config_invalid = bool(probe.get("config_invalid", False))
            self.sync_survival_mode(probe=probe, config_invalid=config_invalid)
            process_layer_healthy = bool(probe.get("process_layer_healthy", False))
            service_layer_healthy = bool(probe.get("service_layer_healthy", True))
            conversation_ready = bool(probe.get("conversation_ready", False))
            minimal_usable_ready = bool(probe.get("minimal_usable_ready", False))
            active = "true" if probe.get("service_active") else "false"
            main_pid = str(probe.get("service_main_pid", "0"))
            listeners = [str(item) for item in probe.get("listener_pids", [])]
            listeners_str = " ".join(listeners) if listeners else "none"
            self.log(
                "INFO",
                f"survivability precheck active={active} main_pid={main_pid or '0'} listeners={listeners_str} "
                f"doctor_rc={probe.get('doctor_rc', 0)} service_probe={probe.get('service_probe_summary', 'n/a')} "
                f"conversation={probe.get('conversation_status', 'down')}",
            )

            run_state = self.read_run_state()
            previous_service_probe_failures = int(run_state.get("service_probe_failures", 0) or 0)
            service_probe_failures = self._service_probe_failures_for(probe, previous_service_probe_failures)
            service_probe_threshold_met = (
                self.config.watchdog_enable_service_level_probe
                and process_layer_healthy
                and not service_layer_healthy
                and service_probe_failures >= self.config.watchdog_service_level_failure_threshold
            )
            self._write_probe_run_state(probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)

            if process_layer_healthy and conversation_ready and not config_invalid:
                self.finalize_recovery_tracking(strategy="steady-state", restored_conversation=True)
                if not self.survival_mode_active:
                    self.backup_last_good(validation=probe)
                summary = "conversation ready and gateway listener healthy"
                self.set_state("healthy", summary)
                self.log("INFO", "watchdog tick healthy (survivability flow)")
                return RunOutcome(exit_code=0, state="healthy", summary=summary)

            if process_layer_healthy and minimal_usable_ready and not config_invalid and not service_probe_threshold_met:
                self.finalize_recovery_tracking(strategy="minimal-usable", restored_conversation=True)
                summary = f"minimal usable conversation only: {probe.get('conversation_probe_summary', 'n/a')}"
                self.set_state("degraded", summary)
                self.log("WARN", f"watchdog degraded without remediation: {summary}")
                return RunOutcome(exit_code=0, state="degraded", summary=summary)

            self.record_recovery_step(
                "diagnose",
                "diagnosed",
                "config-invalid"
                if config_invalid
                else "process-down"
                if not process_layer_healthy
                else "service-threshold"
                if service_probe_threshold_met
                else str(probe.get("conversation_status", "down") or "down"),
            )
            drift = self.drift_context()
            self.config_drift_detected = bool(drift.get("detected", False))
            self.drift_scope = [str(item) for item in drift.get("scope", []) if str(item).strip()]
            self.drift_since_last_good = str(drift.get("since_last_good", "") or "")
            self.drift_summary = str(drift.get("summary", "") or "")

            self.run_pre_repair_backup()

            if config_invalid:
                self.record_recovery_step("restart", "skipped", "config-invalid")
            else:
                if active != "true" and self.listener_count() > 0:
                    self.kill_stray_listeners(main_pid)
                restart_ok = self.restart_service()
                self.record_recovery_step("restart", "success" if restart_ok else "failed", "systemctl")
                if restart_ok:
                    restart_probe = self.live_probe(include_doctor=True, apply_grace=True)
                    self.latest_probe = dict(restart_probe)
                    doctor_output = str(restart_probe.get("doctor_output", doctor_output))
                    config_invalid = bool(restart_probe.get("config_invalid", False))
                    service_probe_failures = self._service_probe_failures_for(restart_probe, service_probe_failures)
                    self._write_probe_run_state(restart_probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
                    if bool(restart_probe.get("minimal_usable_ready", False)):
                        self.finalize_recovery_tracking(strategy="restart", restored_conversation=True)
                        if bool(restart_probe.get("conversation_ready", False)):
                            self.backup_last_good(validation=restart_probe)
                        summary = (
                            "restart restored conversation readiness"
                            if bool(restart_probe.get("conversation_ready", False))
                            else "restart restored minimal usable conversation"
                        )
                        self.set_state("recovered", summary)
                        self.log("INFO", f"watchdog recovered via restart: {summary}")
                        return RunOutcome(exit_code=0, state="recovered", summary=summary)

            if self.config.watchdog_last_good_config.exists() or self.config.watchdog_last_good_manifest_file.exists():
                rollback_reason = (
                    "config-invalid"
                    if config_invalid
                    else "config-drift"
                    if self.config_drift_detected
                    else "restart-did-not-restore-conversation"
                )
                rollback_ok = self.restore_last_good(reason=rollback_reason)
                self.record_recovery_step(
                    "rollback",
                    "success" if rollback_ok else "failed",
                    self.rollback_candidate_used or rollback_reason,
                )
                if rollback_ok:
                    rollback_restart_ok = self.restart_service()
                    self.record_recovery_step("rollback-restart", "success" if rollback_restart_ok else "failed", "systemctl")
                    if rollback_restart_ok:
                        rollback_probe = self.live_probe(include_doctor=True, apply_grace=True)
                        self.latest_probe = dict(rollback_probe)
                        doctor_output = str(rollback_probe.get("doctor_output", doctor_output))
                        config_invalid = bool(rollback_probe.get("config_invalid", False))
                        service_probe_failures = self._service_probe_failures_for(rollback_probe, service_probe_failures)
                        self._write_probe_run_state(rollback_probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
                        if bool(rollback_probe.get("minimal_usable_ready", False)):
                            self.finalize_recovery_tracking(strategy="rollback", restored_conversation=True)
                            if bool(rollback_probe.get("conversation_ready", False)):
                                self.backup_last_good(validation=rollback_probe)
                            summary = (
                                f"rollback restored conversation readiness (candidate={self.rollback_candidate_used or 'unknown'})"
                                if bool(rollback_probe.get("conversation_ready", False))
                                else f"rollback restored minimal usable conversation (candidate={self.rollback_candidate_used or 'unknown'})"
                            )
                            self.set_state("recovered", summary)
                            self.log("INFO", f"watchdog recovered via rollback: {summary}")
                            return RunOutcome(exit_code=0, state="recovered", summary=summary)
            else:
                self.record_recovery_step("rollback", "skipped", "no-last-good")

            survival_reason = (
                "config-invalid"
                if config_invalid
                else "config-drift"
                if self.config_drift_detected
                else str(probe.get("conversation_status", "down") or "down")
            )
            survival_result = self.enter_survival_mode(reason=survival_reason)
            if bool(survival_result.get("applied", False)):
                self.record_recovery_step("survival", "success", survival_reason)
                survival_restart_ok = self.restart_service()
                self.record_recovery_step("survival-restart", "success" if survival_restart_ok else "failed", "systemctl")
                if survival_restart_ok:
                    survival_probe = self.live_probe(include_doctor=True, apply_grace=True)
                    self.latest_probe = dict(survival_probe)
                    doctor_output = str(survival_probe.get("doctor_output", doctor_output))
                    config_invalid = bool(survival_probe.get("config_invalid", False))
                    service_probe_failures = self._service_probe_failures_for(survival_probe, service_probe_failures)
                    self._write_probe_run_state(survival_probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
                    if bool(survival_probe.get("minimal_usable_ready", False)):
                        self.finalize_recovery_tracking(strategy="survival", restored_conversation=True)
                        summary = (
                            "survival mode restored conversation readiness"
                            if bool(survival_probe.get("conversation_ready", False))
                            else "survival mode restored minimal usable conversation"
                        )
                        self.set_state("recovered", summary, health_level_override="degraded")
                        self.log("WARN", f"watchdog recovered via survival mode: {summary}")
                        return RunOutcome(exit_code=0, state="recovered", summary=summary)
            else:
                self.record_recovery_step("survival", "skipped", str(survival_result.get("detail", "not-applicable") or "not-applicable"))

            if self.config.watchdog_enable_doctor_repair:
                self.run_doctor_repair()
                self.record_recovery_step("doctor", "success", "repair-ran")
                doctor_restart_ok = self.restart_service()
                self.record_recovery_step("doctor-restart", "success" if doctor_restart_ok else "failed", "systemctl")
                if doctor_restart_ok:
                    doctor_probe = self.live_probe(include_doctor=True, apply_grace=True)
                    self.latest_probe = dict(doctor_probe)
                    doctor_output = str(doctor_probe.get("doctor_output", doctor_output))
                    config_invalid = bool(doctor_probe.get("config_invalid", False))
                    service_probe_failures = self._service_probe_failures_for(doctor_probe, service_probe_failures)
                    self._write_probe_run_state(doctor_probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
                    if bool(doctor_probe.get("minimal_usable_ready", False)):
                        self.finalize_recovery_tracking(strategy="doctor", restored_conversation=True)
                        if bool(doctor_probe.get("conversation_ready", False)):
                            self.backup_last_good(validation=doctor_probe)
                        summary = (
                            "doctor repair restored conversation readiness"
                            if bool(doctor_probe.get("conversation_ready", False))
                            else "doctor repair restored minimal usable conversation"
                        )
                        self.set_state("recovered", summary)
                        self.log("INFO", f"watchdog recovered via doctor repair: {summary}")
                        return RunOutcome(exit_code=0, state="recovered", summary=summary)
            else:
                self.record_recovery_step("doctor", "skipped", "disabled")

            final_probe = dict(self.latest_probe) if self.latest_probe else self.live_probe(include_doctor=False, apply_grace=True)
            final_process_layer_healthy = bool(final_probe.get("process_layer_healthy", False))
            final_service_layer_healthy = bool(final_probe.get("service_layer_healthy", True))
            final_active = "true" if final_probe.get("service_active") else "false"
            final_pid = str(final_probe.get("service_main_pid", "0"))
            final_listeners = [str(item) for item in final_probe.get("listener_pids", [])]
            final_listeners_str = " ".join(final_listeners) if final_listeners else "none"
            final_summary = (
                f"conversation={final_probe.get('conversation_status', 'down')} active={final_active} main_pid={final_pid or '0'} "
                f"listeners={final_listeners_str} service_probe={final_probe.get('service_probe_summary', 'n/a')} "
                f"recovery_path={self.recovery_path_text()}"
            )

            self.finalize_recovery_tracking(strategy="escalated", restored_conversation=False)
            self.increment_failure_count()
            self.write_run_state(
                {
                    "service_probe_failures": service_probe_failures if final_process_layer_healthy and not final_service_layer_healthy else 0,
                    "last_service_probe_at": str(final_probe.get("service_probe_checked_at", self.now_iso())),
                    "last_service_probe_result": "healthy" if final_service_layer_healthy else "degraded",
                    "last_service_probe_summary": str(final_probe.get("service_probe_summary", "")),
                    "last_service_probe_rc": int(final_probe.get("service_probe_rc", 0) or 0),
                    "health_level": "failed",
                    "current_mode": self.current_mode(maintenance=self.config.watchdog_maintenance_file.exists(), survival=self.survival_mode_active),
                    "cooldown_remaining_seconds": self.codex_cooldown_remaining(),
                    "conversation_ready": bool(final_probe.get("conversation_ready", False)),
                    "minimal_usable_ready": bool(final_probe.get("minimal_usable_ready", False)),
                    "conversation_status": str(final_probe.get("conversation_status", "down") or "down"),
                    "conversation_probe_summary": str(final_probe.get("conversation_probe_summary", "") or ""),
                    "last_recovery_strategy": self.last_recovery_strategy,
                    "last_recovery_path": self.recovery_path_text(),
                    "last_recovery_action_count": self.last_recovery_action_count,
                    "last_recovery_restored_conversation": self.last_recovery_restored_conversation,
                    "rollback_candidate_used": self.rollback_candidate_used,
                    "rollback_reason": self.rollback_reason,
                    "config_drift_detected": self.config_drift_detected,
                    "drift_scope": list(self.drift_scope),
                    "drift_since_last_good": self.drift_since_last_good,
                    "drift_summary": self.drift_summary,
                    **survival_ops.run_state_fields(self),
                    **self.guard_status(),
                }
            )
            self.collect_incident_bundle(
                f"survivability remediation failed: {final_summary}",
                doctor_output,
                final_active,
                final_pid,
                final_listeners_str,
            )
            self.trigger_codex_autorun()
            self.write_incident_operator_summary(
                summary=f"survivability remediation failed: {final_summary}",
                active=final_active,
                main_pid=final_pid,
                listeners=final_listeners_str,
            )
            summary = (
                f"{final_summary}；incident={self.incident_dir or 'none'}；"
                f"codex_handoff={self.codex_handoff_file or 'none'}；codex_result={self.codex_trigger_result or 'not-run'}"
            )
            self.set_state("failed", summary)
            self.log(
                "ERROR",
                f"watchdog failed to recover: {final_summary} incident={self.incident_dir or 'none'} codex={self.codex_trigger_result or 'not-run'}",
            )
            return RunOutcome(exit_code=1, state="failed", summary=summary)
        finally:
            finish_ts = datetime.now().astimezone()
            self.last_run_finished_at = finish_ts
            duration_ms = max(0, int((finish_ts - start_ts).total_seconds() * 1000))
            self.write_run_state(
                {
                    "last_run_finished_at": finish_ts.isoformat(timespec="seconds"),
                    "last_run_duration_ms": duration_ms,
                }
            )

    def run_once(self) -> RunOutcome:
        if self.config.watchdog_enable_survivability_flow:
            return self._run_once_survivability()
        return self._run_once_legacy()
