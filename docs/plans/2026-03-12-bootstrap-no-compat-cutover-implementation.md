# Bootstrap And No-Compatibility Cutover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the project into a single-name OpenClaw watchdog package with a read-only bootstrap surface, no legacy naming, and no compatibility layers.

**Architecture:** First cut the package and public surface over to `openclaw_watchdog` so all later refactors land on the final identity. Then shrink `bootstrap` into a pure readiness inspector, extract shared executor metadata into one registry, and rewire `engine` plus rescue context building to use that single source of truth.

**Tech Stack:** Python 3.11+, stdlib `argparse`/`pathlib`/`json`/`unittest`, setuptools console scripts, shell wrappers, existing rehearsal harness.

---

### Task 1: Cut over package and entrypoints to `openclaw_watchdog`

**Files:**
- Create: `openclaw_watchdog/` as the canonical package root
- Modify: `pyproject.toml`
- Modify: `scripts/openclaw-watchdog`
- Modify: `README.md`
- Modify: `docs/internal-architecture.md`
- Modify: `docs/rescue-lifecycle.md`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_runtime_wrapper.py`

**Step 1: Write the failing tests**

Update imports and wrapper expectations so tests require the new package/module path:

```python
from openclaw_watchdog.cli import build_parser
```

```python
self.assertIn('python3.11 -m openclaw_watchdog --help', stderr)
```

**Step 2: Run focused tests to verify they fail**

Run: `python3.13 -m unittest tests.test_cli_smoke tests.test_runtime_wrapper -q`
Expected: FAIL with `ModuleNotFoundError` or old wrapper expectation mismatch.

**Step 3: Write the minimal implementation**

- Cut the package over to `openclaw_watchdog/`
- Change the console script entrypoint to `openclaw_watchdog.cli:main`
- Update `scripts/openclaw-watchdog` to execute `python -m openclaw_watchdog`
- Replace documentation references that say the internal package intentionally remains `openclaw_watchdog`

**Step 4: Run focused tests to verify they pass**

Run: `python3.13 -m unittest tests.test_cli_smoke tests.test_runtime_wrapper -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml scripts/openclaw-watchdog README.md docs/internal-architecture.md docs/rescue-lifecycle.md openclaw_watchdog tests/test_cli_smoke.py tests/test_runtime_wrapper.py
git commit -m "refactor: rename package to openclaw_watchdog"
```

### Task 2: Remove compatibility shims and legacy naming surfaces

**Files:**
- Delete or move to history: `docs/compatibility-and-deprecations.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/history/migration-legacy-rollout.md` (rename content and references)
- Modify: `openclaw_watchdog/config.py`
- Modify: `openclaw_watchdog/repair.py`
- Test: `tests/test_config.py`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_rescue_models.py`

**Step 1: Write the failing tests**

Add assertions that the repo no longer exposes deprecated names and no longer advertises compatibility behavior:

```python
self.assertNotIn('legacy wrapper', readme_text)
self.assertEqual(default_env_file().name, 'openclaw-watchdog.env')
```

**Step 2: Run focused tests to verify they fail**

Run: `python3.13 -m unittest tests.test_config tests.test_cli_smoke tests.test_rescue_models -q`
Expected: FAIL because docs/scripts/config logic still reference deprecated paths or legacy strings.

**Step 3: Write the minimal implementation**

- Delete all legacy shim scripts
- Remove compatibility/deprecation guidance from current docs
- Rename migration notes to a neutral historical filename if kept
- Simplify `default_env_file()` so it returns only the canonical path
- Remove `repair.py` fallback text and behavior that depends on legacy single-file snapshot semantics

**Step 4: Run focused tests to verify they pass**

Run: `python3.13 -m unittest tests.test_config tests.test_cli_smoke tests.test_rescue_models -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy naming and compatibility shims"
```

### Task 3: Redefine `bootstrap` as a read-only readiness inspector

