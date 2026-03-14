from __future__ import annotations

from pathlib import Path

from openclaw_watchdog import state_store


def read_run_state(
    run_state_file: Path,
    *,
    stable_required_runs: int,
    guard_manifest_file: Path | None = None,
) -> dict[str, object]:
    return state_store.read_run_state(
        run_state_file,
        stable_required_runs=stable_required_runs,
        guard_manifest_file=guard_manifest_file,
    )


def write_run_state(
    run_state_file: Path,
    updates: dict[str, object],
    *,
    stable_required_runs: int,
    guard_manifest_file: Path | None = None,
) -> dict[str, object]:
    return state_store.write_run_state(
        run_state_file,
        updates,
        stable_required_runs=stable_required_runs,
        guard_manifest_file=guard_manifest_file,
    )
