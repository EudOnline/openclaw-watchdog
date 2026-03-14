# OpenClaw Watchdog Next-Stage Execution Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the already-landed survivability architecture into a release-gated, production-trustworthy operating surface by tightening rehearsals, adapter robustness, operator-surface consistency, and deployment guidance.

**Architecture:** Treat the current conversation-aware probe, deterministic recovery chain, survival mode, last-good rollback, drift guard, and learning system as the baseline. The next stage should avoid inventing new core recovery primitives unless verification exposes a real gap. Work should instead focus on hardening the verified path: align the rehearsal harness with the canonical rescue contract, increase direct-flow coverage on the riskiest branches, make external adapter behavior more predictable, and keep `status` / `report` / `metrics` / live acceptance saying the same thing.

**Tech Stack:** Python 3.11 and 3.13, stdlib `unittest`, repo-local rehearsal harness, GitHub Actions, shell wrappers, existing `openclaw_watchdog` runtime owners.

---

## Recommended execution order

1. `P0-1` Remove stale rescue-order override artifacts from the harness
2. `P0-2` Promote survivability-critical rehearsal scenarios into the CI gate
3. `P1-1` Deepen direct flow coverage for deterministic recovery branches
4. `P1-2` Harden external CLI rescue adapter parsing and fallback behavior
5. `P2-1` Unify operator-surface and live-acceptance wording/contracts
6. `P2-2` Finish deployment and onboarding doc convergence

This order keeps product-truth and release protection ahead of incremental polish.

---

## P0: Make the release gate match the product contract

### Task P0-1: Remove stale rescue-order override artifacts from rehearsal and tests

**Files:**
- Modify: `rehearsal/scripts/run-scenario.sh`
- Modify: `tests/test_rescue_runtime.py`
- Modify: `tests/test_rescue_flow.py`
- Modify: `rehearsal/scenarios/README.md`
- Test: `tests/test_config.py`
- Test: `tests/test_executor_registry.py`
- Test: `tests/test_rescue_runtime.py`

**Why this task exists**

The code and docs now describe executor order as fixed and canonical, but the rehearsal harness still injects `WATCHDOG_RESCUE_EXECUTOR_PRIORITY=...` in scenario commands. That creates a false second contract: production says “fixed order,” while local validation still exercises “override order.” This needs to be removed before the rest of the next-stage hardening, or every adapter and scenario task will continue to validate the wrong model.

**Step 1: Write the failing tests**

Add focused assertions that the harness and runtime no longer depend on priority overrides:

```python
def test_run_scenario_script_does_not_use_priority_override(self):
    text = Path("rehearsal/scripts/run-scenario.sh").read_text(encoding="utf-8")
    self.assertNotIn("WATCHDOG_RESCUE_EXECUTOR_PRIORITY=", text)
```

```python
def test_rescue_runtime_uses_canonical_availability_order(self):
    config = SimpleNamespace(watchdog_litellm_enabled=False, watchdog_litellm_model="")
    self.assertEqual(available_executors(config), ("rule-agent",))
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_config tests.test_executor_registry tests.test_rescue_runtime -v
```

Expected: FAIL because the rehearsal harness and at least one focused test still reference the removed override path.

**Step 3: Write the minimal implementation**

- Rewrite rescue-chain rehearsal cases so they control executor selection by scenario fixture state, binary availability, or explicit enable/disable flags instead of priority injection.
- Remove stale test fixtures that mutate `watchdog_rescue_executor_priority`.
- Update `rehearsal/scenarios/README.md` so it describes the tiering model without implying order overrides.

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_config tests.test_executor_registry tests.test_rescue_runtime tests.test_rescue_flow -v
```

Expected: PASS.

**Step 5: Run a narrow rehearsal sanity check**

Run:

```bash
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-codex
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-rule-agent
```

Expected: PASS without `WATCHDOG_RESCUE_EXECUTOR_PRIORITY`.

**Step 6: Commit**

```bash
git add rehearsal/scripts/run-scenario.sh rehearsal/scenarios/README.md tests/test_rescue_runtime.py tests/test_rescue_flow.py
git commit -m "fix: align rehearsal rescue order with canonical contract"
```

### Task P0-2: Promote survivability-critical scenarios into the CI release gate

**Files:**
- Modify: `rehearsal/scripts/run-scenario.sh`
- Modify: `rehearsal/scenarios/README.md`
- Modify: `tests/test_rehearsal_smoke_matrix.py`
- Modify: `.github/workflows/ci.yml`

**Why this task exists**

Conversation probe, rollback-before-doctor, survival mode, and drift guard are already core product behavior, but they still live in the extended tier. The next-stage goal is to make “survivability correctness” part of the release gate rather than an optional local sweep.

**Step 1: Write the failing test**

Add a focused matrix assertion for the promoted scenarios:

```python
for scenario in [
    "watchdog-conversation-probe-ready",
    "watchdog-rollback-priority-before-doctor",
    "watchdog-survival-mode-recovery",
    "watchdog-config-drift-guard",
]:
    self.assertIn(scenario, CRITICAL_SCENARIOS)
