# Recovery Phases P0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split `openclaw_watchdog/flows/recovery_phases.py` into smaller owner modules without changing rescue behavior, so the next round of recovery work lands on clear seams instead of re-inflating one orchestration hotspot.

**Architecture:** Keep `openclaw_watchdog/flows/rescue_run.py` as the single public run-flow entry and keep `openclaw_watchdog/flows/recovery_phases.py` as a temporary thin facade during the cutover. Move probe/state shaping, deterministic recovery, rescue dispatch/learning, and finalization into separate owner modules under `openclaw_watchdog/flows/`, then make `recovery_phases.py` mostly imports plus public wrappers.

**Tech Stack:** Python 3.11+, stdlib `unittest`, current rehearsal harness, existing runtime owner modules (`health`, `repair_action_runtime`, `rollback_runtime`, `rescue_runtime`, `rescue_learning_service`, `state_transition`).

---

## Recommended cut strategy

### Option A: Split by phase owner modules (recommended)

Create four focused flow-owner modules:

- `openclaw_watchdog/flows/recovery_probe_runtime.py`
- `openclaw_watchdog/flows/recovery_finalize_runtime.py`
- `openclaw_watchdog/flows/deterministic_recovery_runtime.py`
- `openclaw_watchdog/flows/rescue_phase_runtime.py`

Keep `recovery_phases.py` as a thin facade during the cut so tests and imports move gradually.

**Why this is recommended:** it matches the project’s recent strangler pattern, keeps `rescue_run.py` stable, and reduces risk because each extraction can be verified independently.

### Option B: Keep one file and only reorder functions

Move code blocks around inside `recovery_phases.py` and add comments/regions.

**Tradeoff:** low short-term churn, but the file remains the hotspot and future work keeps piling into it.

### Option C: Replace phase helpers with one class orchestrator

Introduce a `RecoveryCoordinator` object and migrate all phase state into methods.

**Tradeoff:** potentially tidy on paper, but it adds a new abstraction layer right when the current owner-first module split is already working.

**Recommendation:** choose **Option A**.

---

## Scope guardrails

- Do **not** change the rescue order: `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`.
- Do **not** reintroduce `engine.py` wrappers to support the new modules.
- Do **not** widen the OpenClaw mutation policy while doing this split.
- Do **not** rewrite `rescue_run.py`; keep it as the public coordinator with the same entrypoint shape.
- Do **not** change rehearsal semantics; critical scenarios must still pass sequentially.

---

## Task 1: Pin the current phase contracts with narrow tests

**Files:**
- Create: `tests/test_recovery_probe_runtime.py`
- Create: `tests/test_recovery_finalize_runtime.py`
- Modify: `tests/test_rescue_flow.py`

**Step 1: Write the failing probe/runtime tests**

Cover:

- probe -> health-level classification
- summary selection precedence
- baseline probe writes run-state and syncs survival mode
- initial healthy/degraded finalization behavior

