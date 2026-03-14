# Internal architecture

This document describes the post-refactor internal structure of the OpenClaw-specific fallback system.

## Design goals

The current layout keeps the OpenClaw-specific fallback surface coherent while making the implementation easier to test and evolve:

- keep canonical CLI names, required output fields, and rehearsal semantics clear for operators and automation
- keep the rescue chain fixed as `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`
- move ad-hoc dict handling behind typed models and explicit serialization boundaries
- isolate human-readable rendering from command dispatch
- reduce `openclaw_watchdog/engine.py` to a runtime facade and dependency container
- make orchestration readable in dedicated flow modules
- keep bootstrap behavior read-only while splitting executor detection and prerequisite inspection into focused helpers
- keep config mutation bounded to explicit OpenClaw file and key policies

## Package map

### Core runtime primitives

- `openclaw_watchdog/config.py` parses env/config and defines filesystem layout
- `openclaw_watchdog/runtime.py` owns subprocess execution primitives
- `openclaw_watchdog/state_store.py` owns persistence helpers for JSON/text snapshots
- `openclaw_watchdog/health.py` builds probe payloads and status snapshots
- `openclaw_watchdog/engine_support_runtime.py` owns state-dir prep, file locking, logging, notifications, failure counters, and small engine host helpers
- `openclaw_watchdog/doctor_runtime.py` owns `openclaw doctor --non-interactive` execution and config-invalid parsing
- `openclaw_watchdog/last_good_runtime.py` owns last-good manifests, protected-path snapshots, drift context, and guard manifest persistence
- `openclaw_watchdog/rollback_runtime.py` owns rollback summaries, rollback archive pruning, and last-good restore execution
- `openclaw_watchdog/repair_action_runtime.py` owns pre-repair backup, service restart, stray-listener cleanup, and doctor-repair actions

### Typed models

- `openclaw_watchdog/models.py` defines typed dataclasses for probe state, run state, incidents, and bootstrap summaries
- the models keep `from_dict()` / `to_dict()` adapters only at real persistence and CLI boundaries
- read-heavy consumers such as reporting and incident context now normalize payloads through these dataclasses first

### Presentation layer

- `openclaw_watchdog/presenters/status.py` renders compact operator status summaries
- `openclaw_watchdog/presenters/report.py` renders human-readable report output
- `openclaw_watchdog/presenters/incidents.py` renders incident queue text output
- `openclaw_watchdog/presenters/bootstrap.py` renders bootstrap summaries
- `openclaw_watchdog/cli.py` keeps parser + dispatch + JSON branching, and delegates text formatting to presenters

### Engine facade and run context

- `openclaw_watchdog/run_context.py` defines mutable per-run state such as recovery metadata, rescue attempt order, learning summaries, survival-mode state, and current timestamps
- `openclaw_watchdog/engine.py` keeps long-lived dependencies and only the smallest shared filesystem helpers on the engine itself
- mutable runtime-only fields live under `engine.ctx`; there is no legacy attribute bridge

### Run flows

For the operator/contributor walkthrough of this path, see [rescue-lifecycle.md](rescue-lifecycle.md).


