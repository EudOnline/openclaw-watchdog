# OpenClaw Watchdog Refactor Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild OpenClaw Watchdog into a thinner, more testable, and more maintainable operations tool without breaking its public CLI, env surface, reporting contract, or rehearsal workflows.

**Architecture:** Use a gradual strangler-style refactor, not a rewrite. First freeze public contracts and validation gates, then extract typed models and presentation helpers, then split orchestration out of `watchdog_v2/engine.py` and `watchdog_v2/bootstrap.py` into smaller flow modules, and only then tighten packaging and release discipline. The public surface stays stable: `scripts/openclaw-watchdog`, env variable names, report/metrics JSON keys, and current rehearsal scenario semantics remain the compatibility anchors throughout the work.

**Tech Stack:** Python 3.11+, `argparse`, standard-library dataclasses and typing, shell wrappers, GitHub Actions, existing `unittest` suite, existing rehearsal harness under `rehearsal/`.

---

## Refactor constraints

This roadmap assumes the following constraints remain true throughout the work:

- do **not** rename the internal `watchdog_v2` package during this refactor;
- do **not** change canonical CLI names (`openclaw-watchdog`, `detect`, `run-once`, `report`, `metrics`, `incidents`, `bootstrap`) unless there is a separately approved migration plan;
- do **not** break the stable report/metrics contract documented in `docs/reporting-contract.md`;
- do **not** weaken rollback, drift-guard, incident logging, or operator visibility in the name of cleanup;
- prefer additive internal modules and compatibility facades over in-place rewrites.

## Recommended approach

### Option A: Gradual strangler refactor (recommended)

Keep behavior stable, extract one seam at a time, and preserve existing wrappers/tests while moving code into smaller modules. This is the best fit for an ops-heavy codebase where hidden regressions are more dangerous than temporary duplication.

**Why this is recommended:** the current project already has real operator value, decent docs, and strong rehearsal intent. The main issue is concentrated complexity in a few modules, not a failed product direction. A gradual refactor reduces maintenance risk while continuing to ship.

### Option B: Internal package redesign first

Introduce a brand-new package layout (`models/`, `flows/`, `presenters/`, `adapters/`) and migrate everything rapidly. This yields a cleaner end-state faster, but it creates a high risk of orchestration regressions and prolonged red CI during the transition.

### Option C: Minimal cleanup only

Make only tactical improvements around `engine.py`, `bootstrap.py`, and the wrapper. This lowers near-term risk, but it leaves the project vulnerable to continued growth of dict-based state and god-object orchestration.

## Target end-state

At the end of this roadmap, the repository should converge on these responsibilities:

- `watchdog_v2/config.py`: env parsing + config construction only
- `watchdog_v2/runtime.py`: subprocess execution only
- `watchdog_v2/state_store.py`: persistence primitives only
- `watchdog_v2/models.py`: typed dataclasses for probe state, run state, incidents, and bootstrap results
- `watchdog_v2/presenters/`: text/json/prometheus rendering helpers
- `watchdog_v2/flows/`: legacy run flow, survivability flow, bootstrap flow
- `watchdog_v2/engine.py`: thin compatibility facade and dependency container
- `watchdog_v2/cli.py`: parser + dispatch only, not full rendering/orchestration

The resulting architecture is intentionally pragmatic. It does **not** introduce a framework, dependency injection container, or event bus. The aim is to make the existing design legible and testable, not to reinvent it.

## Delivery phases

- **Phase 0:** freeze contracts and verification baseline
- **Phase 1:** unblock runtime ergonomics and local validation
- **Phase 2:** remove dict soup and presentation sprawl
- **Phase 3:** thin the engine and split run flows
- **Phase 4:** split bootstrap into a step pipeline
- **Phase 5:** expand regression coverage and finalize release gates

Success means:

- `watchdog_v2/engine.py` becomes a thin facade instead of the main implementation home;
- `watchdog_v2/bootstrap.py` becomes a composable step pipeline;
- report/metrics/incident/status rendering no longer lives as a giant pile of printer functions in `watchdog_v2/cli.py`;
- runtime/rehearsal verification works reliably on any machine with Python 3.11+;
- tests prove contract stability and cover major orchestration branches directly, not only through indirect smoke flows.

---

### Task 1: Freeze public contracts and establish a refactor safety baseline

**Files:**
- Modify: `docs/reporting-contract.md`
- Modify: `docs/supported-environments.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_reporting.py`
- Modify: `tests/test_cli_smoke.py`
- Verify against: `README.md`
- Verify against: `.github/workflows/ci.yml`

