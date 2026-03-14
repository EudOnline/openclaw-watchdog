from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from openclaw_watchdog import engine_support_runtime
from openclaw_watchdog import run_state_service
from openclaw_watchdog.config import Config
from openclaw_watchdog.runtime import CommandResult, run_capture_to_file, run_command
from openclaw_watchdog.run_context import RunContext


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
        engine_support_runtime.prepare_state_dirs(self)

    def acquire_lock(self) -> bool:
        return engine_support_runtime.acquire_lock(self)

    def release_lock(self) -> None:
        engine_support_runtime.release_lock(self)

    def log(self, level: str, message: str) -> None:
        engine_support_runtime.log(self, level, message)

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
        engine_support_runtime.notify(self, message)

    def append_rollback_summary(self, text: str) -> str:
        return engine_support_runtime.append_rollback_summary(self, text)

    def read_failure_count(self) -> int:
        return engine_support_runtime.read_failure_count(self)

    def write_failure_count(self, count: int) -> None:
        engine_support_runtime.write_failure_count(self, count)

    def reset_failure_count(self) -> None:
        engine_support_runtime.reset_failure_count(self)

    def increment_failure_count(self) -> int:
        return engine_support_runtime.increment_failure_count(self)

    def now_iso(self) -> str:
        return engine_support_runtime.now_iso(self)

    def read_run_state(self) -> dict[str, object]:
        return run_state_service.read_run_state(
            self.run_state_file,
            stable_required_runs=self.config.watchdog_survival_stable_ready_runs,
            guard_manifest_file=self.config.watchdog_guard_manifest_file,
        )

    def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
        return run_state_service.write_run_state(
            self.run_state_file,
            updates,
            stable_required_runs=self.config.watchdog_survival_stable_ready_runs,
            guard_manifest_file=self.config.watchdog_guard_manifest_file,
        )

    def current_mode(self, *, maintenance: bool, degraded: bool = False, survival: bool = False) -> str:
        return engine_support_runtime.current_mode(
            maintenance=maintenance,
            degraded=degraded,
            survival=survival,
        )

    def sibling_json_path(self, path: Path) -> Path:
        return engine_support_runtime.sibling_json_path(path)

    def run_once(self) -> RunOutcome:
        from openclaw_watchdog.flows import rescue_run

        return rescue_run.run(self, self.ctx)
