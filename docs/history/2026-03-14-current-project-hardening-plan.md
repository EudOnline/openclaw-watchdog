# Current Project Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the current convergence from “default-fixed” to “truly fixed” OpenClaw fallback behavior, then reduce the next two structural hotspots so the project remains easy to evolve without re-inflating orchestration complexity.

**Architecture:** Keep the current OpenClaw-specific fallback direction intact: one canonical rescue order, detect-only bootstrap, no compatibility shims, no automatic installation, and local-only bounded mutation. Implement the next round as small TDD slices: first harden the executor-order contract, then split `cli.py` into owner modules, then trim the next heavy runtime modules by ownership rather than adding abstractions.

**Tech Stack:** Python 3.13 local validation, stdlib `unittest`, current rehearsal harness, existing `openclaw_watchdog` runtime owners, current docs/test surface guards.

---

## Recommended scope

### Option A: Contract-first hardening plus hotspot decomposition (recommended)

1. Make rescue executor order truly fixed in code, config, docs, and tests.
2. Split `openclaw_watchdog/cli.py` into smaller command-owner modules without changing CLI surface.
3. Continue reducing the next heavy modules (`survival.py`, `incidents.py`, `detect.py`) by owner seams.

**Why this is recommended:** it closes the main product/implementation mismatch first, then spends effort where maintainability pressure is now highest.

### Option B: Keep structure as-is and only add features

Ship more rescue capability or learning behavior now, while leaving order mutability and CLI hotspot structure in place.

**Why this is not recommended:** it increases the chance that future changes reopen the same structural issues that were just fixed.

### Option C: Rewrite orchestration again

Do another large structural rewrite across CLI, flows, and runtime boundaries.

**Why this is not recommended:** the current architecture is already good enough to evolve incrementally; a large rewrite would increase risk without proportional value.

**Recommendation:** choose **Option A**.

---

## Task 1: Make rescue executor order truly fixed

**Files:**
- Modify: `openclaw_watchdog/executor_registry.py`
- Modify: `openclaw_watchdog/config.py`
- Modify: `config/openclaw-watchdog.env.example`
- Modify: `README.md`
- Modify: `docs/internal-architecture.md`
- Modify: `docs/first-deployment.md`
- Test: `tests/test_config.py`
- Test: `tests/test_executor_registry.py`
- Test: `tests/test_rescue_flow.py`

**Step 1: Write the failing tests**

Add focused tests that lock the intended product rule:
- executor order is always `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`
- config parsing no longer treats `WATCHDOG_RESCUE_EXECUTOR_PRIORITY` as a supported runtime input
- registry output still filters by availability, but never reorders the canonical chain

**Step 2: Run the focused tests to verify failure**

Run:
```bash
python3.13 -m unittest tests.test_config tests.test_executor_registry tests.test_rescue_flow -v
```

Expected: FAIL because executor order is still configurable today.

**Step 3: Implement the minimal code change**

- Remove configurable-priority behavior from `openclaw_watchdog/executor_registry.py`
- Make registry order derive only from the canonical constant
- Remove the public config/env surface for rescue-order overrides from `openclaw_watchdog/config.py` and `config/openclaw-watchdog.env.example`
- Update docs so they describe the order as fixed, not configurable

**Step 4: Run the focused tests to verify pass**

Run:
```bash
python3.13 -m unittest tests.test_config tests.test_executor_registry tests.test_rescue_flow -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/executor_registry.py openclaw_watchdog/config.py config/openclaw-watchdog.env.example README.md docs/internal-architecture.md docs/first-deployment.md tests/test_config.py tests/test_executor_registry.py tests/test_rescue_flow.py
git commit -m "fix: make rescue executor order canonical"
```

---

## Task 2: Split `cli.py` into command-owner modules

