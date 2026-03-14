# Rescue lifecycle guide

This guide explains the end-to-end OpenClaw fallback system lifecycle that the watchdog now enforces.

## 1. Detect and read-only validation first

The safe entrypoint is still read-only:

1. `detect` inventories OpenClaw, rescue executors, and config surfaces without installing anything.
2. `check` probes process, service, and conversation readiness.
3. `status --summary` and `report --message` give the operator a compact view of what is broken and what would be protected during remediation.

Use this phase to confirm that OpenClaw is already present on the host, that the configured rescue chain matches your intent, and that the editable-path boundaries only cover the OpenClaw files you are willing to mutate. This system does not install missing rescue tools for you.

The `bootstrap` command is now a read-only readiness inspector. It reports executor inventory, config placeholders, plugin presence, and runtime markers, and returns `attention` when follow-up is still required.

## 2. Deterministic repair order

When `run-once` enters remediation, it follows one deterministic sequence before any model-assisted rescue is allowed:

1. `restart`
2. `rollback` to the last known good snapshot
3. `survival` mode
4. `doctor`
5. rescue dispatch

This ordering is intentional: cheap, bounded, reversible steps happen first; broader or more opinionated repair moves happen later. The watchdog no longer tries to preserve old compatibility branches.

## 3. Rescue dispatch order

If deterministic repair does not restore a usable path, the fallback system dispatches rescue in this fixed priority order:

1. `Codex`
2. `Claude Code`
3. `Gemini CLI`
4. `OpenCode`
5. `LiteLLM`
6. local `rule-agent`

External executors may propose structured rescue plans, but they do not get arbitrary shell access, they do not install missing software, and they only succeed if their plan stays inside the configured OpenClaw mutation boundary.

## 4. Local action execution boundary

All host mutation stays inside the local allow-listed executor. In practice this means:

- restart / rollback / survival / doctor remain local primitives;
- OpenClaw config edits are limited to explicit editable files and exact-or-descendant dotted-key prefixes;
- JSON writes are atomic temp-file-and-replace operations;
- dispatch rejects unsafe config-mutation plans before execution, and execution validates the same policy again before writing;
- validation gates may roll a plan back if service health, minimal usability, conversation readiness, or config validity gets worse.

## 5. Learning and candidate promotion

Every recovered run in the fallback system may produce structured learning output:

- cases are persisted under the local learning store;
- matching now prefers a normalized failure signature over raw summary text;
- recovered low-risk evidence can auto-promote a candidate rule;
- high-risk regressions send rules back to pending review;
- repeated failed outcomes can suppress a learned rule so the static heuristic or another executor wins instead.

## 6. Operator outputs to inspect

During and after recovery, the operator should inspect these surfaces together:

- `status --summary` for compact current state and rescue-chain highlights;
- `report --json` / `report --message` for recovery narrative, attention items, and recent incidents;
- `metrics --json` / `metrics --prometheus` for dashboards and alerting;
- `incidents current` / `incidents queue` for open operational follow-up.

The `status`, `report`, and `metrics` outputs now share one operator snapshot for the rescue-chain fields, so attempt order, rejected executors, learning summary, and mutation scope stay aligned.

## 7. Internal ownership after the refactor

The fallback system keeps `WatchdogEngine` as the composition root, but the detailed rescue/incident state handling is now delegated:

- `openclaw_watchdog/incident_service.py` for incident payloads, indexes, and current-incident state
- `openclaw_watchdog/rescue_context_builder.py` for rescue-context creation and LiteLLM client wiring
- `openclaw_watchdog/rescue_runtime.py` for rescue adapter assembly, dispatch ordering, and local plan execution handoff
- `openclaw_watchdog/rescue_policy.py` for explicit OpenClaw mutation boundaries and unsafe-plan rejection rules
- `openclaw_watchdog/rescue_learning_service.py` for learning persistence and candidate-rule promotion status
- `openclaw_watchdog/probe_run_state.py` for probe-failure counting and run-state projection
- `openclaw_watchdog/flows/rescue_run.py` as the single public recovery coordinator, with `openclaw_watchdog/flows/recovery_probe_runtime.py`, `openclaw_watchdog/flows/recovery_finalize_runtime.py`, `openclaw_watchdog/flows/deterministic_recovery_runtime.py`, and `openclaw_watchdog/flows/rescue_phase_runtime.py` owning the concrete phase logic behind the thin `openclaw_watchdog/flows/recovery_phases.py` facade
- `openclaw_watchdog/maintenance_runtime.py` for maintenance-mode file toggles and status handoff
- `openclaw_watchdog/engine_support_runtime.py` for state-dir prep, file locking, logging, notifications, failure counters, and small engine host helpers
- `openclaw_watchdog/doctor_runtime.py` for `doctor` subprocess execution and config-invalid detection
- `openclaw_watchdog/last_good_runtime.py` for last-good manifests, guard snapshots, protected-path archive metadata, and drift projection
- `openclaw_watchdog/rollback_runtime.py` for rollback summary generation, rollback archive retention, and restore execution
- `openclaw_watchdog/repair_action_runtime.py` for pre-repair backup, restart, stray-listener cleanup, and doctor-repair side effects
- `openclaw_watchdog/state_transition.py` for state-change side effects, incident refresh/clear rules, and notification gating
- `openclaw_watchdog/event_runtime.py` for event snapshot persistence and event-history append handoff
- `openclaw_watchdog/event_history.py` for event history parsing and recent-window statistics
- `openclaw_watchdog/health.py` and `openclaw_watchdog/reporting.py` for operator-facing observability payloads, with CLI formatting and maintenance-status rendering now calling these module owners directly instead of routing through extra `WatchdogEngine` wrappers

The same is now true for incident handling and repair ownership: `reporting.py`, `health.py`, `cli.py`, and `state_transition.py` call `incident_service.py` / `incidents.py` directly, while repair-related callers use `doctor_runtime.py`, `last_good_runtime.py`, `rollback_runtime.py`, and `repair_action_runtime.py` directly instead of routing through compatibility wrappers.
