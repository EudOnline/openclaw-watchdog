# Engine Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Cut `openclaw_watchdog/engine.py` from a multi-responsibility god object into a thinner OpenClaw watchdog facade that mainly wires dependencies and delegates incident, rescue, learning, and run-state responsibilities to focused modules.

**Architecture:** Keep `WatchdogEngine` as the public composition root and operator-facing facade, but move heavy logic out in four slices: incident persistence/workflow, rescue context construction, rescue learning recording, and probe/run-state projection. Stay stdlib-first, keep the current CLI and flow contracts, and do not add framework-style dependency injection.

**Tech Stack:** Python 3.11+, stdlib dataclasses/typing/pathlib/json, existing `openclaw_watchdog` modules, existing `unittest` suite, existing rehearsal harness.

---

## Recommended approach

### Option A: Seam-first extraction (recommended)

Extract the largest cohesive clusters out of `openclaw_watchdog/engine.py` behind plain functions or tiny service objects, leaving public engine methods in place as delegating wrappers during the transition.

**Why this is recommended:** it changes internals aggressively without changing the CLI, rescue flow, or current test harness shape. It is the safest way to reduce `engine.py` now while preserving the OpenClaw-specific operational behavior you already validated.

### Option B: Full engine breakup in one pass

Move almost every cluster out of `engine.py` immediately and rewrite call sites to use the new modules directly.

**Why this is not recommended first:** it produces the cleanest end state, but it increases review size and raises the chance of subtle regression in incident/reporting/rescue edge cases.

### Option C: Freeze features and only trim lines

Do the smallest possible edits to reduce line count without rethinking boundaries.

**Why this is not enough:** it may make `engine.py` shorter, but it will not meaningfully improve ownership, readability, or change safety.

---

## Success criteria

The refactor is complete when all of these are true:

- `openclaw_watchdog/engine.py` is reduced from ~1448 lines to roughly `<= 900` lines.
- `WatchdogEngine` no longer owns the detailed implementation of incident persistence/workflow.
- `WatchdogEngine` no longer owns the detailed implementation of rescue context construction and rescue learning case recording.
- `WatchdogEngine` no longer computes probe-to-run-state projection inline.
- Public CLI/reporting/rescue behavior remains unchanged.
- `python3.13 -m unittest discover -s tests -q` passes.
- `bash rehearsal/scripts/run-scenario.sh critical` passes.

---

## Module target state

By the end of this plan, the code should look like this:

- `openclaw_watchdog/engine.py`
  - keeps construction, lock lifecycle, thin wrappers, and public facade methods
  - keeps only tiny delegating methods for CLI-facing access
- `openclaw_watchdog/incident_service.py`
  - owns incident state reads/writes, index refresh, owner/ack/note workflow, snapshot payload assembly
- `openclaw_watchdog/rescue_context_builder.py`
  - owns normalized failure-signature calculation, recent-case lookup, executor inventory shaping, and `RescueContext` construction
- `openclaw_watchdog/rescue_learning_service.py`
  - owns successful recovery case payload generation, candidate rule shaping, promotion result mapping
- `openclaw_watchdog/probe_run_state.py`
  - owns service-probe failure counting, health-level derivation, and run-state write payload generation

Optional only if needed during implementation:

- `openclaw_watchdog/engine_runtime.py`
  - small helper for `now_iso`, current-mode shaping, and shared engine runtime fields if those pieces are still duplicated after the four primary extractions

---

### Task 1: Add characterization coverage around current engine seams

**Files:**
- Modify: `tests/test_rescue_flow.py`
- Modify: `tests/test_reporting.py`
- Modify: `tests/test_run_context.py`
- Modify: `tests/test_cli_json_contract.py`
- Inspect: `openclaw_watchdog/engine.py`

**Step 1: Identify current engine-owned behavior that must not drift**

Freeze the current observable behavior around these seams:
- rescue context fields
- rescue learning result fields
- incident queue/detail payload shape
- probe/run-state projection fields

**Step 2: Write the failing or missing tests first**

Add focused tests that assert:
- rescue context includes normalized signature and recent cases
- recovery learning persists the expected candidate-rule metadata
- status/report/metrics still expose the same operator snapshot keys
- run-state projection still computes health level and conversation fields identically

**Step 3: Run the focused test subset**

Run: `python3.13 -m unittest tests.test_rescue_flow tests.test_reporting tests.test_run_context tests.test_cli_json_contract -v`
Expected: either fail on the new assertions or pass and lock in the current contract.

**Step 4: Commit**

```bash
git add tests/test_rescue_flow.py tests/test_reporting.py tests/test_run_context.py tests/test_cli_json_contract.py
git commit -m "test: lock engine seam behavior before refactor"
```

---

### Task 2: Extract incident persistence and workflow out of engine.py

**Files:**
- Create: `openclaw_watchdog/incident_service.py`
- Modify: `openclaw_watchdog/engine.py`
- Verify against: `openclaw_watchdog/incidents.py`
- Verify against: `openclaw_watchdog/incident_context.py`
- Test: `tests/test_reporting.py`
- Test: `tests/test_cli_json_contract.py`