**Files:**
- Create: `openclaw_watchdog/cli_commands/__init__.py`
- Create: `openclaw_watchdog/cli_commands/run_once_command.py`
- Create: `openclaw_watchdog/cli_commands/status_command.py`
- Create: `openclaw_watchdog/cli_commands/report_command.py`
- Create: `openclaw_watchdog/cli_commands/metrics_command.py`
- Create: `openclaw_watchdog/cli_commands/incidents_command.py`
- Create: `openclaw_watchdog/cli_commands/bootstrap_command.py`
- Create: `openclaw_watchdog/cli_commands/maintenance_command.py`
- Modify: `openclaw_watchdog/cli.py`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_cli_json_contract.py`
- Test: `tests/test_cli_presenters.py`

**Step 1: Write the failing tests**

Add focused seam tests that pin:
- `cli.py` keeps the same public parser and exit behavior
- each major subcommand dispatches through a dedicated command-owner function
- JSON/text output contracts do not drift during the split

**Step 2: Run the focused tests to verify failure**

Run:
```bash
python3.13 -m unittest tests.test_cli_smoke tests.test_cli_json_contract tests.test_cli_presenters -v
```

Expected: FAIL because the command-owner modules do not exist yet.

**Step 3: Implement the minimal split**

- Move per-command execution logic out of `openclaw_watchdog/cli.py`
- Keep parser construction and top-level command routing in `cli.py`
- Do not change the CLI names, flags, presenter behavior, or JSON field shapes

**Step 4: Run focused tests to verify pass**

Run:
```bash
python3.13 -m unittest tests.test_cli_smoke tests.test_cli_json_contract tests.test_cli_presenters -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/cli.py openclaw_watchdog/cli_commands tests/test_cli_smoke.py tests/test_cli_json_contract.py tests/test_cli_presenters.py
git commit -m "refactor: split cli command handlers"
```

---

## Task 3: Split `survival.py` by state vs policy vs transitions

**Files:**
- Create: `openclaw_watchdog/survival_state_runtime.py`
- Create: `openclaw_watchdog/survival_policy_runtime.py`
- Create: `openclaw_watchdog/survival_transition_runtime.py`
- Modify: `openclaw_watchdog/survival.py`
- Modify: `openclaw_watchdog/state_transition.py`
- Modify: `openclaw_watchdog/engine.py`
- Test: `tests/test_maintenance_runtime.py`
- Test: `tests/test_state_transition.py`
- Test: `tests/test_rescue_flow.py`

**Step 1: Write the failing tests**

Add focused tests that pin:
- survival mode state projection fields
- sticky/manual-clear exit rules
- transition side effects when survival state changes

**Step 2: Run the focused tests to verify failure**

Run:
```bash
python3.13 -m unittest tests.test_maintenance_runtime tests.test_state_transition tests.test_rescue_flow -v
```

Expected: FAIL because the new owner modules do not exist yet.

**Step 3: Implement the minimal split**

- Move pure survival state-field shaping into `survival_state_runtime.py`
- Move exit/readiness policy into `survival_policy_runtime.py`
- Move state mutation / transition helpers into `survival_transition_runtime.py`
- Keep `openclaw_watchdog/survival.py` as a thin facade

**Step 4: Run focused tests to verify pass**

Run:
```bash
python3.13 -m unittest tests.test_maintenance_runtime tests.test_state_transition tests.test_rescue_flow -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/survival.py openclaw_watchdog/survival_state_runtime.py openclaw_watchdog/survival_policy_runtime.py openclaw_watchdog/survival_transition_runtime.py openclaw_watchdog/state_transition.py openclaw_watchdog/engine.py tests/test_maintenance_runtime.py tests/test_state_transition.py tests/test_rescue_flow.py
git commit -m "refactor: split survival runtime ownership"
```

---

## Task 4: Split incident read models from incident workflow

**Files:**
- Create: `openclaw_watchdog/incident_read_runtime.py`
- Create: `openclaw_watchdog/incident_write_runtime.py`
- Modify: `openclaw_watchdog/incident_service.py`
- Modify: `openclaw_watchdog/incidents.py`
- Modify: `openclaw_watchdog/reporting.py`
- Modify: `openclaw_watchdog/cli.py`
- Test: `tests/test_incident_cutover.py`
- Test: `tests/test_reporting.py`
- Test: `tests/test_cli_json_contract.py`

**Step 1: Write the failing tests**

Add seam tests that pin:
- incident queue/detail/timeline payload shapes
- incident owner/ack/note workflow behavior
- reporting and CLI still read the same incident fields

**Step 2: Run the focused tests to verify failure**

Run:
```bash
python3.13 -m unittest tests.test_incident_cutover tests.test_reporting tests.test_cli_json_contract -v
```

Expected: FAIL because the new read/write owner modules do not exist yet.

**Step 3: Implement the minimal split**

- Move read-heavy payload construction into `incident_read_runtime.py`
- Move write/update workflow into `incident_write_runtime.py`
- Keep `incident_service.py` as a narrow coordination facade

**Step 4: Run focused tests to verify pass**

Run:
```bash
python3.13 -m unittest tests.test_incident_cutover tests.test_reporting tests.test_cli_json_contract -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/incident_service.py openclaw_watchdog/incidents.py openclaw_watchdog/incident_read_runtime.py openclaw_watchdog/incident_write_runtime.py openclaw_watchdog/reporting.py openclaw_watchdog/cli.py tests/test_incident_cutover.py tests/test_reporting.py tests/test_cli_json_contract.py
git commit -m "refactor: split incident read and write ownership"
```

---

## Task 5: Split `detect.py` into host inspection owners

**Files:**
- Create: `openclaw_watchdog/detect_service_runtime.py`
- Create: `openclaw_watchdog/detect_executor_runtime.py`
- Create: `openclaw_watchdog/detect_health_runtime.py`
- Modify: `openclaw_watchdog/detect.py`
- Modify: `openclaw_watchdog/bootstrap_inventory.py`
- Test: `tests/test_detect.py`
- Test: `tests/test_executor_registry.py`
- Test: `tests/test_bootstrap_steps.py`

**Step 1: Write the failing tests**

Add seam tests that pin:
- host/service inspection behavior
- executor inventory shaping
- detect payload fields consumed by bootstrap and status/report surfaces

**Step 2: Run the focused tests to verify failure**

Run:
```bash
python3.13 -m unittest tests.test_detect tests.test_executor_registry tests.test_bootstrap_steps -v
```

Expected: FAIL because the new detect owner modules do not exist yet.

**Step 3: Implement the minimal split**

- Move service/process inspection into `detect_service_runtime.py`
- Move executor/tool inventory shaping into `detect_executor_runtime.py`
- Move overall detect payload assembly into `detect_health_runtime.py`
- Keep `detect.py` as a thin public facade

**Step 4: Run focused tests to verify pass**

Run:
```bash
python3.13 -m unittest tests.test_detect tests.test_executor_registry tests.test_bootstrap_steps -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/detect.py openclaw_watchdog/detect_service_runtime.py openclaw_watchdog/detect_executor_runtime.py openclaw_watchdog/detect_health_runtime.py openclaw_watchdog/bootstrap_inventory.py tests/test_detect.py tests/test_executor_registry.py tests/test_bootstrap_steps.py
git commit -m "refactor: split detect runtime ownership"
```

---

## Task 6: Run full verification and rehearsal gate

**Files:**
- Verify only

**Step 1: Run docs surface guard**

Run:
```bash
python3.13 -m unittest tests.test_docs_surface -q
```

Expected: `OK`

**Step 2: Run full unit suite**

Run:
```bash
python3.13 -m unittest discover -s tests -q
```

Expected: `OK`

**Step 3: Run critical rehearsal**

Run:
```bash
bash rehearsal/scripts/run-scenario.sh critical
```

Expected: all critical scenarios pass sequentially.

**Step 4: Commit final stabilization updates if needed**

```bash
git add .
git commit -m "test: verify current hardening slice"
```

---

## Exit criteria

- rescue executor order is implemented as truly fixed, not “default fixed but overridable”
- `openclaw_watchdog/cli.py` is no longer the dominant orchestration hotspot
- `survival.py`, `incident_service.py`, and `detect.py` each have narrower ownership boundaries
- docs, config surface, and implementation all tell the same story
- full unit suite passes
- critical rehearsal passes

---

## Recommended execution order

1. `fix: make rescue executor order canonical`
2. `refactor: split cli command handlers`
3. `refactor: split survival runtime ownership`
4. `refactor: split incident read and write ownership`
5. `refactor: split detect runtime ownership`
6. `test: verify current hardening slice`