```

**Step 2: Run the matrix test to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_rehearsal_smoke_matrix -v
```

Expected: FAIL because those scenarios are still listed under `EXTENDED_SCENARIOS`.

**Step 3: Write the minimal implementation**

- Move the selected survivability scenarios into `CRITICAL_SCENARIOS`.
- Keep the critical set intentionally small and stable; do not move operator-workflow-only scenarios.
- Update `.github/workflows/ci.yml` only if the critical invocation or comments need to explain the expanded gate.

**Step 4: Run the focused test to verify it passes**

Run:

```bash
python3.13 -m unittest tests.test_rehearsal_smoke_matrix -v
```

Expected: PASS.

**Step 5: Run the critical rehearsal group**

Run:

```bash
bash rehearsal/scripts/run-scenario.sh critical
```

Expected: PASS, with runtime still acceptable for CI.

**Step 6: Commit**

```bash
git add rehearsal/scripts/run-scenario.sh rehearsal/scenarios/README.md tests/test_rehearsal_smoke_matrix.py .github/workflows/ci.yml
git commit -m "test: promote survivability scenarios into critical rehearsal gate"
```

---

## P1: Raise confidence in the actual recovery path

### Task P1-1: Deepen direct flow coverage for deterministic recovery branches

**Files:**
- Modify: `tests/test_deterministic_recovery_runtime.py`
- Modify: `tests/test_rescue_phase_runtime.py`
- Modify: `tests/test_rescue_flow.py`
- Modify: `tests/test_repair_action_runtime.py`
- Modify: `openclaw_watchdog/flows/deterministic_recovery_runtime.py`
- Modify: `openclaw_watchdog/flows/rescue_phase_runtime.py`

**Why this task exists**

The architectural pieces are in place, but the roadmap still calls out deeper direct flow coverage for restart, rollback, survival, and rescue-dispatch branches. This is the highest-value coverage gap left in the core runtime.

**Step 1: Write the failing tests**

Add narrow tests for branches that are already product-significant but easy to regress:

```python
def test_doctor_is_skipped_when_rollback_restores_minimal_usability(self):
    ...
    self.assertEqual(result.status, "recovered")
    self.assertNotIn("doctor", engine.ctx.last_recovery_path)
```

```python
def test_survival_branch_records_degraded_but_usable_outcome(self):
    ...
    self.assertTrue(engine.ctx.survival_mode_active)
    self.assertEqual(engine.ctx.last_recovery_strategy, "survival")
```

```python
def test_rescue_phase_records_negative_learning_for_rolled_back_plan(self):
    ...
    self.assertEqual(engine.ctx.candidate_rule_status, "negative-evidence-recorded")
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_deterministic_recovery_runtime tests.test_rescue_phase_runtime tests.test_rescue_flow tests.test_repair_action_runtime -v
```

Expected: FAIL on at least one uncovered branch or mismatched recovery marker.

**Step 3: Write the minimal implementation**