**Phase:** 0

**Step 1: Inventory the public surface before refactoring**

Write down the surfaces that may not break during the refactor:
- CLI commands and help epilog in `watchdog_v2/cli.py`
- wrapper entrypoint `scripts/openclaw-watchdog`
- report/metrics keys in `docs/reporting-contract.md`
- systemd sample layout in `systemd/`
- rehearsal scenario names under `rehearsal/scenarios/`

**Step 2: Tighten explicit contract tests**

Extend `tests/test_reporting.py` and `tests/test_cli_smoke.py` so they assert the current stable command names and the stable report/metrics top-level keys.

Recommended test additions:
- parser still exposes `run-once`, `check`, `detect`, `status`, `report`, `metrics`, `incidents`, `bootstrap`, `maintenance`
- `report_payload()` and `metrics_payload()` still include the stable top-level contract keys

**Step 3: Document compatibility rules more explicitly**

Update `docs/reporting-contract.md`, `docs/supported-environments.md`, and `CHANGELOG.md` to say that internal refactors are expected, but public CLI names, stable JSON keys, and rehearsal scenario intent remain guarded surfaces.

**Step 4: Run baseline verification**

Run:
- `python3.11 -m watchdog_v2 --help`
- `python3.11 -m unittest tests/test_cli_smoke.py -v`
- `python3.11 -m unittest tests/test_reporting.py -v`

Expected:
- help text prints;
- parser smoke tests pass;
- reporting contract tests pass.

**Step 5: Commit**

```bash
git add docs/reporting-contract.md docs/supported-environments.md CHANGELOG.md tests/test_reporting.py tests/test_cli_smoke.py
git commit -m "test: freeze public contracts before refactor"
```

---

### Task 2: Normalize interpreter discovery and rehearsal runtime compatibility

**Files:**
- Modify: `scripts/openclaw-watchdog`
- Modify: `rehearsal/scripts/prepare-system-bin.sh`
- Modify: `rehearsal/scripts/run-scenario.sh`
- Modify: `tests/test_runtime_wrapper.py`
- Modify: `README.md`
- Modify: `rehearsal/README.md`
- Modify: `docs/first-deployment.md`

**Phase:** 1

**Step 1: Reproduce current compatibility friction**

Run on a host where `python3` is older than 3.11 but `python3.12+` exists under another name:
- `./scripts/openclaw-watchdog --help`
- `bash rehearsal/scripts/run-scenario.sh bootstrap-missing-openclaw`

Expected today:
- the wrapper may fail even when a compatible interpreter exists under `python3.12` or `python3.13`;
- local rehearsal may fail for the same reason.

**Step 2: Make interpreter resolution truly match the project promise**

Update `scripts/openclaw-watchdog` so it:
- prefers `python3.11`, `python3.12`, `python3.13` if present;
- otherwise falls back to `python3` only if it is `>=3.11`;
- otherwise exits with the current friendly requirement message.

Update `rehearsal/scripts/prepare-system-bin.sh` so the rehearsal PATH also exposes a compatible `python3.11+` command when available, rather than assuming only `/usr/bin/python3` matters.

**Step 3: Strengthen wrapper regression tests**

Expand `tests/test_runtime_wrapper.py` to cover:
- missing compatible interpreter -> friendly failure message;
- compatible version under a non-`python3` name -> wrapper succeeds;
- rehearsal helper scripts do not regress due to PATH construction.

**Step 4: Update docs to match real behavior**

Update `README.md`, `rehearsal/README.md`, and `docs/first-deployment.md` so they describe the wrapper’s real interpreter search rules and the supported baseline of “any Python 3.11+ interpreter.”

**Step 5: Verify end-to-end**

Run:
- `./scripts/openclaw-watchdog --help`
- `python3.11 -m unittest tests/test_runtime_wrapper.py -v`
- `bash rehearsal/scripts/run-scenario.sh bootstrap-missing-openclaw`

Expected:
- wrapper prints help or a clean requirement message;
- runtime wrapper tests pass;
- bootstrap rehearsal scenario passes on a host with a compatible interpreter.

**Step 6: Commit**

```bash
git add scripts/openclaw-watchdog rehearsal/scripts/prepare-system-bin.sh rehearsal/scripts/run-scenario.sh tests/test_runtime_wrapper.py README.md rehearsal/README.md docs/first-deployment.md
git commit -m "fix: normalize python runtime discovery"
```

