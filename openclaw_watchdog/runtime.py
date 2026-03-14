from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def output(self) -> str:
        if self.stdout and self.stderr:
            return f"{self.stdout.rstrip()}\n{self.stderr.rstrip()}\n"
        return self.stdout or self.stderr


def run_command(
    args: list[str],
    *,
    timeout: int | None = None,
    cwd: Path | None = None,
    merge_stderr: bool = False,
    input_text: str | None = None,
) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
            cwd=str(cwd) if cwd is not None else None,
            timeout=timeout,
            check=False,
        )
        if merge_stderr:
            return CommandResult(args=args, returncode=completed.returncode, stdout=completed.stdout or '', stderr='')
        return CommandResult(
            args=args,
            returncode=completed.returncode,
            stdout=completed.stdout or '',
            stderr=completed.stderr or '',
        )
    except FileNotFoundError as exc:
        return CommandResult(args=args, returncode=127, stdout='', stderr=str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ''
        stderr = exc.stderr or f'timed out after {timeout}s'
        return CommandResult(args=args, returncode=124, stdout=stdout, stderr=stderr, timed_out=True)


def run_capture_to_file(args: list[str], destination: Path, *, timeout: int | None = None, cwd: Path | None = None) -> None:
    result = run_command(args, timeout=timeout, cwd=cwd, merge_stderr=True)
    destination.write_text(result.output, encoding='utf-8')
