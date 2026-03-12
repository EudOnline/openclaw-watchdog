# Rescue lifecycle guide

This guide explains the end-to-end OpenClaw-specific rescue lifecycle that the watchdog now enforces.

## 1. Detect and read-only validation first

The safe entrypoint is still read-only:

1. `detect` inventories OpenClaw, rescue executors, and config surfaces without installing anything.
2. `check` probes process, service, and conversation readiness.
3. `status --summary` and `report --message` give the operator a compact view of what is broken and what would be protected during remediation.

Use this phase to confirm that OpenClaw is already present on the host, that the configured rescue chain matches your intent, and that the editable-path boundaries only cover the OpenClaw files you are willing to mutate.

## 2. Deterministic repair order

When `run-once` enters remediation, it follows one deterministic sequence before any model-assisted rescue is allowed:

1. `restart`
2. `rollback` to the last known good snapshot
3. `survival` mode
4. `doctor`
5. rescue dispatch

This ordering is intentional: cheap, bounded, reversible steps happen first; broader or more opinionated repair moves happen later. The watchdog no longer tries to preserve old compatibility branches.

## 3. Rescue dispatch order

If deterministic repair does not restore a usable path, watchdog dispatches rescue in the configured priority order:

1. `Codex`
2. `Claude Code`
3. `Gemini CLI`
4. `OpenCode`
5. `LiteLLM`
6. local `rule-agent`

External executors may propose structured rescue plans, but they do not get arbitrary shell access and they do not install missing software.

## 4. Local action execution boundary

All host mutation stays inside the local allow-listed executor. In practice this means:

- restart / rollback / survival / doctor remain local primitives;
- OpenClaw config edits are limited to explicit editable files and dotted keys;
- JSON writes are atomic temp-file-and-replace operations;
- validation gates may roll a plan back if service health, minimal usability, conversation readiness, or config validity gets worse.

## 5. Learning and candidate promotion

Every recovered run may produce structured learning output:

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

The watchdog keeps `WatchdogEngine` as the composition root, but the detailed rescue/incident state handling is now delegated:

- `watchdog_v2/incident_service.py` for incident payloads, indexes, and current-incident state
- `watchdog_v2/rescue_context_builder.py` for rescue-context creation and LiteLLM client wiring
- `watchdog_v2/rescue_learning_service.py` for learning persistence and candidate-rule promotion status
- `watchdog_v2/probe_run_state.py` for probe-failure counting and run-state projection
- `watchdog_v2/event_history.py` for event history parsing and recent-window statistics