---

### Task 3: Introduce typed models for run state, probes, incidents, and bootstrap results

**Files:**
- Create: `watchdog_v2/models.py`
- Modify: `watchdog_v2/health.py`
- Modify: `watchdog_v2/reporting.py`
- Modify: `watchdog_v2/incidents.py`
- Modify: `watchdog_v2/incident_context.py`
- Modify: `watchdog_v2/bootstrap.py`
- Modify: `watchdog_v2/engine.py`
- Create: `tests/test_models.py`

**Phase:** 2

**Step 1: Define the first typed seam**

Create `watchdog_v2/models.py` with dataclasses for the shapes that are currently passed around as ad-hoc dicts.

Minimum recommended models:
- `ProbeSnapshot`
- `RunStateSnapshot`
- `IncidentSummary`
- `BootstrapSummary`

The first version should support:
- `from_dict()` constructors for compatibility with existing code;
- `to_dict()` helpers for persistence and JSON output;
- conservative defaults so existing files can still be read.

**Step 2: Move one module at a time off raw dict indexing**

Start with read-heavy modules first:
- `watchdog_v2/reporting.py`
- `watchdog_v2/incident_context.py`
- `watchdog_v2/incidents.py`

Avoid converting `engine.py` all at once. Let `engine.py` keep building dicts initially, then wrap them with model constructors inside the consumer modules.

**Step 3: Convert bootstrap output to a typed result**

Refactor `watchdog_v2/bootstrap.py` so `BootstrapOutcome.payload` is still serializable, but the internal assembly logic uses a typed `BootstrapSummary` or step result objects instead of one giant mutable dict.

**Step 4: Add focused model regression tests**

Create `tests/test_models.py` for:
- default construction from incomplete dicts;
- serialization round-trips;
- backward-compatible handling of missing keys.

**Step 5: Verify compatibility**

Run:
- `python3.11 -m unittest tests/test_models.py -v`
- `python3.11 -m unittest tests/test_reporting.py -v`
- `python3.11 -m unittest tests/test_incident_context.py -v`

Expected:
- all model tests pass;
- reporting and incident-context tests still pass without changing public output shape.

**Step 6: Commit**

```bash
git add watchdog_v2/models.py watchdog_v2/health.py watchdog_v2/reporting.py watchdog_v2/incidents.py watchdog_v2/incident_context.py watchdog_v2/bootstrap.py watchdog_v2/engine.py tests/test_models.py
git commit -m "refactor: introduce typed watchdog models"
```

---

### Task 4: Split CLI responsibilities into parser, dispatch, and presenters

**Files:**
- Create: `watchdog_v2/presenters/__init__.py`
- Create: `watchdog_v2/presenters/status.py`
- Create: `watchdog_v2/presenters/report.py`
- Create: `watchdog_v2/presenters/incidents.py`
- Create: `watchdog_v2/presenters/bootstrap.py`
- Modify: `watchdog_v2/cli.py`
- Modify: `tests/test_cli_smoke.py`
- Create: `tests/test_cli_presenters.py`

**Phase:** 2

**Step 1: Freeze existing output behavior before moving code**

Capture the existing responsibilities in `watchdog_v2/cli.py`:
- parser construction;
- command dispatch;
- human-readable output rendering;
- JSON output handling.

Keep parser construction in `watchdog_v2/cli.py`, but move formatter/renderer functions out first.

**Step 2: Extract presenter functions without changing command behavior**

Move these categories into dedicated modules:
- status output helpers -> `watchdog_v2/presenters/status.py`
- report and metrics output helpers -> `watchdog_v2/presenters/report.py`
- incident list/detail/queue/timeline helpers -> `watchdog_v2/presenters/incidents.py`
- bootstrap output helpers -> `watchdog_v2/presenters/bootstrap.py`

`watchdog_v2/cli.py` should become a small command router that delegates rendering.

**Step 3: Add presenter-specific tests**

Create `tests/test_cli_presenters.py` to lock down:
- operator summary formatting;
- incident queue/detail text;
- bootstrap summary rendering;
- metrics/report human-readable output.

**Step 4: Keep JSON handling separate from human-readable formatting**

Ensure JSON output paths stay direct and do not route through string presenters, so machine-readable output stays simple and stable.

**Step 5: Verify CLI behavior**

Run:
- `python3.11 -m unittest tests/test_cli_smoke.py -v`
- `python3.11 -m unittest tests/test_cli_presenters.py -v`
- `python3.11 -m watchdog_v2 --help`

