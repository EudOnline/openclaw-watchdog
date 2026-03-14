# OpenClaw Watchdog Structure Governance Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Continue the no-compatibility cutover by shrinking orchestration hotspots, clarifying ownership boundaries, and making the OpenClaw fallback chain easier to evolve without re-inflating `engine.py`.

**Architecture:** Keep the current single-name, OpenClaw-specific design and continue the strangler refactor that is already working. Do not add frameworks or abstraction layers. Instead, move remaining runtime/health/report/state responsibilities to their owner modules, split large orchestration files by phase, and let `WatchdogEngine` converge toward a minimal runtime shell plus context container.

**Tech Stack:** Python 3.11+, stdlib `unittest`, current rehearsal harness, systemd/user-service probing, existing rescue agents (`codex`, `claude-code`, `gemini-cli`, `opencode`, `litellm`, `rule-agent`).

---

## Recommended governance approach

### Option A: Continue the current owner-first cutover (recommended)

Keep pushing direct module ownership exactly the way the recent slices have done:
- `cli.py` calls `health.py`, `reporting.py`, and `maintenance_runtime.py` directly;
- `rescue_run.py` calls `health.py` and `rescue_runtime.py` directly;
- `engine.py` only keeps methods that are still genuinely useful as runtime shell capabilities.

**Why this is recommended:** it matches the current direction, keeps regression risk low, and preserves the verified rescue chain behavior while making the codebase less magical and less wrapper-heavy each step.

### Option B: Freeze refactoring and add features now

Stop structural cleanup and spend the next phase on more rescue capabilities, more learning behavior, and more operator surface.

**Tradeoff:** near-term feature velocity improves, but remaining hotspots such as `rescue_run.py`, `reporting.py`, and `last_good_runtime.py` become harder to split later because new behavior will pile onto the old shapes.

### Option C: Rewrite the orchestration layer in one pass

Replace `rescue_run.py`, `health.py`, and `reporting.py` with a brand-new package layout immediately.

**Tradeoff:** the theoretical end-state may look cleaner faster, but it creates unnecessary risk because the current system already has verified tests and critical rehearsals that are passing.

**Recommendation:** choose **Option A** and continue with focused, owner-first cuts.

---

## Current system assessment baseline

- Canonical package and public surface are already `openclaw_watchdog`.
- Bootstrap is already detect-only / read-only and no longer auto-installs tools.
- Rescue order is already canonicalized as `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`.
- `engine.py` has already dropped probe/status/metrics/maintenance compatibility-style wrappers.
- Current verification baseline is strong enough to support more slicing:
  - `python3.13 -m unittest discover -s tests -q`
  - `bash rehearsal/scripts/run-scenario.sh critical`

The remaining work is no longer “fix the product direction.” It is “finish structural convergence so the product direction stays maintainable.”

---

## P0: Finish the boundary cleanup around orchestration hotspots

**Outcome:** `WatchdogEngine` stops being a silent business-logic router and becomes mostly runtime/context infrastructure.

### Task P0-1: Remove the remaining event/state/report wrappers from `engine.py`

**Files:**
- Modify: `openclaw_watchdog/engine.py`
- Modify: `openclaw_watchdog/state_transition.py`
- Modify: `openclaw_watchdog/flows/rescue_run.py`
- Modify: `openclaw_watchdog/cli.py`
- Modify: `openclaw_watchdog/reporting.py`
- Test: `tests/test_observability_cutover.py`
- Test: `tests/test_state_transition.py`
- Test: `tests/test_reporting.py`

**Steps:**
1. Write failing tests asserting `WatchdogEngine` no longer exposes `write_event`, `set_state`, and `report_payload`.
2. Run the focused tests and confirm failure for the expected missing-boundary reason.
3. Update callers to use `event_runtime.write_event`, `state_transition.set_state`, and `reporting.report_payload` directly.
4. Remove the wrapper methods from `engine.py`.
5. Re-run focused tests until they pass.

### Task P0-2: Remove the remaining deterministic repair wrappers from `engine.py`

**Files:**
- Modify: `openclaw_watchdog/engine.py`
- Modify: `openclaw_watchdog/health.py`
- Modify: `openclaw_watchdog/flows/rescue_run.py`
- Modify: `openclaw_watchdog/rescue_actions.py`
- Test: `tests/test_repair_cutover.py`
- Test: `tests/test_doctor_runtime.py`
- Test: `tests/test_rescue_flow.py`

**Steps:**
1. Add failing tests for the absence of `run_doctor`, `config_invalid`, `backup_last_good`, `run_pre_repair_backup`, `restore_last_good`, `restart_service`, and `run_doctor_repair` on `WatchdogEngine`.
2. Update direct callers to use `doctor_runtime`, `last_good_runtime`, `rollback_runtime`, and `repair_action_runtime`.
3. Remove the wrappers from `engine.py`.
4. Re-run the targeted suites and then the full rescue-flow suite.

### Task P0-3: Split `rescue_run.py` by recovery phase without changing behavior

**Files:**
- Create: `openclaw_watchdog/flows/recovery_phases.py`
- Modify: `openclaw_watchdog/flows/rescue_run.py`
- Test: `tests/test_rescue_flow.py`

**Steps:**
1. Write failing tests around one deterministic path and one rescue path to pin current behavior.
2. Extract phase helpers for:
   - baseline probe + survival sync
   - deterministic recovery chain
   - rescue dispatch / plan execution
   - success/failure finalization
3. Keep `run()` as the single public flow entrypoint.
4. Re-run focused and full tests.