**Files:**
- Modify: `openclaw_watchdog/cli.py`
- Modify: `openclaw_watchdog/bootstrap.py`
- Modify: `openclaw_watchdog/bootstrap_steps.py`
- Modify: `openclaw_watchdog/models.py`
- Modify: `openclaw_watchdog/presenters/bootstrap.py`
- Modify: `README.md`
- Modify: `docs/first-deployment.md`
- Modify: `docs/rescue-lifecycle.md`
- Test: `tests/test_bootstrap_steps.py`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_cli_json_contract.py`

**Step 1: Write the failing tests**

Change tests so `bootstrap` no longer exposes provisioning semantics:

```python
self.assertNotIn('provision', subparsers_action.choices)
self.assertNotIn('--dry-run', bootstrap_help)
self.assertEqual(result.state, 'attention')
```

for cases where OpenClaw or required prerequisites are missing.

**Step 2: Run focused tests to verify they fail**

Run: `python3.13 -m unittest tests.test_bootstrap_steps tests.test_cli_smoke tests.test_cli_json_contract -q`
Expected: FAIL because CLI still exposes `provision` / `--dry-run`, and bootstrap still returns the old `ready`/`dry-run` style state.

**Step 3: Write the minimal implementation**

- Remove `provision` alias and `--dry-run`
- Change help text from “provision/scaffold” to “inspect rescue prerequisites”
- Replace `ready` + warning behavior with explicit states such as `ready`, `attention`, `failed`
- Ensure missing OpenClaw, missing QQ plugin, unresolved placeholders, or missing executor prerequisites produce `attention`
- Update docs so bootstrap is clearly detect-only and non-mutating

**Step 4: Run focused tests to verify they pass**

Run: `python3.13 -m unittest tests.test_bootstrap_steps tests.test_cli_smoke tests.test_cli_json_contract -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/cli.py openclaw_watchdog/bootstrap.py openclaw_watchdog/bootstrap_steps.py openclaw_watchdog/models.py openclaw_watchdog/presenters/bootstrap.py README.md docs/first-deployment.md docs/rescue-lifecycle.md tests/test_bootstrap_steps.py tests/test_cli_smoke.py tests/test_cli_json_contract.py
git commit -m "refactor: make bootstrap a read-only readiness inspector"
```

### Task 4: Remove bootstrap write-path logic and shrink `BootstrapSummary`

**Files:**
- Modify: `openclaw_watchdog/bootstrap.py`
- Modify: `openclaw_watchdog/models.py`
- Modify: `openclaw_watchdog/presenters/bootstrap.py`
- Test: `tests/test_bootstrap_steps.py`
- Test: `tests/test_cli_presenters.py`

**Step 1: Write the failing tests**

Require bootstrap payloads to exclude write-only fields:

```python
self.assertNotIn('files_changed', outcome.payload)
self.assertNotIn('backup_files', outcome.payload)
self.assertNotIn('dry_run', outcome.payload)
```

**Step 2: Run focused tests to verify they fail**

Run: `python3.13 -m unittest tests.test_bootstrap_steps tests.test_cli_presenters -q`
Expected: FAIL because payload and presenter still include write-path state.

**Step 3: Write the minimal implementation**

- Delete `ensure_opencode_config`, `ensure_qq_plugin`, `ensure_default_channel_config`, backup-path helpers, and any no-longer-used write helpers
- Remove `files_changed`, `backup_files`, and `dry_run` from `BootstrapSummary`
- Keep only inventory / inspection / warning / next-step fields
- Simplify presenter output to show availability and attention items only

**Step 4: Run focused tests to verify they pass**

Run: `python3.13 -m unittest tests.test_bootstrap_steps tests.test_cli_presenters -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/bootstrap.py openclaw_watchdog/models.py openclaw_watchdog/presenters/bootstrap.py tests/test_bootstrap_steps.py tests/test_cli_presenters.py
git commit -m "refactor: remove bootstrap write paths"
```

### Task 5: Extract executor registry and shared detection helpers

**Files:**
- Create: `openclaw_watchdog/executor_registry.py`
- Create: `openclaw_watchdog/bootstrap_inventory.py`
- Create: `openclaw_watchdog/bootstrap_inspectors.py`
- Modify: `openclaw_watchdog/bootstrap.py`
- Modify: `openclaw_watchdog/bootstrap_steps.py`
- Modify: `openclaw_watchdog/rescue_context_builder.py`
- Modify: `openclaw_watchdog/engine.py`
- Test: `tests/test_bootstrap_steps.py`
- Test: `tests/test_rescue_flow.py`
- Test: `tests/test_cli_rescue_adapters.py`

**Step 1: Write the failing tests**

Add assertions that one canonical executor order is used everywhere:

```python
self.assertEqual(summary.executors_order, ['codex', 'claude-code', 'gemini-cli', 'opencode', 'litellm', 'rule-agent'])
self.assertEqual(context.available_executors, ('codex', 'opencode', 'rule-agent'))
```

with inputs driven from one shared registry fixture.

**Step 2: Run focused tests to verify they fail**

Run: `python3.13 -m unittest tests.test_bootstrap_steps tests.test_rescue_flow tests.test_cli_rescue_adapters -q`
Expected: FAIL because executor metadata is still duplicated across bootstrap, engine, and rescue context builder.

**Step 3: Write the minimal implementation**

- Move executor display names, canonical order, binary candidates, config key names, and availability rules into `executor_registry.py`
- Move bootstrap binary probing into `bootstrap_inventory.py`
- Move QQ/Feishu/OpenClaw config inspection into `bootstrap_inspectors.py`
- Rewire `bootstrap.py` into a thin façade over those helpers
- Rewire `rescue_context_builder.py` and `engine.py` to ask the registry for priority, command resolution, and availability

**Step 4: Run focused tests to verify they pass**

Run: `python3.13 -m unittest tests.test_bootstrap_steps tests.test_rescue_flow tests.test_cli_rescue_adapters -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/executor_registry.py openclaw_watchdog/bootstrap_inventory.py openclaw_watchdog/bootstrap_inspectors.py openclaw_watchdog/bootstrap.py openclaw_watchdog/bootstrap_steps.py openclaw_watchdog/rescue_context_builder.py openclaw_watchdog/engine.py tests/test_bootstrap_steps.py tests/test_rescue_flow.py tests/test_cli_rescue_adapters.py
git commit -m "refactor: unify executor inventory and bootstrap helpers"
```

### Task 6: Add executor-specific config keys and final contract validation

**Files:**
- Modify: `openclaw_watchdog/config.py`
- Modify: `config/openclaw-watchdog.env.example`
- Modify: `openclaw_watchdog/engine.py`
- Modify: `openclaw_watchdog/rescue_context_builder.py`
- Modify: `README.md`
- Modify: `docs/reporting-contract.md`
- Test: `tests/test_config.py`
- Test: `tests/test_rescue_flow.py`
- Test: `tests/test_litellm_agent.py`
- Verify: `rehearsal/scripts/run-scenario.sh`

**Step 1: Write the failing tests**

Require dedicated config for each external executor and no reuse of Codex settings for Claude/Gemini:

```python
self.assertEqual(config.watchdog_claude_code_timeout_seconds, 1800)
self.assertEqual(config.watchdog_gemini_cli_timeout_seconds, 1800)
self.assertNotEqual(engine._rescue_command('claude-code'), engine._rescue_command('codex'))
```

**Step 2: Run focused tests to verify they fail**

Run: `python3.13 -m unittest tests.test_config tests.test_rescue_flow tests.test_litellm_agent -q`
Expected: FAIL because config still shares Codex-specific knobs and old OpenCode fallback names.

**Step 3: Write the minimal implementation**

- Add dedicated config/env fields for `claude-code`, `gemini-cli`, and canonical `opencode`
- Rename `WATCHDOG_OPENCODE_FALLBACK_*` to `WATCHDOG_OPENCODE_*`
- Update executor registry, engine wiring, docs, and sample env to use the canonical names
- Keep rescue-chain contract `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`

**Step 4: Run focused tests and final verification**

Run: `python3.13 -m unittest tests.test_config tests.test_rescue_flow tests.test_litellm_agent -q`
Expected: PASS.

Run: `python3.13 -m unittest discover -s tests -q`
Expected: PASS.

Run: `bash rehearsal/scripts/run-scenario.sh critical`
Expected: all critical scenarios pass.

**Step 5: Commit**

```bash
git add openclaw_watchdog/config.py config/openclaw-watchdog.env.example openclaw_watchdog/engine.py openclaw_watchdog/rescue_context_builder.py README.md docs/reporting-contract.md tests/test_config.py tests/test_rescue_flow.py tests/test_litellm_agent.py
git commit -m "refactor: finalize executor config and no-compat bootstrap contract"
```

## Notes for execution

- Do not preserve import, CLI, or script compatibility for `openclaw_watchdog` or `openclaw-watchdog`.
- Do not add any installer flow back into `bootstrap`; it must stay detect-only.
- Keep all host mutation inside the local rescue action executor boundary.
- Prefer relative imports inside `openclaw_watchdog/` while renaming to reduce churn.
