from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openclaw_watchdog import bootstrap_inspectors, bootstrap_inventory, bootstrap_steps as bootstrap_step_ops
from openclaw_watchdog.config import Config
from openclaw_watchdog.models import BootstrapSummary


@dataclass(frozen=True)
class ShellResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def output(self) -> str:
        return f"{self.stdout}{self.stderr}"


@dataclass(frozen=True)
class BootstrapOutcome:
    exit_code: int
    state: str
    summary: str
    payload: dict[str, Any]


class BootstrapError(RuntimeError):
    pass


class Bootstrapper:
    def __init__(self, config: Config):
        self.config = config

    @property
    def bootstrap_error(self):
        return BootstrapError

    def empty_shell_result(self) -> ShellResult:
        return ShellResult(command='', returncode=1, stdout='', stderr='empty candidate')

    def run(self) -> BootstrapOutcome:
        bootstrap_summary = BootstrapSummary.initial(config_path=str(self.config.openclaw_config))
        result = bootstrap_step_ops.run_bootstrap_pipeline(self, bootstrap_summary)
        return self.finish(result.bootstrap_summary, state=result.state, summary=result.message, exit_code=result.exit_code)

    def finish(
        self,
        bootstrap_summary: BootstrapSummary,
        *,
        state: str,
        summary: str,
        exit_code: int,
    ) -> BootstrapOutcome:
        bootstrap_summary.state = state
        bootstrap_summary.summary = summary
        bootstrap_summary.exit_code = exit_code
        return BootstrapOutcome(
            exit_code=exit_code,
            state=state,
            summary=summary,
            payload=bootstrap_summary.to_dict(),
        )

    def unique_nonempty(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    def run_shell(self, command: str, *, timeout: int | None = None) -> ShellResult:
        try:
            completed = subprocess.run(
                ['/bin/bash', '-c', command],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            return ShellResult(
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout or '',
                stderr=completed.stderr or '',
            )
        except subprocess.TimeoutExpired as exc:
            return ShellResult(
                command=command,
                returncode=124,
                stdout=exc.stdout or '',
                stderr=exc.stderr or f'timed out after {timeout}s',
                timed_out=True,
            )

    def detect_binary(self, candidate: str) -> tuple[bool, str, ShellResult]:
        candidate = candidate.strip()
        if not candidate:
            return False, '', self.empty_shell_result()
        if '/' in candidate:
            resolved = str(Path(candidate).expanduser())
            available = os.access(resolved, os.X_OK)
            return (
                available,
                resolved if available else '',
                ShellResult(
                    command=f'test -x {resolved}',
                    returncode=0 if available else 1,
                    stdout=f'{resolved}\n' if available else '',
                    stderr='',
                ),
            )
        detected = shutil.which(candidate) or ''
        return (
            bool(detected),
            detected,
            ShellResult(
                command=f'command -v {candidate}',
                returncode=0 if detected else 1,
                stdout=f'{detected}\n' if detected else '',
                stderr='',
            ),
        )

    def _detect_openclaw_binary(self) -> tuple[bool, str, ShellResult]:
        return self.detect_binary('openclaw')

    def detect_openclaw(self) -> dict[str, Any]:
        available, detected_binary, detect_result = self._detect_openclaw_binary()
        return {
            'available': available,
            'binary': detected_binary,
            'detect_returncode': detect_result.returncode,
        }

    def detect_first_available(self, *candidates: str) -> dict[str, Any]:
        return bootstrap_inventory.detect_first_available(self, *candidates)

    def detect_codex(self) -> dict[str, Any]:
        return bootstrap_inventory.detect_codex(self)

    def detect_claude_code(self) -> dict[str, Any]:
        return bootstrap_inventory.detect_claude_code(self)

    def detect_gemini_cli(self) -> dict[str, Any]:
        return bootstrap_inventory.detect_gemini_cli(self)

    def detect_litellm(self) -> dict[str, Any]:
        return bootstrap_inventory.detect_litellm(self)

    def populate_opencode_watchdog_status(self, payload: dict[str, Any]) -> None:
        bootstrap_inventory.populate_opencode_watchdog_status(self, payload)

    def inspect_opencode_config(self) -> dict[str, Any]:
        return bootstrap_inspectors.inspect_opencode_config(self)

    def detect_opencode(self) -> dict[str, Any]:
        return bootstrap_inventory.detect_opencode(self)

    def inspect_qq_plugin(self) -> dict[str, Any]:
        return bootstrap_inspectors.inspect_qq_plugin(self)

    def inspect_default_channel_config(self) -> dict[str, Any]:
        return bootstrap_inspectors.inspect_default_channel_config(self)

    def load_json_object(self, path: Path, *, label: str, allow_jsonc: bool) -> dict[str, Any]:
        return bootstrap_inspectors.load_json_object(self, path, label=label, allow_jsonc=allow_jsonc)

    def normalize_jsonc(self, text: str) -> str:
        return bootstrap_inspectors.normalize_jsonc(text)

    def strip_jsonc_comments(self, text: str) -> str:
        return bootstrap_inspectors.strip_jsonc_comments(text)

    def strip_trailing_commas(self, text: str) -> str:
        return bootstrap_inspectors.strip_trailing_commas(text)

    def detect_feishu_runtime_markers(self) -> dict[str, Any]:
        return bootstrap_inspectors.detect_feishu_runtime_markers(self)

    def log_candidates(self) -> list[Path]:
        return bootstrap_inspectors.log_candidates(self)

    def read_logging_file_from_config(self) -> Path | None:
        return bootstrap_inspectors.read_logging_file_from_config(self)

    def read_tail(self, path: Path, max_bytes: int = 262144) -> str:
        return bootstrap_inspectors.read_tail(path, max_bytes=max_bytes)