- Fix only the missing branch accounting or recovery markers exposed by the new tests.
- Do not reorder recovery phases or widen mutation scope while increasing coverage.
- Keep deterministic recovery semantics aligned with `restart -> rollback -> survival -> doctor -> rescue`.

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_deterministic_recovery_runtime tests.test_rescue_phase_runtime tests.test_rescue_flow tests.test_repair_action_runtime -v
```

Expected: PASS.

**Step 5: Run one targeted survivability rehearsal**

Run:

```bash
bash rehearsal/scripts/run-scenario.sh watchdog-rollback-priority-before-doctor
bash rehearsal/scripts/run-scenario.sh watchdog-survival-mode-recovery
```

Expected: PASS.

**Step 6: Commit**

```bash
git add tests/test_deterministic_recovery_runtime.py tests/test_rescue_phase_runtime.py tests/test_rescue_flow.py tests/test_repair_action_runtime.py openclaw_watchdog/flows/deterministic_recovery_runtime.py openclaw_watchdog/flows/rescue_phase_runtime.py
git commit -m "test: deepen deterministic recovery branch coverage"
```

### Task P1-2: Harden external CLI rescue adapter parsing and fallback behavior

**Files:**
- Modify: `openclaw_watchdog/rescue_agents/base.py`
- Modify: `openclaw_watchdog/rescue_agents/codex_adapter.py`
- Modify: `openclaw_watchdog/rescue_agents/claude_code_adapter.py`
- Modify: `openclaw_watchdog/rescue_agents/gemini_cli_adapter.py`
- Modify: `openclaw_watchdog/rescue_agents/opencode_adapter.py`
- Modify: `tests/test_cli_rescue_adapters.py`
- Modify: `tests/test_rescue_dispatch.py`
- Modify: `docs/roadmap.md`

**Why this task exists**

The no-shell, structured-plan contract is already in place, but the roadmap still names adapter improvement as a near-term follow-up. The likely remaining risk is not policy but robustness: nested JSON, banner/noise text, empty plans, malformed plan fields, and clear executor rejection/fallback when a provider returns garbage.

**Step 1: Write the failing tests**

Add adapter tests for noisy but recoverable provider output and hard rejection cases:

```python
def test_adapter_extracts_last_json_object_from_noisy_stdout(self):
    ...
    self.assertEqual(plan.plan_id, "plan-codex")
```

```python
def test_adapter_rejects_plan_with_unknown_top_level_keys(self):
    ...
    with self.assertRaises(ValueError):
        adapter.propose_plan(context)
```

```python
def test_dispatch_continues_to_next_executor_after_parse_failure(self):
    ...
    self.assertEqual(result.executor, "rule-agent")
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_cli_rescue_adapters tests.test_rescue_dispatch -v
```

Expected: FAIL because at least one adapter still accepts overly loose output or does not degrade cleanly to the next executor.

**Step 3: Write the minimal implementation**

- Tighten parsing in the shared adapter base where possible.
- Keep provider-specific command invocation unchanged unless the failing test proves a concrete problem.
- Preserve the current “structured plans only” contract.
- Ensure dispatch logs or marks a rejection cleanly and continues down the canonical chain.

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_cli_rescue_adapters tests.test_rescue_dispatch -v
```

Expected: PASS.

**Step 5: Run the critical rescue-chain rehearsal group**

Run:

```bash
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-codex
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-claude-code
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-gemini-cli
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-opencode
```

Expected: PASS.

**Step 6: Commit**

```bash
git add openclaw_watchdog/rescue_agents/base.py openclaw_watchdog/rescue_agents/codex_adapter.py openclaw_watchdog/rescue_agents/claude_code_adapter.py openclaw_watchdog/rescue_agents/gemini_cli_adapter.py openclaw_watchdog/rescue_agents/opencode_adapter.py tests/test_cli_rescue_adapters.py tests/test_rescue_dispatch.py docs/roadmap.md
git commit -m "fix: harden external rescue adapter parsing"
```

---

## P2: Keep operator-facing outputs and docs aligned

### Task P2-1: Unify operator-surface and live-acceptance wording/contracts

**Files:**
- Modify: `openclaw_watchdog/presenters/status.py`
- Modify: `tests/test_cli_presenters.py`
- Modify: `scripts/openclaw-watchdog-live-acceptance.sh`
- Modify: `docs/live-acceptance-checklist.md`
- Modify: `docs/reporting-contract.md`

**Why this task exists**

The main data contract is aligned, but wording and surface checks have drifted. For example, the status summary currently prints `conv=...`, while the live acceptance script still checks for `conversation=`. This kind of mismatch is small but dangerous because it makes operator validation noisy and undermines confidence in the release gate.

**Step 1: Write the failing tests**

Add one presenter test and one acceptance-contract test:

