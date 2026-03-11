from __future__ import annotations

import json
import shutil
from pathlib import Path

from watchdog_v2 import repair as repair_ops


def _stable_required_runs(engine) -> int:
    return max(1, int(engine.config.watchdog_survival_stable_ready_runs))


def _default_state(engine) -> dict[str, object]:
    return {
        "active": False,
        "entered_at": "",
        "exited_at": "",
        "exit_reason": "",
        "reason": "",
        "summary": "",
        "actions": [],
        "disabled_features": [],
        "required_channels": list(engine.config.watchdog_survival_required_channels),
        "config_path": str(engine.config.watchdog_survival_config_file),
        "source_config_path": "",
        "source_config_fingerprint": "",
        "applied_config_fingerprint": "",
        "previous_config_backup_path": "",
        "sticky": False,
        "sticky_reason": "",
        "exit_ready": False,
        "exit_policy": "manual-clear-or-reconfig",
        "exit_blockers": [],
        "stable_ready_runs": 0,
        "stable_required_runs": _stable_required_runs(engine),
        "stable_ready_since": "",
        "manual_clear_required": False,
        "config_changed_away": False,
        "last_exit_at": "",
        "last_exit_reason": "",
        "last_exit_kind": "",
        "last_exit_summary": "",
    }


def read_survival_state(engine) -> dict[str, object]:
    state = _default_state(engine)
    try:
        payload = json.loads(engine.config.watchdog_survival_state_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return state
    if isinstance(payload, dict):
        state.update(payload)
    return state


def write_survival_state(engine, state: dict[str, object]) -> dict[str, object]:
    payload = _default_state(engine)
    payload.update(state)
    engine.config.watchdog_survival_state_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_survival_state_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _apply_state_to_engine(engine, state: dict[str, object]) -> None:
    ctx = engine.ctx
    ctx.survival_mode_active = bool(state.get("active", False))
    ctx.survival_mode_reason = str(state.get("reason", "") or "") if ctx.survival_mode_active else ""
    ctx.survival_mode_since = str(state.get("entered_at", "") or "") if ctx.survival_mode_active else ""
    ctx.survival_mode_summary = str(state.get("summary", "") or "") if ctx.survival_mode_active else ""
    ctx.survival_mode_actions = [str(item) for item in state.get("actions", []) if str(item).strip()] if ctx.survival_mode_active else []
    ctx.survival_mode_disabled_features = [
        str(item) for item in state.get("disabled_features", []) if str(item).strip()
    ] if ctx.survival_mode_active else []
    ctx.survival_mode_config_file = (
        str(state.get("config_path", engine.config.watchdog_survival_config_file) or engine.config.watchdog_survival_config_file)
        if ctx.survival_mode_active
        else ""
    )
    ctx.survival_mode_sticky = bool(state.get("sticky", False)) if ctx.survival_mode_active else False
    ctx.survival_mode_sticky_reason = str(state.get("sticky_reason", "") or "") if ctx.survival_mode_active else ""
    ctx.survival_mode_exit_ready = bool(state.get("exit_ready", False)) if ctx.survival_mode_active else False
    ctx.survival_mode_exit_policy = str(state.get("exit_policy", "") or "") if ctx.survival_mode_active else "none"
    ctx.survival_mode_exit_blockers = [
        str(item) for item in state.get("exit_blockers", []) if str(item).strip()
    ] if ctx.survival_mode_active else []
    ctx.survival_mode_stable_ready_runs = int(state.get("stable_ready_runs", 0) or 0) if ctx.survival_mode_active else 0
    ctx.survival_mode_stable_required_runs = int(state.get("stable_required_runs", _stable_required_runs(engine)) or _stable_required_runs(engine))
    ctx.survival_mode_manual_clear_required = bool(state.get("manual_clear_required", False)) if ctx.survival_mode_active else False
    ctx.survival_mode_config_changed_away = bool(state.get("config_changed_away", False)) if ctx.survival_mode_active else False
    ctx.survival_mode_last_exit_at = str(state.get("last_exit_at", "") or "")
    ctx.survival_mode_last_exit_reason = str(state.get("last_exit_reason", "") or "")
    ctx.survival_mode_last_exit_kind = str(state.get("last_exit_kind", "") or "")
    ctx.survival_mode_last_exit_summary = str(state.get("last_exit_summary", "") or "")


def run_state_fields(engine) -> dict[str, object]:
    ctx = engine.ctx
    return {
        "survival_mode_active": ctx.survival_mode_active,
        "survival_mode_reason": ctx.survival_mode_reason,
        "survival_mode_since": ctx.survival_mode_since,
        "survival_mode_summary": ctx.survival_mode_summary,
        "survival_mode_actions": list(ctx.survival_mode_actions),
        "survival_mode_disabled_features": list(ctx.survival_mode_disabled_features),
        "survival_mode_config_file": ctx.survival_mode_config_file,
        "survival_mode_sticky": ctx.survival_mode_sticky,
        "survival_mode_sticky_reason": ctx.survival_mode_sticky_reason,
        "survival_mode_exit_ready": ctx.survival_mode_exit_ready,
        "survival_mode_exit_policy": ctx.survival_mode_exit_policy,
        "survival_mode_exit_blockers": list(ctx.survival_mode_exit_blockers),
        "survival_mode_stable_ready_runs": ctx.survival_mode_stable_ready_runs,
        "survival_mode_stable_required_runs": ctx.survival_mode_stable_required_runs,
        "survival_mode_manual_clear_required": ctx.survival_mode_manual_clear_required,
        "survival_mode_config_changed_away": ctx.survival_mode_config_changed_away,
        "survival_mode_last_exit_at": ctx.survival_mode_last_exit_at,
        "survival_mode_last_exit_reason": ctx.survival_mode_last_exit_reason,
        "survival_mode_last_exit_kind": ctx.survival_mode_last_exit_kind,
        "survival_mode_last_exit_summary": ctx.survival_mode_last_exit_summary,
    }


def clear_survival_mode(engine, *, reason: str, exit_kind: str = "automatic") -> dict[str, object]:
    previous = read_survival_state(engine)
    exited_at = engine.now_iso()
    state = _default_state(engine)
    state.update(
        {
            "active": False,
            "required_channels": [],
            "config_path": "",
            "source_config_path": "",
            "source_config_fingerprint": "",
            "applied_config_fingerprint": "",
            "previous_config_backup_path": "",
            "exited_at": exited_at,
            "exit_reason": reason,
            "last_exit_at": exited_at,
            "last_exit_reason": reason,
            "last_exit_kind": exit_kind,
            "last_exit_summary": str(previous.get("summary", "") or ""),
        }
    )
    state = write_survival_state(engine, state)
    _apply_state_to_engine(engine, state)
    engine.log("INFO", f"survival mode cleared kind={exit_kind} reason={reason}")
    return state


def sync_survival_mode(engine, *, probe: dict[str, object], config_invalid: bool) -> dict[str, object]:
    state = read_survival_state(engine)
    if not bool(state.get("active", False)):
        _apply_state_to_engine(engine, state)
        return state

    applied_fingerprint = str(state.get("applied_config_fingerprint", "") or "")
    current_fingerprint = repair_ops.fingerprint_path(engine.config.openclaw_config)
    config_changed_away = bool(applied_fingerprint and current_fingerprint and applied_fingerprint != current_fingerprint)
    conversation_ready = bool(probe.get("conversation_ready", False))
    minimal_usable_ready = bool(probe.get("minimal_usable_ready", conversation_ready))
    stable_required_runs = max(1, int(state.get("stable_required_runs", _stable_required_runs(engine)) or _stable_required_runs(engine)))
    stable_ready_runs = int(state.get("stable_ready_runs", 0) or 0)
    stable_ready_since = str(state.get("stable_ready_since", "") or "")

    if conversation_ready and not config_invalid:
        stable_ready_runs += 1
        if not stable_ready_since:
            stable_ready_since = engine.now_iso()
    else:
        stable_ready_runs = 0
        stable_ready_since = ""

    exit_ready = conversation_ready and not config_invalid and stable_ready_runs >= stable_required_runs
    exit_policy = "automatic" if config_changed_away else "manual-clear-or-reconfig"

    blockers: list[str] = []
    if config_invalid:
        blockers.append("config invalid")
    if not minimal_usable_ready:
        blockers.append("minimal conversation not yet usable")
    elif not conversation_ready:
        blockers.append("full conversation not yet ready")
    if stable_ready_runs < stable_required_runs:
        blockers.append(f"waiting for stable full-ready window {stable_ready_runs}/{stable_required_runs}")
    if exit_ready and not config_changed_away:
        blockers.append("still running survival config; manual-clear-or-reconfig required")

    state.update(
        {
            "sticky": not (exit_ready and config_changed_away),
            "sticky_reason": blockers[0] if blockers else "",
            "exit_ready": exit_ready,
            "exit_policy": exit_policy,
            "exit_blockers": blockers,
            "stable_ready_runs": stable_ready_runs,
            "stable_required_runs": stable_required_runs,
            "stable_ready_since": stable_ready_since,
            "manual_clear_required": bool(exit_ready and not config_changed_away),
            "config_changed_away": config_changed_away,
        }
    )

    if exit_ready and config_changed_away:
        state = clear_survival_mode(engine, reason="stable-ready-config-recovered", exit_kind="automatic")
    else:
        state = write_survival_state(engine, state)
        _apply_state_to_engine(engine, state)
    return state


def _load_candidate_config(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _select_source_config(engine) -> tuple[dict[str, object] | None, str, str]:
    current = _load_candidate_config(engine.config.openclaw_config)
    if current is not None:
        return current, str(engine.config.openclaw_config), repair_ops.fingerprint_path(engine.config.openclaw_config)
    for candidate in repair_ops.last_good_candidates(engine):
        path = Path(str(candidate.get("path", "") or ""))
        payload = _load_candidate_config(path)
        if payload is not None:
            return payload, str(path), repair_ops.fingerprint_path(path)
    return None, "", ""


def _normalize_channels(raw: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw, dict):
        return {}
    channels: dict[str, dict[str, object]] = {}
    for name, details in raw.items():
        if isinstance(details, dict):
            channels[str(name)] = details
    return channels


def build_survival_plan(engine, *, reason: str) -> dict[str, object] | None:
    source_config, source_path, source_fingerprint = _select_source_config(engine)
    if source_config is None:
        return None

    plan_config = json.loads(json.dumps(source_config, ensure_ascii=False))
    channels = _normalize_channels(plan_config.get("channels", {}))
    if not channels:
        return None
    plan_config["channels"] = channels

    requested = [channel for channel in engine.config.watchdog_survival_required_channels if channel in channels]
    enabled = [name for name, details in channels.items() if bool(details.get("enabled", False))]
    kept = requested or enabled[:1] or list(channels.keys())[:1]
    if not kept:
        return None

    actions: list[str] = []
    disabled_features: list[str] = []
    for name, details in channels.items():
        should_enable = name in kept
        if bool(details.get("enabled", False)) != should_enable:
            details["enabled"] = should_enable
            if should_enable:
                actions.append(f"enabled required channel {name}")
            else:
                actions.append(f"disabled optional channel {name}")
        if not should_enable:
            disabled_features.append(f"channel:{name}")

    if engine.config.watchdog_survival_disable_optional_extensions:
        for key in ("extensions", "mcpServers", "services", "workers", "schedules"):
            if key not in plan_config:
                continue
            current = plan_config.get(key)
            if isinstance(current, dict) and current:
                plan_config[key] = {}
                actions.append(f"cleared optional section {key}")
                disabled_features.append(f"section:{key}")
            elif isinstance(current, list) and current:
                plan_config[key] = []
                actions.append(f"cleared optional section {key}")
                disabled_features.append(f"section:{key}")

    kept_channels = [name for name in channels if name in kept]
    disabled_channels = [name for name in channels if name not in kept]
    summary = (
        f"kept channels={','.join(kept_channels)}; "
        f"disabled={','.join(disabled_channels) if disabled_channels else 'none'}"
    )
    if not actions:
        actions.append("reused existing minimal channel-only config")

    return {
        "config": plan_config,
        "summary": summary,
        "reason": reason,
        "actions": actions,
        "disabled_features": disabled_features,
        "required_channels": kept_channels,
        "source_config_path": source_path,
        "source_config_fingerprint": source_fingerprint,
    }


def enter_survival_mode(engine, *, reason: str) -> dict[str, object]:
    if not engine.config.watchdog_enable_survival_mode:
        return {"applied": False, "detail": "disabled"}

    state = read_survival_state(engine)
    if bool(state.get("active", False)):
        _apply_state_to_engine(engine, state)
        return {"applied": False, "detail": "already-active", "state": state}

    plan = build_survival_plan(engine, reason=reason)
    if plan is None:
        return {"applied": False, "detail": "no-usable-config-basis"}

    rendered = json.dumps(plan["config"], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    json.loads(rendered)

    guard_before = repair_ops.protected_paths_snapshot(engine.config)
    repair_ops.record_guard_event(
        engine.config,
        operation="survival-mode-apply",
        phase="before",
        before=guard_before,
        context={
            "reason": reason,
            "source_config_path": plan.get("source_config_path", ""),
        },
    )

    previous_backup_path = ""
    if engine.config.openclaw_config.exists():
        backup_path = engine.config.watchdog_rollback_archive_dir / f"survival-preapply.{engine.now_iso().replace(':', '').replace('+', '_')}.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(engine.config.openclaw_config, backup_path)
        previous_backup_path = str(backup_path)

    engine.config.watchdog_survival_config_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_survival_config_file.write_text(rendered, encoding="utf-8")
    engine.config.openclaw_config.parent.mkdir(parents=True, exist_ok=True)
    engine.config.openclaw_config.write_text(rendered, encoding="utf-8")

    guard_after = repair_ops.protected_paths_snapshot(engine.config)
    repair_ops.record_guard_event(
        engine.config,
        operation="survival-mode-apply",
        phase="after",
        before=guard_before,
        after=guard_after,
        validation="survival-config-json-valid",
        context={
            "reason": reason,
            "summary": plan.get("summary", ""),
            "required_channels": list(plan.get("required_channels", [])),
        },
    )

    state = write_survival_state(
        engine,
        {
            "active": True,
            "entered_at": engine.now_iso(),
            "exited_at": "",
            "exit_reason": "",
            "reason": reason,
            "summary": str(plan.get("summary", "") or ""),
            "actions": list(plan.get("actions", [])),
            "disabled_features": list(plan.get("disabled_features", [])),
            "required_channels": list(plan.get("required_channels", [])),
            "config_path": str(engine.config.watchdog_survival_config_file),
            "source_config_path": str(plan.get("source_config_path", "") or ""),
            "source_config_fingerprint": str(plan.get("source_config_fingerprint", "") or ""),
            "applied_config_fingerprint": repair_ops.fingerprint_path(engine.config.openclaw_config),
            "previous_config_backup_path": previous_backup_path,
            "sticky": True,
            "sticky_reason": f"waiting for stable full-ready window 0/{_stable_required_runs(engine)}",
            "exit_ready": False,
            "exit_policy": "manual-clear-or-reconfig",
            "exit_blockers": [f"waiting for stable full-ready window 0/{_stable_required_runs(engine)}"],
            "stable_ready_runs": 0,
            "stable_required_runs": _stable_required_runs(engine),
            "stable_ready_since": "",
            "manual_clear_required": False,
            "config_changed_away": False,
            "last_exit_at": "",
            "last_exit_reason": "",
            "last_exit_kind": "",
            "last_exit_summary": "",
        },
    )
    _apply_state_to_engine(engine, state)
    engine.log(
        "WARN",
        f"survival mode activated reason={reason} summary={state.get('summary', '')} actions={'; '.join(engine.survival_mode_actions) or 'none'}",
    )
    return {"applied": True, "detail": "applied", "state": state}