Expected:
- CLI parser behavior is unchanged;
- presenter tests pass;
- help output remains unchanged except for intentional formatting fixes.

**Step 6: Commit**

```bash
git add watchdog_v2/presenters watchdog_v2/cli.py tests/test_cli_smoke.py tests/test_cli_presenters.py
git commit -m "refactor: split cli presentation from dispatch"
```

---

### Task 5: Extract engine state into a dedicated run context and make `engine.py` a facade

**Files:**
- Create: `watchdog_v2/run_context.py`
- Modify: `watchdog_v2/engine.py`
- Modify: `watchdog_v2/reporting.py`
- Modify: `watchdog_v2/events.py`
- Modify: `watchdog_v2/handoff.py`
- Modify: `watchdog_v2/survival.py`
- Create: `tests/test_run_context.py`

**Phase:** 3

**Step 1: Identify mutable runtime-only fields inside `WatchdogEngine`**

Move the execution-scoped mutable fields out of `WatchdogEngine.__init__` into a separate `RunContext` dataclass.

Recommended fields to move first:
- recovery tracking fields
- rollback metadata
- survival-mode runtime flags
- current incident/handoff fields
- timestamps for the current run

Keep long-lived dependencies inside `WatchdogEngine`:
- `config`
- subprocess helpers
- file path helpers
- lock management

**Step 2: Replace direct engine field mutation with context mutation**

Change modules such as `reporting.py`, `handoff.py`, and `survival.py` to read/write `engine.ctx.<field>` instead of growing more `engine.<field>` attributes.

**Step 3: Preserve the current public method surface during migration**

Do **not** remove `WatchdogEngine` methods yet. Keep them as compatibility facades while the implementation is relocated behind `engine.ctx` and smaller helpers.

**Step 4: Add focused tests for run-context defaults and transitions**

Create `tests/test_run_context.py` covering:
- fresh context defaults;
- recovery tracking updates;
- survival mode state updates;
- rollback metadata assignment.

**Step 5: Verify the migration**

Run:
- `python3.11 -m unittest tests/test_run_context.py -v`
- `python3.11 -m unittest tests/test_reporting.py -v`
- `python3.11 -m unittest tests/test_events.py -v`

Expected:
- run context tests pass;
- reporting and event output stay compatible.

**Step 6: Commit**

```bash
git add watchdog_v2/run_context.py watchdog_v2/engine.py watchdog_v2/reporting.py watchdog_v2/events.py watchdog_v2/handoff.py watchdog_v2/survival.py tests/test_run_context.py
git commit -m "refactor: extract engine run context"
```

---

### Task 6: Split `run-once` logic into explicit legacy and survivability flows

**Files:**
- Create: `watchdog_v2/flows/__init__.py`
- Create: `watchdog_v2/flows/legacy_run.py`
- Create: `watchdog_v2/flows/survivability_run.py`
- Modify: `watchdog_v2/engine.py`
- Modify: `watchdog_v2/repair.py`
- Modify: `watchdog_v2/health.py`
- Modify: `watchdog_v2/survival.py`
- Create: `tests/test_legacy_flow.py`
- Create: `tests/test_survivability_flow.py`

**Phase:** 3

**Step 1: Move orchestration, not primitives**

Extract the control flow from:
- `WatchdogEngine._run_once_legacy()`
- `WatchdogEngine._run_once_survivability()`

Leave low-level helpers in place initially:
- health probes
- restart/doctor/rollback primitives
- state-store reads/writes

The first extracted modules should accept `engine` and `ctx` and return `RunOutcome`, without changing behavior.

**Step 2: Make the decision tree explicit**

Inside each flow module, separate:
- observe / probe
- decide
- act
- persist
- notify / incident escalation

This refactor is successful when an engineer can read the file top-to-bottom and understand the flow without jumping across 15 helper methods.

**Step 3: Add direct flow tests**

Create:
- `tests/test_legacy_flow.py`
- `tests/test_survivability_flow.py`

Use fake or rehearsal-style engine doubles to cover:
- already healthy path;
- restart recovers path;
- rollback before doctor path;
- escalated failure path with incident creation.

**Step 4: Reduce `engine.py` to a thin delegator**

After extraction, `WatchdogEngine.run_once()` should mainly choose the flow and delegate. `engine.py` should no longer contain the full orchestration bodies.

**Step 5: Verify direct and indirect behavior**