- `openclaw_watchdog/flows/rescue_run.py` contains the single rescue-first `run-once` orchestration path
- deterministic repair always runs in one order: restart -> rollback -> survival -> doctor -> rescue dispatch
- `openclaw_watchdog/engine.py` is now primarily a composition root and thin facade for the CLI-facing operations
- `openclaw_watchdog/incident_service.py` owns incident payload parsing, index refresh, and current-incident context wiring
- `openclaw_watchdog/executor_registry.py` owns the fixed canonical rescue-chain order, command resolution, executor availability checks, and per-executor runtime settings
- `openclaw_watchdog/maintenance_runtime.py` owns maintenance-mode file writes/removal and hands status rendering back to health payload helpers
- `openclaw_watchdog/engine_support_runtime.py` owns state-dir prep, file locking, logging, notifications, failure counters, and small engine host helpers
- `openclaw_watchdog/doctor_runtime.py` owns `doctor` subprocess execution and config-invalid detection
- `openclaw_watchdog/last_good_runtime.py` owns last-good candidate selection, protected-path archive/restore metadata, drift projection, and guard-event persistence
- `openclaw_watchdog/rollback_runtime.py` owns rollback diff summarization, rollback archive retention, and last-good restore execution flow
- `openclaw_watchdog/repair_action_runtime.py` owns pre-repair backup, service restart, stray-listener cleanup, and doctor-repair subprocess flows
- core callers such as `engine.py`, `survival.py`, and `rescue_actions.py` now import these focused modules directly; there is no remaining `repair.py` compatibility layer in the current surface
- incident readers/writers now call `incident_service.py` and `incidents.py` directly from `reporting.py`, `health.py`, `cli.py`, and `state_transition.py` instead of routing through an `engine.py` incident façade
- observability helpers now also call their owning modules directly: `event_runtime.py` appends via `event_history.py`, `health.py` reads event history / last-good / guard state directly, `maintenance_runtime.py` hands status rendering to `health.py`, and `cli.py` formats Prometheus output through `reporting.py` instead of keeping extra `engine.py` wrappers
- `openclaw_watchdog/rescue_context_builder.py` owns failure-signature normalization, executor inventory shaping, rescue context construction, and LiteLLM client construction
- `openclaw_watchdog/rescue_runtime.py` owns rescue adapter assembly, dispatch wiring, and local rescue-plan execution handoff
- `openclaw_watchdog/rescue_learning_service.py` owns rescue learning case persistence and candidate-rule promotion mapping
- `openclaw_watchdog/rescue_policy.py` owns OpenClaw rescue boundaries such as editable files, editable key prefixes, mutation scope summaries, and dispatch-time plan validation
- `openclaw_watchdog/probe_run_state.py` owns probe failure counting and probe-to-run-state projection
- `openclaw_watchdog/flows/rescue_run.py` now calls `probe_run_state.py`, `rescue_context_builder.py`, `rescue_runtime.py`, and `rescue_learning_service.py` directly, with test-only override hooks living in the flow instead of more `engine.py` forwarding methods
- `openclaw_watchdog/service_runtime.py` owns `systemctl` / `ss` / `ps` based service and listener tree probing
- `openclaw_watchdog/state_transition.py` owns state-change side effects, run-state write shaping, incident refresh/clear rules, and notification gating
- `openclaw_watchdog/event_runtime.py` owns event payload persistence, text/json snapshot writes, and event-history append handoff
- low-level repair / health / incident primitives stay in their focused modules; rollback bookkeeping and imperative repair actions no longer share one monolithic file

### Bootstrap pipeline

- `openclaw_watchdog/bootstrap.py` keeps the public `Bootstrapper` and final payload shaping
- `openclaw_watchdog/bootstrap_inventory.py` owns rescue-executor and OpenClaw binary detection
- `openclaw_watchdog/bootstrap_inspectors.py` owns read-only config, plugin, and runtime-marker inspection
- `openclaw_watchdog/bootstrap_steps.py` coordinates the ordered detect-only bootstrap steps:
  - detect OpenCode
  - detect Codex / Claude Code / Gemini CLI
  - detect `LiteLLM` specialist-agent readiness
  - detect OpenClaw availability
  - inspect QQ plugin and default channel prerequisites
  - scan Feishu runtime markers
- `openclaw_watchdog/models.BootstrapSummary` remains the serializable bootstrap payload and executor inventory snapshot

## Validation layers

The repository now uses three complementary validation layers for the OpenClaw fallback system:

1. **Unit / focused output tests** for models, presenters, reporting, events, runtime helpers, rescue dispatch, and learning
2. **Direct orchestration tests** for run context, the unified rescue flow, and bootstrap steps
3. **Sequential critical rehearsals** for the `LiteLLM` tier, rule-agent tier, candidate auto-promotion, and pending-review paths in a bounded local harness

## Operational boundaries

The watchdog explicitly protects these operational boundaries:

- canonical CLI names under `scripts/openclaw-watchdog`
- the fixed rescue order `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`
- no automatic installation of OpenClaw, rescue CLIs, or model clients
- rescue config writes only within the explicit OpenClaw file allowlist and exact-or-descendant key policy
- report / metrics fields that rehearsals, live acceptance, or dashboards actually consume
- Prometheus metric names emitted by `metrics --prometheus` when they drive alerting or visibility
- rehearsal scenario intent and expected operator recovery flows

## Non-goals

These changes intentionally do not introduce a framework, service container, or event bus. The code stays standard-library-first and pragmatic: smaller modules, clearer seams, and only the output surfaces that help OpenClaw operations. This is not a general-purpose platform; it is an OpenClaw-specific fallback system.
