# OpenClaw Specialized Rescue Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove compatibility-era fallback residue, eliminate auto-install behavior, and harden the rescue chain into a single OpenClaw-specialized recovery system.

**Architecture:** The implementation keeps one rescue-first orchestration path and one local action-execution boundary. External CLIs and the LiteLLM specialist produce structured rescue plans only; all host mutation stays inside the local white-listed action executor. Learning is widened from successful agent rescue only to successful recovery outcomes across deterministic, specialist, and offline tiers.

**Tech Stack:** Python 3.11+, standard library, `unittest`, repo-local rehearsal harness.

---

### Task 1: Remove bootstrap auto-install surface

**Files:**
- Modify: `watchdog_v2/cli.py`
- Modify: `watchdog_v2/bootstrap.py`
- Modify: `watchdog_v2/bootstrap_steps.py`
- Modify: `watchdog_v2/config.py`
- Modify: `watchdog_v2/detect.py`
- Modify: `tests/test_cli_smoke.py`
- Modify: `tests/test_bootstrap_steps.py`
- Modify: `tests/test_config.py`
- Modify: `README.md`
- Modify: `docs/supported-environments.md`
- Modify: `rehearsal/README.md`
- Modify: `rehearsal/scripts/run-scenario.sh`

**Steps:**
1. Write failing tests asserting bootstrap no longer exposes install flags or install-command guidance.
2. Remove dead bootstrap install entrypoints and config/env fields that imply automatic rescue-tool installation.
3. Update detect/bootstrap docs and rehearsal references to describe detect-only inventory plus manual prerequisite setup.
4. Run focused bootstrap/CLI/config tests.

### Task 2: Remove legacy Codex/OpenCode handoff side path

**Files:**
- Modify: `watchdog_v2/run_context.py`
- Modify: `watchdog_v2/engine.py`
- Modify: `watchdog_v2/events.py`
- Modify: `watchdog_v2/incidents.py`
- Modify: `watchdog_v2/incident_context.py`
- Modify: `tests/test_events.py`
- Modify: `tests/test_incident_context.py`
- Modify: `tests/test_cli_json_contract.py`
- Modify: `tests/test_reporting.py`
- Delete or simplify: `watchdog_v2/handoff.py`

**Steps:**
1. Write failing tests asserting runtime/event/incident payloads no longer expose codex autorun or opencode fallback handoff fields.
2. Remove unused incident handoff artifacts and old autorun trigger plumbing from runtime state and event shaping.
3. Keep incident evidence collection only if still used; otherwise collapse the whole obsolete module surface.
4. Run focused incident/reporting/event tests.

### Task 3: Tighten rescue plan contract to executable actions only

**Files:**
- Modify: `watchdog_v2/rescue_models.py`
- Modify: `watchdog_v2/rescue_actions.py`
- Modify: `watchdog_v2/rescue_agents/base.py`
- Modify: `tests/test_rescue_models.py`
- Modify: `tests/test_rescue_actions.py`
- Modify: `tests/test_cli_rescue_adapters.py`

**Steps:**
1. Write failing tests proving unsupported-but-declared actions are rejected.
2. Reduce the allowed action surface to actions with concrete executor support, or implement the missing actions with tests.
3. Ensure adapters reject plans that depend on unavailable mutations.
4. Run focused rescue contract tests.

### Task 4: Introduce OpenClaw rescue policy and richer specialist context

**Files:**
- Create: `watchdog_v2/rescue_policy.py`
- Modify: `watchdog_v2/engine.py`
- Modify: `watchdog_v2/rescue_agents/litellm_agent.py`
- Modify: `watchdog_v2/rescue_agents/rule_agent.py`
- Modify: `tests/test_litellm_agent.py`
- Modify: `tests/test_rule_agent.py`

**Steps:**
1. Write failing tests for richer payloads and OpenClaw-specific heuristic fallback behavior.
2. Centralize editable-key policy, minimal channel policy, and failure-signature shaping in one module.
3. Feed LiteLLM the compact OpenClaw policy/context summary and teach the offline rule-agent to combine promoted rules with static heuristics.
4. Run focused specialist-agent tests.

### Task 5: Expand learning to all successful recovery outcomes

**Files:**
- Modify: `watchdog_v2/flows/rescue_run.py`
- Modify: `watchdog_v2/engine.py`
- Modify: `watchdog_v2/learning.py`
- Modify: `tests/test_learning.py`
- Modify: `tests/test_rescue_flow.py`

**Steps:**
1. Write failing tests for deterministic recovery learning records and richer promotion metadata.
2. Record successful deterministic and rescue-tier recoveries into a common case format.
3. Add promotion metadata such as evidence counts, timestamps, mutation scope, and confidence summary.
4. Run focused learning/flow tests.

### Task 6: Strengthen reporting and docs around the unified rescue chain

**Files:**
- Modify: `watchdog_v2/reporting.py`
- Modify: `watchdog_v2/presenters/status.py`
- Modify: `watchdog_v2/presenters/report.py`
- Modify: `tests/test_cli_presenters.py`
- Modify: `tests/test_reporting.py`
- Modify: `docs/internal-architecture.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/README.md`
- Modify: `docs/compatibility-and-deprecations.md`

**Steps:**
1. Write failing tests for the new rescue observability fields and removal of legacy handoff wording.
2. Surface attempt order, rejected executors, learning result, and mutation summary in operator-facing status/report outputs.
3. Rewrite docs to present the project as an OpenClaw-specific rescue orchestrator with historical compatibility notes pushed to background context only.
4. Run focused presenter/reporting tests.

### Task 7: Final validation

**Files:**
- Modify as needed based on verification findings only.

**Steps:**
1. Run focused test groups after each task.
2. Run rehearsal smoke coverage for critical rescue-chain scenarios.
3. Run `python3.13 -m unittest discover -s tests -v`.
4. Update the plan/task status summary in the final handoff.
