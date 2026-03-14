# OpenClaw Watchdog Next P0-P2 Rebuild Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden the current OpenClaw-specific rescue system for long-term maintainability by shrinking orchestration hotspots, making host mutation crash-safe, improving learning quality, and tightening operator observability and rehearsal discipline.

**Architecture:** Keep the current single rescue-first product direction intact: deterministic repair runs first, external executors only return structured rescue plans, and all host mutation stays inside the local white-listed action executor. The next iteration focuses on extracting smaller runtime services from `openclaw_watchdog/engine.py`, adding atomic config mutation and stronger validation gates, upgrading learning from exact-match case replay to normalized signatures plus rule lifecycle controls, and introducing one shared operator snapshot for `status` / `report` / `metrics`.

**Tech Stack:** Python 3.11+, standard library, `unittest`, repo-local rehearsal harness, GitHub Actions.

---

## Scope guardrails

Before implementation starts, keep these constraints explicit:

- do **not** reintroduce compatibility shims, auto-install behavior, or legacy fallback branches;
- do **not** give rescue agents arbitrary shell execution;
- do **not** add framework or DI-container style infrastructure;
- keep validation on `python3.13` locally and preserve CI compatibility with the existing `python` invocations.

---

## P0: Stabilize structure and write safety

### Task P0-1: Extract run-state and recovery-tracking services out of `engine.py`

**Files:**
- Create: `openclaw_watchdog/run_state_service.py`
- Create: `openclaw_watchdog/recovery_tracking.py`
- Modify: `openclaw_watchdog/engine.py`
- Modify: `openclaw_watchdog/health.py`
- Modify: `openclaw_watchdog/reporting.py`
- Test: `tests/test_run_context.py`
- Test: `tests/test_rescue_flow.py`
- Test: `tests/test_reporting.py`

**Step 1: Write the failing tests**

Add focused tests that lock in the extracted helper contracts without changing public behavior:
- `tests/test_run_context.py::test_run_state_service_round_trips_learning_and_attempt_fields`
- `tests/test_rescue_flow.py::test_recovery_tracking_helper_keeps_action_count_and_path_order`
- `tests/test_reporting.py::test_report_payload_reads_extracted_run_state_fields`

**Step 2: Run tests to verify they fail**

Run:
```bash
python3.13 -m unittest   tests.test_run_context tests.test_rescue_flow tests.test_reporting -v
```
Expected: FAIL because the new helper modules do not exist yet.

**Step 3: Write the minimal implementation**

- Move default run-state shaping, read/write helpers, and recovery-field resets into `openclaw_watchdog/run_state_service.py`.
- Move recovery-path accumulation and summary shaping into `openclaw_watchdog/recovery_tracking.py`.
- Keep `WatchdogEngine` as the facade that delegates to those helpers.
- Do not change CLI output or report/metrics contracts in this task.

**Step 4: Run tests to verify they pass**

Run:
```bash
python3.13 -m unittest   tests.test_run_context tests.test_rescue_flow tests.test_reporting -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/run_state_service.py openclaw_watchdog/recovery_tracking.py openclaw_watchdog/engine.py openclaw_watchdog/health.py openclaw_watchdog/reporting.py tests/test_run_context.py tests/test_rescue_flow.py tests/test_reporting.py
git commit -m "refactor: extract run-state and recovery tracking services"
```

### Task P0-2: Make OpenClaw config mutation atomic and crash-safe

**Files:**
- Create: `openclaw_watchdog/file_ops.py`
- Modify: `openclaw_watchdog/rescue_actions.py`
- Modify: `openclaw_watchdog/rescue_policy.py`
- Test: `tests/test_rescue_actions.py`

**Step 1: Write the failing tests**

Add tests for crash-safe config writes:
- `tests/test_rescue_actions.py::test_update_openclaw_config_preserves_original_file_when_replace_fails`
- `tests/test_rescue_actions.py::test_update_openclaw_config_cleans_up_temp_file_after_success`
- `tests/test_rescue_actions.py::test_update_openclaw_config_rejects_non_object_json_root`

**Step 2: Run tests to verify they fail**