```python
def test_status_summary_uses_the_documented_conversation_token(self):
    text = render_status_summary(payload)
    self.assertIn("conversation=", text)
```

```python
def test_acceptance_script_checks_match_current_status_summary_contract(self):
    script = Path("scripts/openclaw-watchdog-live-acceptance.sh").read_text(encoding="utf-8")
    self.assertIn("status_summary_has_conversation", script)
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_cli_presenters tests.test_cli_json_contract -v
```

Expected: FAIL because the presenter text and live-acceptance check language are still out of sync.

**Step 3: Write the minimal implementation**

- Choose one wording and make all surfaces use it.
- Prefer the more explicit token if it does not harm summary readability.
- Keep JSON keys and Prometheus metric names unchanged.
- Update the acceptance script and checklist together.

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_cli_presenters tests.test_cli_json_contract tests.test_reporting -v
```

Expected: PASS.

**Step 5: Run the live-acceptance script locally if the workspace is configured**

Run:

```bash
./scripts/openclaw-watchdog-live-acceptance.sh
```

Expected: PASS on a configured host. If the local machine is not set up for a true run, at minimum keep the script syntactically valid and document the host requirement.

**Step 6: Commit**

```bash
git add openclaw_watchdog/presenters/status.py tests/test_cli_presenters.py scripts/openclaw-watchdog-live-acceptance.sh docs/live-acceptance-checklist.md docs/reporting-contract.md
git commit -m "docs: align operator surface and acceptance contract"
```

### Task P2-2: Finish deployment and onboarding doc convergence

**Files:**
- Modify: `README.md`
- Modify: `docs/first-deployment.md`
- Modify: `docs/supported-environments.md`
- Modify: `docs/rescue-lifecycle.md`
- Modify: `docs/faq.md`
- Modify: `CHANGELOG.md`

**Why this task exists**

The implementation story is now ahead of the operator story. The docs already describe the right direction, but the next stage should make the first-rollout path and “what is actually supported” unmistakable for operators who were not part of the refactor.

**Step 1: Write the failing docs-surface tests**

Add or extend tests to lock the main promises:

```python
def test_docs_describe_fixed_rescue_chain_and_detect_only_bootstrap(self):
    text = Path("docs/rescue-lifecycle.md").read_text(encoding="utf-8")
    self.assertIn("detect and read-only validation first", text.lower())
    self.assertIn("codex", text)
    self.assertIn("rule-agent", text)
```

```python
def test_readme_points_first_rollout_to_live_acceptance(self):
    text = Path("README.md").read_text(encoding="utf-8")
    self.assertIn("first-deployment", text)
    self.assertIn("live acceptance", text.lower())
```

**Step 2: Run the docs tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: FAIL if any of the operator promises are still under-specified or stale.

**Step 3: Write the minimal documentation update**

- Make the quick-start path explicitly: `detect -> check -> status --summary -> report --message -> live acceptance`.
- Keep the supported-environments doc strict about Linux + `systemd --user` and Python 3.11+.
- Clarify what is optional versus release-gated.
- Record any operator-surface change in `CHANGELOG.md`.

**Step 4: Run the docs test to verify it passes**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: PASS.

**Step 5: Run one final broad verification**

Run:

```bash
python3.13 -m unittest discover -s tests -q
bash rehearsal/scripts/run-scenario.sh critical
```

Expected: PASS.

**Step 6: Commit**

```bash
git add README.md docs/first-deployment.md docs/supported-environments.md docs/rescue-lifecycle.md docs/faq.md CHANGELOG.md
git commit -m "docs: converge deployment guidance with current fallback behavior"
```

---

## Completion gate

The next stage should be considered complete only when all of the following are true:

- the rehearsal harness no longer validates removed rescue-order override behavior;
- the critical rehearsal tier includes the most important survivability scenarios;
- deterministic recovery and rescue-phase branch coverage explicitly protects rollback, survival, and validation-driven outcomes;
- external rescue adapters reject malformed output cleanly and allow canonical-chain fallback;
- `status --summary`, `report`, `metrics`, and the live-acceptance script describe the same operator reality;
- deployment docs reflect the product that ships today, not the one the repo used to be.

Plan complete and saved to `docs/plans/2026-03-14-next-stage-execution-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
