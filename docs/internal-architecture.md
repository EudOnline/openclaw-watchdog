# Internal architecture

This document describes the post-refactor internal structure of OpenClaw Watchdog.

## Design goals

The current layout keeps the operator-facing fallback surface coherent while making the implementation easier to test and evolve:

- keep canonical CLI names, required output fields, and rehearsal semantics clear for operators and automation
- move ad-hoc dict handling behind typed models and explicit serialization boundaries
- isolate human-readable rendering from command dispatch
- reduce `watchdog_v2/engine.py` to a runtime facade and dependency container
- make orchestration readable in dedicated flow modules
- keep bootstrap behavior object-first while splitting it into ordered internal steps

## Package map

### Core runtime primitives

- `watchdog_v2/config.py` parses env/config and defines filesystem layout
- `watchdog_v2/runtime.py` owns subprocess execution primitives
- `watchdog_v2/state_store.py` owns persistence helpers for JSON/text snapshots
- `watchdog_v2/health.py` builds probe payloads and status snapshots
- `watchdog_v2/repair.py` owns restart / rollback / backup primitives

### Typed models

- `watchdog_v2/models.py` defines typed dataclasses for probe state, run state, incidents, and bootstrap summaries
- the models keep `from_dict()` / `to_dict()` adapters only at real persistence and CLI boundaries
- read-heavy consumers such as reporting and incident context now normalize payloads through these dataclasses first

### Presentation layer

- `watchdog_v2/presenters/status.py` renders compact operator status summaries
- `watchdog_v2/presenters/report.py` renders human-readable report output
- `watchdog_v2/presenters/incidents.py` renders incident queue text output
- `watchdog_v2/presenters/bootstrap.py` renders bootstrap summaries
- `watchdog_v2/cli.py` keeps parser + dispatch + JSON branching, and delegates text formatting to presenters

### Engine facade and run context

- `watchdog_v2/run_context.py` defines mutable per-run state such as recovery metadata, rescue attempt order, learning summaries, survival-mode state, and current timestamps
- `watchdog_v2/engine.py` keeps long-lived dependencies and filesystem helpers on the engine itself
- mutable runtime-only fields live under `engine.ctx`; there is no legacy attribute bridge

### Run flows

For the operator/contributor walkthrough of this path, see [rescue-lifecycle.md](rescue-lifecycle.md).


- `watchdog_v2/flows/rescue_run.py` contains the single rescue-first `run-once` orchestration path
- deterministic repair always runs in one order: restart -> rollback -> survival -> doctor -> rescue dispatch
- `watchdog_v2/engine.py` now builds a typed `RescueContext`, dispatches the prioritized executor chain, and records learning outcomes
- low-level repair / health / incident primitives stay in their focused modules; only orchestration moved out

### Bootstrap pipeline

- `watchdog_v2/bootstrap.py` keeps the public `Bootstrapper` and final payload shaping
- `watchdog_v2/bootstrap_steps.py` coordinates the ordered detect-only bootstrap steps:
  - detect OpenCode
  - detect Codex / Claude Code / Gemini CLI
  - detect `LiteLLM` specialist-agent readiness
  - detect OpenClaw availability
  - inspect QQ plugin and default channel prerequisites
  - scan Feishu runtime markers
- `watchdog_v2/models.BootstrapSummary` remains the serializable bootstrap payload and executor inventory snapshot

## Validation layers

The repository now uses three complementary validation layers:

1. **Unit / focused output tests** for models, presenters, reporting, events, runtime helpers, rescue dispatch, and learning
2. **Direct orchestration tests** for run context, the unified rescue flow, and bootstrap steps
3. **Rehearsal smoke scenarios** for the `LiteLLM` tier, rule-agent tier, candidate auto-promotion, and pending-review paths in a bounded local harness

## Operational boundaries

The watchdog explicitly protects these operational boundaries:

- canonical CLI names under `scripts/openclaw-watchdog`
- report / metrics fields that rehearsals, live acceptance, or dashboards actually consume
- Prometheus metric names emitted by `metrics --prometheus` when they drive alerting or visibility
- rehearsal scenario intent and expected operator recovery flows

## Non-goals

These changes intentionally do not introduce a framework, service container, or event bus. The code stays standard-library-first and pragmatic: smaller modules, clearer seams, and only the output surfaces that help OpenClaw fallback operations.