Run:
```bash
python3.13 -m unittest tests.test_rescue_actions -v
```
Expected: FAIL because current writes are direct and not atomic.

**Step 3: Write the minimal implementation**

- Add a small helper in `openclaw_watchdog/file_ops.py` that writes JSON through temp-file + flush + replace.
- Make `openclaw_watchdog/rescue_actions.py` use that helper for `update_openclaw_config()`.
- Keep the existing allowed-path and allowed-key checks.
- Avoid introducing third-party locking libraries; standard-library only.

**Step 4: Run tests to verify they pass**

Run:
```bash
python3.13 -m unittest tests.test_rescue_actions -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/file_ops.py openclaw_watchdog/rescue_actions.py openclaw_watchdog/rescue_policy.py tests/test_rescue_actions.py
git commit -m "fix: make rescue config writes atomic"
```

### Task P0-3: Strengthen validation gates for mutating rescue plans

**Files:**
- Modify: `openclaw_watchdog/rescue_actions.py`
- Modify: `openclaw_watchdog/health.py`
- Modify: `openclaw_watchdog/flows/rescue_run.py`
- Test: `tests/test_rescue_actions.py`
- Test: `tests/test_rescue_flow.py`

**Step 1: Write the failing tests**

Add tests for stricter rollback-on-worsen behavior:
- `tests/test_rescue_actions.py::test_rolls_back_when_service_layer_degrades_after_mutation`
- `tests/test_rescue_actions.py::test_rolls_back_when_config_validation_fails_after_mutation`
- `tests/test_rescue_flow.py::test_failed_validation_marks_rescue_result_as_rolled_back`

**Step 2: Run tests to verify they fail**

Run:
```bash
python3.13 -m unittest tests.test_rescue_actions tests.test_rescue_flow -v
```
Expected: FAIL because the current validation only checks minimal / conversation regression.

**Step 3: Write the minimal implementation**

- Expand validation so mutating plans may gate on:
  - `service_layer_healthy`
  - `minimal_usable_ready`
  - `conversation_ready`
  - OpenClaw config JSON reload success
- Keep the validation vocabulary compact; do not build a mini rule engine.

**Step 4: Run tests to verify they pass**

Run:
```bash
python3.13 -m unittest tests.test_rescue_actions tests.test_rescue_flow -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/rescue_actions.py openclaw_watchdog/health.py openclaw_watchdog/flows/rescue_run.py tests/test_rescue_actions.py tests/test_rescue_flow.py
git commit -m "fix: tighten validation gates for mutating rescue plans"
```

---

## P1: Improve learning quality and shared operator state

### Task P1-1: Normalize learning signatures beyond exact failure matches

**Files:**
- Create: `openclaw_watchdog/learning_signatures.py`
- Modify: `openclaw_watchdog/engine.py`
- Modify: `openclaw_watchdog/learning.py`
- Modify: `openclaw_watchdog/rescue_policy.py`
- Test: `tests/test_learning.py`
- Test: `tests/test_rule_agent.py`

**Step 1: Write the failing tests**

Add tests for signature normalization:
- `tests/test_learning.py::test_similar_cases_match_normalized_signature_not_raw_summary_text`
- `tests/test_learning.py::test_recorded_case_persists_normalized_signature`
- `tests/test_rule_agent.py::test_rule_agent_prefers_cases_with_same_normalized_signature`

**Step 2: Run tests to verify they fail**

Run:
```bash
python3.13 -m unittest tests.test_learning tests.test_rule_agent -v
```
Expected: FAIL because the current store only matches exact `failure_signature` strings.

**Step 3: Write the minimal implementation**

- Introduce `normalized_failure_signature` built from stable fields such as config-invalid / process-down / service-layer / minimal / drift signals.
- Keep raw `failure_signature` for debugging, but match cases by normalized signature first.
- Update rule-agent recent-case lookup to use normalized evidence.

**Step 4: Run tests to verify they pass**

Run:
```bash
python3.13 -m unittest tests.test_learning tests.test_rule_agent -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/learning_signatures.py openclaw_watchdog/engine.py openclaw_watchdog/learning.py openclaw_watchdog/rescue_policy.py tests/test_learning.py tests/test_rule_agent.py
git commit -m "feat: normalize rescue learning signatures"
```

