from __future__ import annotations

from pathlib import Path

from openclaw_watchdog import survival_policy_runtime
from openclaw_watchdog import survival_state_runtime
from openclaw_watchdog import survival_transition_runtime


def _stable_required_runs(engine) -> int:
    return survival_state_runtime.stable_required_runs(engine)


def _default_state(engine) -> dict[str, object]:
    return survival_state_runtime.default_state(engine)


def read_survival_state(engine) -> dict[str, object]:
    return survival_state_runtime.read_survival_state(engine)


def write_survival_state(engine, state: dict[str, object]) -> dict[str, object]:
    return survival_state_runtime.write_survival_state(engine, state)


def _apply_state_to_engine(engine, state: dict[str, object]) -> None:
    survival_state_runtime.apply_state_to_engine(engine, state)


def run_state_fields(engine) -> dict[str, object]:
    return survival_state_runtime.run_state_fields(engine)


def clear_survival_mode(engine, *, reason: str, exit_kind: str = 'automatic') -> dict[str, object]:
    return survival_transition_runtime.clear_survival_mode(engine, reason=reason, exit_kind=exit_kind)


def sync_survival_mode(engine, *, probe: dict[str, object], config_invalid: bool) -> dict[str, object]:
    return survival_transition_runtime.sync_survival_mode(engine, probe=probe, config_invalid=config_invalid)


def _load_candidate_config(path: Path) -> dict[str, object] | None:
    return survival_policy_runtime.load_candidate_config(path)


def _select_source_config(engine) -> tuple[dict[str, object] | None, str, str]:
    return survival_policy_runtime.select_source_config(engine)


def _normalize_channels(raw: object) -> dict[str, dict[str, object]]:
    return survival_policy_runtime.normalize_channels(raw)


def build_survival_plan(engine, *, reason: str) -> dict[str, object] | None:
    return survival_policy_runtime.build_survival_plan(engine, reason=reason)


def enter_survival_mode(engine, *, reason: str) -> dict[str, object]:
    return survival_transition_runtime.enter_survival_mode(engine, reason=reason)