**Primary engine area to remove:**
- incident payload helpers and workflow methods currently clustered around `incident_state_file` through `add_incident_note`

**Step 1: Move read/write primitives into the new module**

Put the detailed filesystem/payload logic into plain functions or a tiny `IncidentService` object that accepts `engine` and uses current paths/config.

Recommended public entrypoints:
- `incident_snapshot(engine, incident_dir)`
- `list_incident_snapshots(engine, ...)`
- `incident_detail_payload(engine, incident_id)`
- `incident_timeline_payload(engine, incident_id, ...)`
- `incident_queue_payload(engine, ...)`
- `set_incident_owner(engine, incident_id, owner)`
- `clear_incident_owner(engine, incident_id)`
- `acknowledge_incident(engine, incident_id, acknowledged_by, note='')`
- `clear_incident_acknowledgement(engine, incident_id)`
- `add_incident_note(engine, incident_id, note_by, message)`

**Step 2: Turn engine methods into thin delegates**

Keep the current `WatchdogEngine` method names for compatibility inside the repo, but make them one-line or tiny delegating wrappers into `incident_service`.

**Step 3: Remove duplicated JSON/index logic from engine**

If `engine.py` still contains incident index assembly or operator workflow file mutation after extraction, move it too. The target is for `engine.py` to orchestrate, not own incident storage rules.

**Step 4: Run focused tests**

Run: `python3.13 -m unittest tests.test_reporting tests.test_cli_json_contract -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/incident_service.py openclaw_watchdog/engine.py tests/test_reporting.py tests/test_cli_json_contract.py
git commit -m "refactor: extract incident workflow from engine"
```

---

### Task 3: Extract rescue context construction from engine.py

**Files:**
- Create: `openclaw_watchdog/rescue_context_builder.py`
- Modify: `openclaw_watchdog/engine.py`
- Verify against: `openclaw_watchdog/rescue_policy.py`
- Verify against: `openclaw_watchdog/learning.py`
- Verify against: `openclaw_watchdog/learning_signatures.py`
- Test: `tests/test_rescue_flow.py`
- Test: `tests/test_rule_agent.py`

**Primary engine area to remove:**
- `_rescue_failure_signature`
- `_rescue_available_executors`
- `_rescue_command`
- `build_rescue_context`
- `_build_litellm_client` if it is only rescue-context wiring

**Step 1: Introduce a focused builder API**

Recommended entrypoints:
- `build_failure_metadata(engine, probe)`
- `available_rescue_executors(engine)`
- `build_rescue_context(engine, probe)`

The builder should own:
- normalized signature creation
- recent similar-case lookup
- executor inventory/order shaping
- policy snapshot shaping
- editable-path metadata shaping

**Step 2: Keep engine as composition root only**

`WatchdogEngine.build_rescue_context()` should delegate to the new module. If command resolution or LiteLLM client creation is needed, pass them through explicit helper calls rather than embedding lookup logic in the builder.

**Step 3: Keep rule-agent contract stable**

Do not change the structure of `RescueContext.metadata` unless the tests explicitly move with it. The purpose here is ownership cleanup, not behavior expansion.

**Step 4: Run focused tests**

Run: `python3.13 -m unittest tests.test_rescue_flow tests.test_rule_agent -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/rescue_context_builder.py openclaw_watchdog/engine.py tests/test_rescue_flow.py tests/test_rule_agent.py
git commit -m "refactor: extract rescue context builder from engine"
```

---

### Task 4: Extract rescue learning recording from engine.py

**Files:**
- Create: `openclaw_watchdog/rescue_learning_service.py`
- Modify: `openclaw_watchdog/engine.py`
- Verify against: `openclaw_watchdog/learning.py`
- Verify against: `openclaw_watchdog/rescue_models.py`
- Test: `tests/test_learning.py`
- Test: `tests/test_rescue_flow.py`

**Primary engine area to remove:**
- `record_learning_from_recovery`
- `record_learning_from_rescue`
- candidate-rule shaping embedded in rescue success recording

**Step 1: Move case-payload shaping into the new service**

The new service should own:
- case id generation
- normalized failure signature fallback
- candidate rule payload creation from plan actions/validations
- case persistence and promotion mapping
- translation of promotion result into `candidate_rule_status`

**Step 2: Keep engine interface stable**

Keep `WatchdogEngine.record_learning_from_recovery()` and `.record_learning_from_rescue()` as delegators during the refactor so the flow layer does not churn.

**Step 3: Be strict about inputs**

Prefer passing explicit inputs like `strategy`, `recovery_kind`, `probe`, `context`, `dispatch_result`, and `plan_result` to the service, rather than letting it read arbitrary engine state.

**Step 4: Run focused tests**

Run: `python3.13 -m unittest tests.test_learning tests.test_rescue_flow -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/rescue_learning_service.py openclaw_watchdog/engine.py tests/test_learning.py tests/test_rescue_flow.py
git commit -m "refactor: extract rescue learning recording from engine"
```

---

### Task 5: Extract probe-to-run-state projection out of engine.py