### Task P1-2: Add rule suppression and demotion lifecycle

**Files:**
- Modify: `openclaw_watchdog/learning.py`
- Modify: `openclaw_watchdog/rescue_agents/rule_agent.py`
- Modify: `openclaw_watchdog/rescue_policy.py`
- Test: `tests/test_learning.py`
- Test: `tests/test_rule_agent.py`

**Step 1: Write the failing tests**

Add tests for negative evidence:
- `tests/test_learning.py::test_rule_is_marked_pending_review_again_after_high_risk_failure_evidence`
- `tests/test_learning.py::test_rule_with_repeated_failed_outcomes_is_suppressed`
- `tests/test_rule_agent.py::test_rule_agent_skips_suppressed_rule_and_falls_back_to_static_heuristic`

**Step 2: Run tests to verify they fail**

Run:
```bash
python3.13 -m unittest tests.test_learning tests.test_rule_agent -v
```
Expected: FAIL because there is no demotion / suppression model yet.

**Step 3: Write the minimal implementation**

- Keep the current `cases / candidate-rules / rules / reviews` layout.
- Add negative evidence counters to promoted rules.
- Suppress a learned rule after a small bounded threshold of failed outcomes.
- Send high-risk regressions back to `reviews/` instead of leaving them permanently promoted.

**Step 4: Run tests to verify they pass**

Run:
```bash
python3.13 -m unittest tests.test_learning tests.test_rule_agent -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/learning.py openclaw_watchdog/rescue_agents/rule_agent.py openclaw_watchdog/rescue_policy.py tests/test_learning.py tests/test_rule_agent.py
git commit -m "feat: add learned rule suppression and demotion"
```

### Task P1-3: Introduce one shared operator snapshot for `status`, `report`, and `metrics`

**Files:**
- Create: `openclaw_watchdog/operator_snapshot.py`
- Modify: `openclaw_watchdog/health.py`
- Modify: `openclaw_watchdog/reporting.py`
- Modify: `openclaw_watchdog/presenters/status.py`
- Modify: `openclaw_watchdog/presenters/report.py`
- Test: `tests/test_reporting.py`
- Test: `tests/test_cli_json_contract.py`
- Test: `tests/test_cli_presenters.py`

**Step 1: Write the failing tests**

Add tests that force one shared snapshot contract:
- `tests/test_reporting.py::test_metrics_and_report_share_same_rescue_chain_fields`
- `tests/test_cli_json_contract.py::test_status_report_metrics_share_operator_snapshot_keys`
- `tests/test_cli_presenters.py::test_status_and_report_render_same_attempt_order_and_learning_summary`

**Step 2: Run tests to verify they fail**

Run:
```bash
python3.13 -m unittest tests.test_reporting tests.test_cli_json_contract tests.test_cli_presenters -v
```
Expected: FAIL because the shared snapshot module does not exist yet.

**Step 3: Write the minimal implementation**

- Create `OperatorSnapshot` as the normalized source for operator-facing rescue state.
- Have `status_payload()`, `report_payload()`, and `metrics_payload()` build on that snapshot instead of independently reshaping overlapping fields.
- Preserve the current public field names unless the tests explicitly change them.

**Step 4: Run tests to verify they pass**

Run:
```bash
python3.13 -m unittest tests.test_reporting tests.test_cli_json_contract tests.test_cli_presenters -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/operator_snapshot.py openclaw_watchdog/health.py openclaw_watchdog/reporting.py openclaw_watchdog/presenters/status.py openclaw_watchdog/presenters/report.py tests/test_reporting.py tests/test_cli_json_contract.py tests/test_cli_presenters.py
git commit -m "refactor: unify operator snapshot for status report metrics"
```

---

## P2: Expand rehearsal discipline and operator documentation

