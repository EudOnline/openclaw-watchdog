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
2. guarded `model-failover` of the configured OpenClaw primary model after repeated recent model HTTP non-200 failures
3. `rollback` to the last known good snapshot
4. `survival` mode
5. `doctor`
6. rescue dispatch

This ordering is intentional: cheap, bounded, reversible steps happen first; broader or more opinionated repair moves happen later. The watchdog no longer tries to preserve old compatibility branches.

The `model-failover` step is additionally bounded by two operator-facing rails:

- cooldown still prevents immediate repeated switches after a recent apply;
- `WATCHDOG_MODEL_FAILOVER_MAX_APPLIES_PER_DAY` stops further automatic rewrites after the configured 24-hour cap and reports `rate-limited` instead of silently churning the model list.

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

For the model-failover path specifically, confirm these fields together:

- `status --summary`: `model_failover=<status>`, `non200=<count>`, and `to=<target>` when the signal is actionable;
- `report --message`: `model_failover=status=...` plus `recent_non_200=...`;
- `report --json` and `metrics --json`: `model_http_error_*` and `model_failover_last_*`;
- `metrics --prometheus`: `openclaw_watchdog_model_http_error_count`, `openclaw_watchdog_model_http_error_latest_status`, and `openclaw_watchdog_model_failover_last_applied_timestamp`.

## 7. Fast rollback for model failover

If operators need to stop automatic model rotation during an incident or rollout:

```bash
WATCHDOG_ENABLE_MODEL_HTTP_ERROR_FAILOVER="false"
```

After the watchdog service restarts or reloads with that env value, future runs stop rewriting the OpenClaw model primary and fall back to the rest of the deterministic repair chain.

## 8. Internal ownership after the refactor

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