**P0 exit criteria**
- `engine.py` is materially smaller and no longer owns state/event/report/repair decision routing.
- `rescue_run.py` reads like a phase coordinator instead of a giant mixed script.
- Full unit suite and critical rehearsal remain green.

---

## P1: Decompose the remaining large modules by responsibility

**Outcome:** large modules are still simple Python files, but each one has a smaller semantic surface and a clearer reason to change.

### Task P1-1: Split `health.py` into probe composition vs payload shaping

**Files:**
- Create: `openclaw_watchdog/health_probe_runtime.py`
- Create: `openclaw_watchdog/health_status_runtime.py`
- Modify: `openclaw_watchdog/health.py`
- Test: `tests/test_service_runtime.py`
- Test: `tests/test_observability_cutover.py`
- Test: `tests/test_incident_cutover.py`

**Intent:**
- keep `live_probe()` and low-level probe logic separate from `status_payload()`;
- reduce the chance that changing status output accidentally changes process/gateway checks.

### Task P1-2: Split `reporting.py` into report assembly vs metric export

**Files:**
- Create: `openclaw_watchdog/report_payload_runtime.py`
- Create: `openclaw_watchdog/metrics_runtime.py`
- Modify: `openclaw_watchdog/reporting.py`
- Test: `tests/test_reporting.py`
- Test: `tests/test_cli_json_contract.py`

**Intent:**
- report text, report JSON, metrics JSON, and Prometheus text currently live too close together;
- separating them lowers coupling between operator messaging and metric contracts.

### Task P1-3: Split `last_good_runtime.py` into guard/diff/generation concerns

**Files:**
- Create: `openclaw_watchdog/guard_runtime.py`
- Create: `openclaw_watchdog/generation_runtime.py`
- Modify: `openclaw_watchdog/last_good_runtime.py`
- Modify: `openclaw_watchdog/rollback_runtime.py`
- Modify: `openclaw_watchdog/survival.py`
- Test: `tests/test_last_good_runtime.py`
- Test: `tests/test_rollback_runtime.py`

**Intent:**
- current last-good logic is valuable but dense;
- guard snapshots, baseline generation bookkeeping, and drift context should stop living in one heavy module.

**P1 exit criteria**
- `health.py`, `reporting.py`, and `last_good_runtime.py` are visibly smaller.
- Each extracted module has one narrow ownership story.
- Contract tests for status/report/metrics remain stable.

---

## P2: Harden the rescue learning system and OpenClaw-specific operating model

**Outcome:** the architecture fully reflects that this is an OpenClaw-specific fallback system, not a generic watchdog toolkit.

### Task P2-1: Make rescue learning explicitly phase-aware

**Files:**
- Modify: `openclaw_watchdog/rescue_learning_service.py`
- Modify: `openclaw_watchdog/learning.py`
- Modify: `openclaw_watchdog/rescue_agents/rule_agent.py`
- Test: `tests/test_learning.py`
- Test: `tests/test_rule_agent.py`

**Intent:**
- classify learned cases by deterministic failure, rescue failure, successful rescue, rolled-back rescue;
- make rule promotion depend on evidence quality, not just case accumulation.

### Task P2-2: Tighten the allowed mutation surface for OpenClaw config rescue

**Files:**
- Modify: `openclaw_watchdog/rescue_actions.py`
- Modify: `openclaw_watchdog/rescue_policy.py`
- Modify: `config/openclaw-watchdog.env.example`
- Modify: `README.md`
- Test: `tests/test_rescue_actions.py`
- Test: `tests/test_rescue_dispatch.py`

**Intent:**
- controlled config mutation is now allowed and useful;
- the next step is to make the editable path/key policy easier to understand, safer to reason about, and more obviously OpenClaw-specific.

### Task P2-3: Reframe docs around “OpenClaw fallback system” rather than “general watchdog”

**Files:**
- Modify: `README.md`
- Modify: `docs/internal-architecture.md`
- Modify: `docs/rescue-lifecycle.md`
- Modify: `docs/faq.md`
- Modify: `docs/supported-environments.md`

**Intent:**
- current code direction is already specialized;
- docs should stop carrying old generalized framing except in history docs.

**P2 exit criteria**
- learning and rule promotion are easier to trust and explain.
- mutation policy is explicit and minimal.
- docs and code tell the same story.

---

## Recommended execution order

1. **P0-1** `engine` event/state/report cut
2. **P0-2** deterministic repair wrapper cut
3. **P0-3** `rescue_run.py` phase split
4. **P1-1** `health.py` split
5. **P1-2** `reporting.py` split
6. **P1-3** `last_good_runtime.py` split
7. **P2-1** learning hardening
8. **P2-2** mutation-surface tightening
9. **P2-3** final doc convergence

This order keeps the highest-value structural work ahead of feature hardening and documentation polish.

---

## Verification strategy

After each task, run the smallest useful checks first, then widen:

1. Focused unit tests for the touched module(s)
2. Adjacent flow tests
3. Full suite:
   - `python3.13 -m unittest discover -s tests -q`
4. Critical rehearsal:
   - `bash rehearsal/scripts/run-scenario.sh critical`

Keep critical rehearsal sequential only.

---

## Success definition

The structural governance phase is successful when:
- `WatchdogEngine` becomes a thin runtime/context shell instead of a hidden routing layer;
- the rescue chain remains `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`;
- bootstrap remains read-only and never installs software;
- controlled OpenClaw config mutation remains possible but tightly bounded;
- the rule-based rescue path is clearly improving from accumulated rescue evidence;
- full tests and critical rehearsals keep passing throughout.