### Task P2-1: Split rehearsal coverage into critical and extended tiers

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_rehearsal_smoke_matrix.py`
- Modify: `rehearsal/scripts/run-scenario.sh`
- Modify: `rehearsal/README.md`
- Create: `rehearsal/scenarios/README.md`

**Step 1: Write the failing tests**

Add tests that enforce two tiers:
- `tests/test_rehearsal_smoke_matrix.py::test_ci_runs_only_critical_release_gate_scenarios`
- `tests/test_rehearsal_smoke_matrix.py::test_extended_scenarios_are_documented_but_not_required_in_ci`

**Step 2: Run tests to verify they fail**

Run:
```bash
python3.13 -m unittest tests.test_rehearsal_smoke_matrix -v
```
Expected: FAIL because the critical / extended split is not documented yet.

**Step 3: Write the minimal implementation**

- Keep current rescue-chain and rule-promotion scenarios in the critical set.
- Move lower-value or slower operator-flow scenarios into an extended set.
- Document the split so future contributors know what belongs in CI.

**Step 4: Run tests to verify they pass**

Run:
```bash
python3.13 -m unittest tests.test_rehearsal_smoke_matrix -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml tests/test_rehearsal_smoke_matrix.py rehearsal/scripts/run-scenario.sh rehearsal/README.md rehearsal/scenarios/README.md
git commit -m "test: split rehearsal scenarios into critical and extended tiers"
```

### Task P2-2: Add a rescue lifecycle guide for operators and contributors

**Files:**
- Create: `docs/rescue-lifecycle.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/internal-architecture.md`
- Modify: `docs/first-deployment.md`
- Modify: `docs/live-acceptance-checklist.md`

**Step 1: Write the failing test**

Add a doc regression test:
- `tests/test_reporting.py::test_docs_index_references_rescue_lifecycle_guide`

**Step 2: Run test to verify it fails**

Run:
```bash
python3.13 -m unittest tests.test_reporting -v
```
Expected: FAIL because the new guide does not exist yet.

**Step 3: Write the minimal implementation**

Document one end-to-end lifecycle:
- detect / check
- deterministic repair order
- rescue dispatch order
- local action execution boundary
- learning + candidate promotion
- operator-facing outputs to inspect during and after recovery

**Step 4: Run test to verify it passes**

Run:
```bash
python3.13 -m unittest tests.test_reporting -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/rescue-lifecycle.md README.md docs/README.md docs/internal-architecture.md docs/first-deployment.md docs/live-acceptance-checklist.md tests/test_reporting.py
git commit -m "docs: add rescue lifecycle guide"
```

---

## Final validation task

### Task Final-1: Run the complete validation stack after P0/P1/P2

**Files:**
- Modify only if verification finds real issues.

**Step 1: Run focused suites from completed tasks**

Run the task-specific `python3.13 -m unittest ... -v` commands listed above.

**Step 2: Run the full unittest suite**

Run:
```bash
python3.13 -m unittest discover -s tests -v
```
Expected: PASS.

**Step 3: Run critical rehearsal scenarios**

Run:
```bash
bash rehearsal/scripts/run-scenario.sh bootstrap-missing-openclaw
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-codex
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-claude-code
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-gemini-cli
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-opencode
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-litellm
bash rehearsal/scripts/run-scenario.sh watchdog-rescue-chain-rule-agent
bash rehearsal/scripts/run-scenario.sh watchdog-candidate-rule-auto-promotion
bash rehearsal/scripts/run-scenario.sh watchdog-candidate-rule-review-pending
```
Expected: PASS.

**Step 4: Verify docs and CI stayed aligned**

Check these files together:
- `README.md`
- `docs/README.md`
- `docs/internal-architecture.md`
- `docs/supported-environments.md`
- `.github/workflows/ci.yml`

**Step 5: Final commit or handoff summary**

If implemented in one batch:
```bash
git status
git --no-pager log --oneline -10
```
Summarize what changed, what passed, and any intentionally deferred items.

---

## Deferred items after this roadmap

These are intentionally out of scope for this round:

- introducing mypy / ruff / new external tooling into the repo;
- redesigning incident management into a separate product surface;
- replacing JSON-file learning storage with a database;
- renaming `openclaw_watchdog` to another package name;
- adding new rescue executors before the current ones are structurally stabilized.
