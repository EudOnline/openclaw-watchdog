# Engine Facade Slimming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove domain-specific convenience wrappers from `openclaw_watchdog/engine.py` so the watchdog engine stays focused on lifecycle, shared process I/O, and top-level run orchestration.

**Architecture:** Keep `WatchdogEngine` as the composition root that owns config, state paths, lock lifecycle, shared command execution, and `RunContext`. Move recovery tracking, rollback helpers, drift context, and stray-listener actions to direct owner-module calls from their consumers. Do not add new abstraction layers or compatibility shims.

**Tech Stack:** Python 3.11+, stdlib dataclasses/pathlib/tempfile, existing `openclaw_watchdog` runtime modules, `unittest`, existing rehearsal scenarios.

---

### Task 1: Lock the new engine seam with failing tests

**Files:**
- Modify: `tests/test_repair_cutover.py`
- Inspect: `openclaw_watchdog/engine.py`

**Step 1: Add missing seam assertions**

Add tests that assert `WatchdogEngine` no longer exposes these wrapper methods:
- `reset_recovery_tracking`
- `record_recovery_step`
- `recovery_path_text`
- `finalize_recovery_tracking`
- `capture_rollback_summary`
- `_walk_json_diff`
- `prune_rollback_archives`
- `drift_context`
- `refresh_drift_context`
- `kill_stray_listeners`

**Step 2: Add direct-owner delegation assertions**

Add or update cutover tests so the affected runtimes prove they use:
- `recovery_tracking` directly
- `rollback_runtime` directly
- `last_good_runtime` directly
- `repair_action_runtime` directly

**Step 3: Run the focused RED test subset**

Run: `python3.13 -m unittest tests.test_repair_cutover tests.test_rescue_flow tests.test_recovery_probe_runtime tests.test_recovery_finalize_runtime -v`

Expected: FAIL because `engine.py` still exposes the wrapper methods.

**Step 4: Commit**

```bash
git add tests/test_repair_cutover.py
git commit -m "test: lock thinner engine facade seams"
```

---

### Task 2: Remove recovery tracking wrappers from engine.py

**Files:**
- Modify: `openclaw_watchdog/engine.py`
- Modify: `openclaw_watchdog/flows/rescue_run.py`
- Modify: `openclaw_watchdog/flows/recovery_probe_runtime.py`
- Modify: `openclaw_watchdog/flows/recovery_finalize_runtime.py`
- Modify: `openclaw_watchdog/state_transition.py`
- Modify: `openclaw_watchdog/incident_write_runtime.py`

**Step 1: Delete thin recovery-tracking wrappers from `WatchdogEngine`**

Remove:
- `reset_recovery_tracking`
- `record_recovery_step`
- `recovery_path_text`
- `finalize_recovery_tracking`

**Step 2: Update consumers to use `recovery_tracking` directly**

Use `engine.ctx` explicitly at each call site. Preserve current behavior and field values exactly.

**Step 3: Run focused tests**

Run: `python3.13 -m unittest tests.test_rescue_flow tests.test_recovery_probe_runtime tests.test_recovery_finalize_runtime -v`

Expected: PASS.

**Step 4: Commit**

```bash
git add openclaw_watchdog/engine.py openclaw_watchdog/flows/rescue_run.py openclaw_watchdog/flows/recovery_probe_runtime.py openclaw_watchdog/flows/recovery_finalize_runtime.py openclaw_watchdog/state_transition.py openclaw_watchdog/incident_write_runtime.py
git commit -m "refactor: remove engine recovery tracking wrappers"
```

---

### Task 3: Remove rollback, drift, and listener wrappers from engine.py

**Files:**
- Modify: `openclaw_watchdog/engine.py`
- Modify: `openclaw_watchdog/flows/rescue_run.py`
- Modify: `tests/test_repair_cutover.py`

**Step 1: Delete the remaining domain-specific wrappers**

Remove:
- `capture_rollback_summary`
- `_walk_json_diff`
- `prune_rollback_archives`
- `drift_context`
- `refresh_drift_context`
- `kill_stray_listeners`

**Step 2: Update runtime consumers**

Replace remaining `engine.*` calls with direct calls to:
- `rollback_runtime`
- `last_good_runtime`
- `repair_action_runtime`

**Step 3: Re-run the focused seam subset**

Run: `python3.13 -m unittest tests.test_repair_cutover tests.test_rescue_flow tests.test_repair_action_runtime -v`

Expected: PASS.

**Step 4: Commit**

```bash
git add openclaw_watchdog/engine.py openclaw_watchdog/flows/rescue_run.py tests/test_repair_cutover.py
git commit -m "refactor: remove engine domain helper wrappers"
```

---

### Task 4: Verify the slice end-to-end

**Files:**
- Inspect: `openclaw_watchdog/engine.py`
- Inspect: `tests/test_repair_cutover.py`

**Step 1: Run the focused engine-adjacent suite**

Run: `python3.13 -m unittest tests.test_repair_cutover tests.test_rescue_flow tests.test_recovery_probe_runtime tests.test_recovery_finalize_runtime tests.test_repair_action_runtime -v`

Expected: PASS.

**Step 2: Run the full suite**

Run: `python3.13 -m unittest discover -s tests -q`

Expected: PASS.

**Step 3: Run the critical rehearsal scenarios**

Run: `bash rehearsal/scripts/run-scenario.sh critical`

Expected: all critical scenarios pass.

**Step 4: Commit**

```bash
git add openclaw_watchdog/engine.py openclaw_watchdog/flows/rescue_run.py openclaw_watchdog/flows/recovery_probe_runtime.py openclaw_watchdog/flows/recovery_finalize_runtime.py openclaw_watchdog/state_transition.py openclaw_watchdog/incident_write_runtime.py tests/test_repair_cutover.py docs/plans/2026-03-14-engine-facade-slimming.md
git commit -m "refactor: slim engine domain facade"
```
