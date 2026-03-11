# Internal architecture

This document describes the post-refactor internal structure of OpenClaw Watchdog.

## Design goals

The current layout keeps the public surface stable while making the implementation easier to test and evolve:

- keep canonical CLI names, JSON keys, and rehearsal semantics stable
- move ad-hoc dict handling behind typed compatibility models
- isolate human-readable rendering from command dispatch
- reduce `watchdog_v2/engine.py` to a runtime facade and dependency container
- make orchestration readable in dedicated flow modules
- keep bootstrap behavior stable while splitting it into ordered internal steps

## Package map

### Core runtime primitives

- `watchdog_v2/config.py` parses env/config and defines filesystem layout
- `watchdog_v2/runtime.py` owns subprocess execution primitives
- `watchdog_v2/state_store.py` owns persistence helpers for JSON/text snapshots
- `watchdog_v2/health.py` builds probe payloads and status snapshots
- `watchdog_v2/repair.py` owns restart / rollback / backup primitives

### Typed models

- `watchdog_v2/models.py` defines compatibility dataclasses for probe state, run state, incidents, and bootstrap summaries
- the models keep `from_dict()` / `to_dict()` adapters so existing persisted payloads remain readable
- read-heavy consumers such as reporting and incident context now normalize payloads through these dataclasses first

### Presentation layer

- `watchdog_v2/presenters/status.py` renders compact operator status summaries
- `watchdog_v2/presenters/report.py` renders human-readable report output
- `watchdog_v2/presenters/incidents.py` renders incident queue text output
- `watchdog_v2/presenters/bootstrap.py` renders bootstrap summaries
- `watchdog_v2/cli.py` keeps parser + dispatch + JSON branching, and delegates text formatting to presenters

### Engine facade and run context

- `watchdog_v2/run_context.py` defines mutable per-run state such as recovery metadata, survival-mode state, incident handoff files, and current timestamps
- `watchdog_v2/engine.py` keeps long-lived dependencies and filesystem helpers on the engine itself
- runtime-only fields are bridged through `engine.ctx`, which lets older `engine.<field>` call sites continue working during migration

### Run flows

- `watchdog_v2/flows/legacy_run.py` contains the legacy `run-once` orchestration path
- `watchdog_v2/flows/survivability_run.py` contains the survivability-first orchestration path
- `watchdog_v2/engine.py` now selects the active flow and delegates into those modules
- low-level repair / health / incident primitives stay in their focused modules; only orchestration moved out

### Bootstrap pipeline

- `watchdog_v2/bootstrap.py` keeps the public `Bootstrapper` and final payload shaping
- `watchdog_v2/bootstrap_steps.py` coordinates the ordered internal steps:
  - ensure OpenCode
  - detect Codex
  - detect / install OpenClaw
  - ensure QQ plugin
  - scaffold default channel config
  - scan Feishu runtime markers
- `watchdog_v2/models.BootstrapSummary` remains the serializable compatibility payload

## Validation layers

The repository now uses three complementary validation layers:

1. **Unit / contract tests** for models, presenters, reporting, events, and runtime compatibility
2. **Direct orchestration tests** for run context, run flows, and bootstrap steps
3. **Rehearsal smoke scenarios** for end-to-end operator behavior in a bounded local harness

## Compatibility boundaries

The refactor explicitly protects these public boundaries:

- canonical CLI names under `scripts/openclaw-watchdog`
- stable top-level keys in `report --json` and `metrics --json`
- Prometheus metric names emitted by `metrics --prometheus`
- rehearsal scenario intent and expected operator flows

## Non-goals

These changes intentionally do not introduce a framework, service container, or event bus. The code stays standard-library-first and pragmatic: smaller modules, clearer seams, and compatibility shims only where they reduce migration risk.