**Step 2: Run the new focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_recovery_probe_runtime tests.test_recovery_finalize_runtime -v
```

Expected: import failures or missing symbol failures for the new owner modules.

**Step 3: Add one focused `tests/test_rescue_flow.py` seam test**

Pin that `rescue_run.run()` still calls:

- baseline probe/sync
- deterministic recovery
- rescue phase

in the same sequence as today.

**Step 4: Re-run the same tests**

Expected: the new module tests still fail for missing owners, while the seam test proves the intended cut boundary.

---

## Task 2: Extract probe/state and finalization owners

**Files:**
- Create: `openclaw_watchdog/flows/recovery_probe_runtime.py`
- Create: `openclaw_watchdog/flows/recovery_finalize_runtime.py`
- Modify: `openclaw_watchdog/flows/recovery_phases.py`
- Test: `tests/test_recovery_probe_runtime.py`
- Test: `tests/test_recovery_finalize_runtime.py`
- Test: `tests/test_rescue_flow.py`

**Step 1: Implement `recovery_probe_runtime.py`**

Move these responsibilities out of `recovery_phases.py`:

- `RecoveryPhaseState`
- probe summary helpers
- service-probe failure carry-forward
- run-state write for probe results
- `baseline_probe_and_sync()`
- `finish_initial_state()` support helpers

**Step 2: Implement `recovery_finalize_runtime.py`**

Move:

- last-good refresh-on-ready
- success/failure finalization
- shared recovery finalization gate

**Step 3: Keep `recovery_phases.py` as a facade**

Have `recovery_phases.py` import and re-export the public functions instead of keeping the implementations inline.

**Step 4: Run the focused suites**

Run:

```bash
python3.13 -m unittest tests.test_recovery_probe_runtime tests.test_recovery_finalize_runtime tests.test_rescue_flow -q
```

Expected: PASS.

---

## Task 3: Extract deterministic recovery into its own owner

**Files:**
- Create: `openclaw_watchdog/flows/deterministic_recovery_runtime.py`
- Create: `tests/test_deterministic_recovery_runtime.py`
- Modify: `openclaw_watchdog/flows/recovery_phases.py`
- Modify: `tests/test_rescue_flow.py`

**Step 1: Write the failing deterministic-phase tests**

Cover:

- restart attempt and re-probe
- rollback attempt and optional restart-after-restore
- survival-mode branch
- doctor enabled vs skipped
- early exit when deterministic recovery restores usability

**Step 2: Run the new deterministic suite**

Run:

```bash
python3.13 -m unittest tests.test_deterministic_recovery_runtime -v
```

Expected: FAIL because the new owner module does not exist yet.

**Step 3: Implement `deterministic_recovery_runtime.py`**

Move `run_deterministic_recovery()` and only the helpers it truly owns.

Keep probe classification/finalization calls delegated to the probe/finalize owners added in Task 2.

**Step 4: Rewire `recovery_phases.py`**

Make `recovery_phases.run_deterministic_recovery()` a thin forwarder.

**Step 5: Run deterministic + flow tests**

Run:

```bash
python3.13 -m unittest tests.test_deterministic_recovery_runtime tests.test_rescue_flow -q
```

Expected: PASS.

---

## Task 4: Extract rescue dispatch, learning, and phase result marking

**Files:**
- Create: `openclaw_watchdog/flows/rescue_phase_runtime.py`
- Create: `tests/test_rescue_phase_runtime.py`
- Modify: `openclaw_watchdog/flows/recovery_phases.py`
- Modify: `tests/test_rescue_flow.py`
- Modify: `tests/test_learning.py`

**Step 1: Write the failing rescue-phase tests**

Cover:

- rescue context build + dispatch
- ctx dispatch/result markers
- rolled-back rescue plan records failure learning
- successful rescue records positive learning
- exhausted rescue records failure learning and final failure outcome

**Step 2: Run the new rescue-phase suite**

Run:

```bash
python3.13 -m unittest tests.test_rescue_phase_runtime -v
```

Expected: FAIL because the owner module is missing.

**Step 3: Implement `rescue_phase_runtime.py`**

Move:

- rescue context construction handoff
- dispatch/plan execution handoff
- dispatch-state markers
- learning-result markers
- `run_rescue_phase()`

**Step 4: Keep learning semantics unchanged**

Do **not** change:

- positive vs negative evidence timing
- auto-promotion thresholds
- rescue rollback failure semantics

This task is structural only.

**Step 5: Run rescue-phase and adjacent tests**

Run:

```bash
python3.13 -m unittest tests.test_rescue_phase_runtime tests.test_learning tests.test_rescue_flow -q
```

Expected: PASS.

---

## Task 5: Collapse `recovery_phases.py` into a thin public facade

**Files:**
- Modify: `openclaw_watchdog/flows/recovery_phases.py`
- Modify: `openclaw_watchdog/flows/rescue_run.py`
- Modify: `docs/internal-architecture.md`
- Test: `tests/test_rescue_flow.py`

**Step 1: Remove inlined owner logic from `recovery_phases.py`**

After Tasks 2–4, `recovery_phases.py` should mainly:

- import the new owner modules
- expose the public phase entrypoints
- keep only the smallest compatibility-free wiring that still belongs to the facade

**Step 2: Re-check `rescue_run.py`**

Keep `rescue_run.py` thin and phase-oriented:

- baseline probe/sync
- initial finish
- deterministic recovery
- rescue phase

No extra decision logic should move back into it.

**Step 3: Update architecture docs**

Add the new owner modules to `docs/internal-architecture.md`.

**Step 4: Run focused validation**

Run:

```bash
python3.13 -m unittest tests.test_rescue_flow tests.test_docs_surface -q
```

Expected: PASS.

---

## Task 6: Full verification and rehearsal gate

**Files:**
- Verify only

**Step 1: Byte-compile touched modules**

Run:

```bash
python3.13 -m py_compile \
  openclaw_watchdog/flows/recovery_phases.py \
  openclaw_watchdog/flows/recovery_probe_runtime.py \
  openclaw_watchdog/flows/recovery_finalize_runtime.py \
  openclaw_watchdog/flows/deterministic_recovery_runtime.py \
  openclaw_watchdog/flows/rescue_phase_runtime.py \
  openclaw_watchdog/flows/rescue_run.py
```

Expected: PASS.

**Step 2: Run the full test suite**

Run:

```bash
python3.13 -m unittest discover -s tests -q
```

Expected: PASS.

**Step 3: Run critical rehearsal sequentially**

Run:

```bash
bash rehearsal/scripts/run-scenario.sh critical
```

Expected: all critical rescue-chain and learning scenarios PASS.

---

## Success criteria

This P0 slice is complete when:

- `openclaw_watchdog/flows/recovery_phases.py` is no longer the main logic hotspot;
- probe/state, finalization, deterministic recovery, and rescue-phase logic each have a clear owner module;
- `openclaw_watchdog/flows/rescue_run.py` stays a thin public coordinator;
- full unit tests remain green;
- critical rehearsal remains green without changing rescue semantics.