Run:
- `python3.11 -m unittest tests/test_legacy_flow.py -v`
- `python3.11 -m unittest tests/test_survivability_flow.py -v`
- `bash rehearsal/scripts/run-scenario.sh watchdog-conversation-probe-ready`
- `bash rehearsal/scripts/run-scenario.sh watchdog-failed-fallback`
- `bash rehearsal/scripts/run-scenario.sh watchdog-incident-queue`

Expected:
- direct flow tests pass;
- key rehearsal scenarios still pass unchanged.

**Step 6: Commit**

```bash
git add watchdog_v2/flows watchdog_v2/engine.py watchdog_v2/repair.py watchdog_v2/health.py watchdog_v2/survival.py tests/test_legacy_flow.py tests/test_survivability_flow.py
git commit -m "refactor: split watchdog run flows"
```

---

### Task 7: Break bootstrap into explicit step objects instead of one giant mutable workflow

**Files:**
- Create: `watchdog_v2/bootstrap_steps.py`
- Modify: `watchdog_v2/bootstrap.py`
- Modify: `watchdog_v2/config.py`
- Create: `tests/test_bootstrap_steps.py`
- Modify: `rehearsal/scripts/run-scenario.sh`
- Verify against: `rehearsal/scenarios/bootstrap-missing-openclaw.expected.txt`
- Verify against: `rehearsal/scenarios/bootstrap-install-openclaw.expected.txt`

**Phase:** 4

**Step 1: Model bootstrap as ordered steps**

Extract these responsibilities into named step helpers or step classes:
- ensure OpenCode
- enforce OpenCode model config
- detect Codex
- detect/install OpenClaw
- ensure QQ plugin
- scaffold default channel config
- scan Feishu runtime markers

The step API can stay simple:
- input: config + current bootstrap summary
- output: updated bootstrap summary + warnings/next steps

**Step 2: Preserve exact user-facing semantics first**

Do not change bootstrap state names or exit codes during this refactor. The goal is structure, not behavior expansion.

**Step 3: Add direct bootstrap-step tests**

Create `tests/test_bootstrap_steps.py` covering:
- OpenClaw missing without install confirmation -> exit code `10`
- OpenCode config changes recorded correctly
- plugin install failure surfaced correctly
- placeholder credentials and next-step warnings preserved

**Step 4: Keep rehearsal bootstrap scenarios green**

Use the existing rehearsal scenarios as acceptance gates for the refactor. If textual output changes intentionally, update the golden files in the same task and record the reason in `CHANGELOG.md`.

**Step 5: Verify behavior**

Run:
- `python3.11 -m unittest tests/test_bootstrap_steps.py -v`
- `bash rehearsal/scripts/run-scenario.sh bootstrap-missing-openclaw`
- `bash rehearsal/scripts/run-scenario.sh bootstrap-install-openclaw`

Expected:
- direct bootstrap-step tests pass;
- rehearsal bootstrap scenarios pass with unchanged semantics.

**Step 6: Commit**

```bash
git add watchdog_v2/bootstrap_steps.py watchdog_v2/bootstrap.py watchdog_v2/config.py tests/test_bootstrap_steps.py rehearsal/scripts/run-scenario.sh rehearsal/scenarios/bootstrap-missing-openclaw.expected.txt rehearsal/scenarios/bootstrap-install-openclaw.expected.txt CHANGELOG.md

git commit -m "refactor: split bootstrap into ordered steps"
```

---