**Files:**
- Create: `openclaw_watchdog/probe_run_state.py`
- Modify: `openclaw_watchdog/engine.py`
- Verify against: `openclaw_watchdog/survival.py`
- Verify against: `openclaw_watchdog/state_store.py`
- Test: `tests/test_run_context.py`
- Test: `tests/test_reporting.py`

**Primary engine area to remove:**
- `_service_probe_failures_for`
- `_write_probe_run_state`
- any inline health-level derivation that exists only to prepare run-state writes

**Step 1: Create a narrow projection API**

Recommended entrypoints:
- `service_probe_failures_for(config, probe, previous_failures)`
- `derive_health_level(probe, *, config_invalid)`
- `write_probe_run_state(engine, probe, *, config_invalid, service_probe_failures)`

**Step 2: Make the helper own the payload map**

The helper should own the concrete run-state payload assembly, including:
- health level
- current mode
- last service probe fields
- conversation readiness fields
- survival-mode fields

**Step 3: Keep engine code narrative short**

After extraction, the `run_once` path and related flow calls should read like orchestration statements, not payload construction blocks.

**Step 4: Run focused tests**

Run: `python3.13 -m unittest tests.test_run_context tests.test_reporting -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/probe_run_state.py openclaw_watchdog/engine.py tests/test_run_context.py tests/test_reporting.py
git commit -m "refactor: extract probe run-state projection from engine"
```

---

### Task 6: Collapse engine.py into facade-only groups and remove dead helpers

**Files:**
- Modify: `openclaw_watchdog/engine.py`
- Modify: `docs/internal-architecture.md`
- Modify: `docs/rescue-lifecycle.md`
- Verify against: `README.md`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_reporting.py`
- Test: `tests/test_rescue_flow.py`

**Step 1: Reorder engine by role**

Reorganize `engine.py` into a small number of sections:
- lifecycle / lock / logging
- command/runtime wrappers
- thin facade delegates for incidents
- thin facade delegates for rescue
- thin facade delegates for reporting/maintenance
- `run_once` handoff

**Step 2: Delete no-longer-needed private helpers**

After the extractions, remove private methods that are now just historical leftovers. Avoid keeping duplicate paths “just in case.”

**Step 3: Update architecture docs**

Document that `WatchdogEngine` is now primarily the composition root, while `incident_service`, `rescue_context_builder`, `rescue_learning_service`, and `probe_run_state` own the heavy logic.

**Step 4: Run broader verification**

Run: `python3.13 -m unittest discover -s tests -q`
Expected: `OK`

**Step 5: Run rehearsal gate**

Run: `bash rehearsal/scripts/run-scenario.sh critical`
Expected: all critical scenarios pass.

**Step 6: Commit**

```bash
git add openclaw_watchdog/engine.py docs/internal-architecture.md docs/rescue-lifecycle.md
git commit -m "refactor: slim engine into composition facade"
```

---

### Task 7: Optional cleanup if engine.py is still too large

**Files:**
- Modify: `openclaw_watchdog/engine.py`
- Create if needed: `openclaw_watchdog/engine_runtime.py`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_reporting.py`

**Only do this task if:** `openclaw_watchdog/engine.py` is still above ~900 lines or still mixes unrelated concerns after Tasks 1-6.

**Step 1: Move tiny shared runtime helpers**

Candidates include:
- `now_iso`
- `current_mode`
- timestamp conversion helpers
- small payload formatting helpers still reused in several modules

**Step 2: Keep it boring**

Do not invent abstractions or base classes. Only move helpers if they make `engine.py` materially easier to scan.

**Step 3: Re-run targeted tests**

Run: `python3.13 -m unittest tests.test_cli_smoke tests.test_reporting -v`
Expected: PASS.

**Step 4: Commit**

```bash
git add openclaw_watchdog/engine.py openclaw_watchdog/engine_runtime.py
git commit -m "refactor: move residual engine runtime helpers"
```

---

## Recommended commit order

1. `test: lock engine seam behavior before refactor`
2. `refactor: extract incident workflow from engine`
3. `refactor: extract rescue context builder from engine`
4. `refactor: extract rescue learning recording from engine`
5. `refactor: extract probe run-state projection from engine`
6. `refactor: slim engine into composition facade`
7. `refactor: move residual engine runtime helpers` (only if needed)

---

## Explicit non-goals

Do **not** do these in the same series:

- add backward-compatibility layers for old watchdog versions
- add automatic installation of missing rescue CLIs
- replace the current CLI surface
- migrate to a framework or DI container
- rewrite the rehearsal harness
- change the rescue chain order away from `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`

---

## Final acceptance checklist

Before declaring the refactor complete, confirm all of the following:

- `openclaw_watchdog/engine.py` is materially smaller and easier to scan.
- incident logic is no longer implemented inline in `WatchdogEngine`.
- rescue context construction is no longer implemented inline in `WatchdogEngine`.
- rescue learning recording is no longer implemented inline in `WatchdogEngine`.
- probe/run-state projection is no longer implemented inline in `WatchdogEngine`.
- docs mention the new ownership boundaries.
- full unit suite passes.
- critical rehearsal passes.