### Task 8: Expand regression coverage around high-risk orchestration and golden outputs

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_runtime_wrapper.py`
- Modify: `tests/test_reporting.py`
- Modify: `tests/test_events.py`
- Modify: `tests/test_incident_context.py`
- Create: `tests/test_cli_json_contract.py`
- Create: `tests/test_rehearsal_smoke_matrix.py`
- Modify: `docs/live-acceptance-checklist.md`

**Phase:** 5

**Step 1: Fill the current coverage gap intentionally**

The post-refactor suite should cover three layers:
- unit tests for helpers/models/presenters;
- direct flow tests for legacy/survivability/bootstrap;
- bounded rehearsal smoke scenarios for end-to-end behavior.

**Step 2: Add machine-readable contract tests**

Create `tests/test_cli_json_contract.py` to run command paths and assert:
- `report --json` contains stable keys
- `metrics --json` contains stable keys
- `metrics --prometheus` contains stable metric names

**Step 3: Make CI reflect the supported promise**

Update `.github/workflows/ci.yml` so it continues to run the fast 3.11 baseline, and consider adding one additional 3.12 or 3.13 job once the wrapper compatibility work is complete.

Minimum expected CI after refactor:
- CLI help smoke
- full unittest suite
- byte-compile check
- bounded rehearsal scenario set

**Step 4: Update live acceptance docs**

Update `docs/live-acceptance-checklist.md` so it mirrors the new validation story: direct tests for internals, rehearsal scenarios for operator flows, and contract checks for machine-readable outputs.

**Step 5: Verify the release gate**

Run:
- `python3.11 -m unittest discover -s tests -v`
- `python3.11 -m py_compile watchdog_v2/*.py rehearsal/lib/*.py rehearsal/tools/*.py tests/*.py`
- `bash rehearsal/scripts/run-scenario.sh bootstrap-missing-openclaw`
- `bash rehearsal/scripts/run-scenario.sh watchdog-conversation-probe-ready`
- `bash rehearsal/scripts/run-scenario.sh watchdog-failed-fallback`
- `bash rehearsal/scripts/run-scenario.sh watchdog-incident-queue`

Expected:
- full unit suite passes;
- byte-compile passes;
- key rehearsal scenarios pass.

**Step 6: Commit**

```bash
git add .github/workflows/ci.yml tests/test_runtime_wrapper.py tests/test_reporting.py tests/test_events.py tests/test_incident_context.py tests/test_cli_json_contract.py tests/test_rehearsal_smoke_matrix.py docs/live-acceptance-checklist.md
git commit -m "test: expand watchdog orchestration regression coverage"
```

---

### Task 9: Finish the refactor by reducing compatibility shims and documenting the new internal architecture

**Files:**
- Create: `docs/internal-architecture.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/roadmap.md`
- Modify: `CHANGELOG.md`
- Verify against: `docs/compatibility-and-deprecations.md`

**Phase:** 5

**Step 1: Document the internal structure that now exists**

Create `docs/internal-architecture.md` describing:
- config/runtime/state primitives
- models
- presenters
- run flows
- engine facade
- bootstrap step pipeline
- how rehearsal and unit tests map onto those layers

**Step 2: Update high-level docs to stop pointing at outdated hotspots**

Refresh `README.md`, `docs/README.md`, and `docs/roadmap.md` so they describe the current architecture and the remaining non-goals honestly.

**Step 3: Re-evaluate deprecated shims**

Review whether deprecated `-v2` wrappers should remain as-is, gain stronger deprecation wording, or get a removal target in the roadmap. Do not remove them in the same task unless migration impact is trivial and documented.

**Step 4: Verify docs against the repo literally**

Manually follow the main paths in the docs and confirm every referenced file/command exists.

**Step 5: Commit**

```bash
git add docs/internal-architecture.md README.md docs/README.md docs/roadmap.md CHANGELOG.md docs/compatibility-and-deprecations.md
git commit -m "docs: publish post-refactor architecture"
```

---

## Sequencing rules

Apply these rules while executing the roadmap:

1. never refactor `engine.py` and `bootstrap.py` in the same PR;
2. land public contract tests before landing structural refactors;
3. extract presenters before rewriting CLI dispatch semantics;
4. extract flow modules before deleting old engine helper methods;
5. keep rehearsal scenarios green at every orchestration milestone.

## Suggested PR breakdown

Use these PR boundaries unless a smaller split is more natural:

1. Contract freeze + runtime compatibility
2. Typed models + presenter extraction
3. Run context + legacy/survivability flow split
4. Bootstrap step pipeline
5. Validation expansion + internal architecture docs

## Risks to watch

- **Hidden dict-shape regressions:** mitigate with typed model adapters and contract tests.
- **Output drift in human-readable summaries:** mitigate with presenter tests and only intentional golden updates.
- **Behavior drift during flow extraction:** mitigate with direct flow tests plus rehearsal acceptance gates.
- **Docs lagging behind code movement:** mitigate by pairing each structural milestone with small doc updates.
- **Refactor fatigue:** mitigate by shipping one maintainability win per PR instead of a giant multi-week branch.

## Definition of done

This roadmap is complete when all of the following are true:

- `watchdog_v2/engine.py` is primarily a facade/delegator;
- `watchdog_v2/bootstrap.py` is primarily a step coordinator;
- `watchdog_v2/cli.py` is primarily parser + dispatch;
- stable report/metrics CLI contracts are enforced in tests;
- local rehearsal no longer depends on a lucky `python3` symlink arrangement;
- docs describe the actual package structure and validation story accurately.
