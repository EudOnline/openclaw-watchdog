# OpenClaw Watchdog Stabilization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise OpenClaw Watchdog from a strong personal/team operations tool into a more trustworthy open-source recovery project by fixing runtime friction, adding automated verification, removing doc drift, and reducing maintenance hotspots.

**Architecture:** Deliver the work in three weekly waves. Week 1 makes the project reliably runnable and automatically checked. Week 2 aligns docs/config semantics and creates a safer onboarding path. Week 3 reduces long-term maintenance cost by splitting orchestration responsibilities and adding focused regression coverage around the most failure-prone flows.

**Tech Stack:** Python 3.11+, `argparse`, GitHub Actions, shell wrappers, existing rehearsal harness, existing `openclaw_watchdog` package.

---

## Recommended approach

### Option A: Reliability-first hardening (recommended)

Start with runtime correctness, CI, and documentation consistency before touching deeper refactors. This gives the fastest trust improvement for both maintainers and outside users.

**Why this is recommended:** the current repo already has strong product shape and docs, but it is still vulnerable to first-run friction (`python3` version mismatch), missing automation, and documentation drift. Fixing those first improves both day-1 usability and confidence in future changes.

### Option B: Refactor-first cleanup

Start by splitting `openclaw_watchdog/engine.py` and `openclaw_watchdog/cli.py`, then circle back to CI and docs. This improves code health quickly, but it delays fixes for the issues most likely to block real users.

### Option C: Feature-first expansion

Add more providers, notification channels, or fallback behaviors first. This creates more visible functionality, but it amplifies complexity before the project’s verification and packaging story are stable.

---

## Delivery rhythm

- **Week 1:** Runtime + CI + smoke verification
- **Week 2:** Docs/config alignment + first-deployment clarity
- **Week 3:** Refactor hotspots + targeted regression coverage

Success at the end of the three weeks means:
- a fresh user can run the documented commands without Python-version confusion;
- every PR gets at least basic automated checks;
- documentation matches the actual repository contents;
- core recovery/reporting/config flows have stable regression coverage;
- the orchestration layer is thinner and easier to extend safely.

---

### Task 1: Fix runtime entrypoint and Python-version detection

**Files:**
- Modify: `scripts/openclaw-watchdog`
- Modify: `README.md`
- Modify: `docs/first-deployment.md`
- Modify: `docs/faq.md`
- Verify against: `pyproject.toml`

**Week:** 1

**Step 1: Reproduce the current failure**

Run: `./scripts/openclaw-watchdog --help`
Expected: on machines where `python3` is below 3.11, fail with an import/runtime error rather than a friendly requirement message.

**Step 2: Add explicit interpreter/version handling**

Implement a wrapper strategy in `scripts/openclaw-watchdog` that prefers a compatible interpreter and exits with a clear message when only Python < 3.11 is available.

Recommended acceptance behavior:
- if `python3.11` exists, use it;
- else if `python3` is 3.11+, use it;
- else exit non-zero with a short upgrade/install hint.

**Step 3: Update install/run docs**

Document the exact expectation in `README.md`, `docs/first-deployment.md`, and `docs/faq.md` so users know the supported version is Python 3.11+ and the wrapper checks it.

**Step 4: Re-run the smoke check**

Run: `./scripts/openclaw-watchdog --help`
Expected: help text prints successfully on a supported interpreter, or a clean requirement message prints on an unsupported interpreter.

**Step 5: Commit**

```bash
git add scripts/openclaw-watchdog README.md docs/first-deployment.md docs/faq.md
git commit -m "fix: enforce supported python runtime"
```

---

### Task 2: Add minimal CI for confidence on every change

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`
- Verify with: `rehearsal/README.md`
- Verify with: `scripts/openclaw-watchdog`

**Week:** 1

**Step 1: Define the minimum CI matrix**

Use one Linux workflow that installs Python 3.11 and runs the smallest high-signal checks first.

Recommended checks:
- `python3.11 -m openclaw_watchdog --help`
- `python3.11 -m py_compile openclaw_watchdog/*.py rehearsal/lib/*.py rehearsal/tools/*.py`
- one or two fast rehearsal scenarios that do not depend on missing Docker assets

**Step 2: Create the workflow**

Add `.github/workflows/ci.yml` with PR/push triggers, checkout, Python setup, and the commands above.

**Step 3: Document the status signal**

Add a short CI note or badge reference in `README.md` once the workflow exists.

**Step 4: Validate locally as far as possible**

Run the same commands locally using a 3.11 interpreter if available. If 3.11 is unavailable locally, at minimum validate the workflow YAML syntax and the commands individually where possible.

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "ci: add basic verification workflow"
```

---

### Task 3: Repair documentation drift in the rehearsal story

**Files:**
- Modify: `rehearsal/README.md`
- Modify: `docs/README.md`
- Modify: `README.md`

**Week:** 1

**Step 1: Diff docs against repository contents**

Check whether files referenced by `rehearsal/README.md` actually exist.

Run: `ls Dockerfile compose.yaml`
Expected: today these are missing in the current checkout.

**Step 2: Choose the smallest truthful fix**

Either:
- remove Docker/Compose claims from `rehearsal/README.md`, or
- add the missing assets if you intend to support that path immediately.

Recommended choice: remove or mark the claims as historical unless you are ready to maintain Docker assets right now.

**Step 3: Align higher-level docs**

Update `docs/README.md` and `README.md` if they imply a containerized rehearsal path that no longer exists.

**Step 4: Verify docs by following them literally**

Walk through each documented rehearsal start path and confirm it maps to files that are present in the repo.

**Step 5: Commit**

```bash
git add rehearsal/README.md docs/README.md README.md
git commit -m "docs: remove rehearsal documentation drift"
```

---

### Task 4: Align config defaults, sample env, and operator expectations

**Files:**
- Modify: `openclaw_watchdog/config.py`
- Modify: `config/openclaw-watchdog.env.example`
- Modify: `README.md`
- Modify: `docs/first-deployment.md`
- Modify: `docs/compatibility-and-deprecations.md`

**Week:** 2

**Step 1: Inventory mismatched defaults**

Compare `openclaw_watchdog/config.py` defaults against `config/openclaw-watchdog.env.example`.

Known examples to verify:
- `WATCHDOG_ENABLE_PRE_REPAIR_BACKUP`
- `WATCHDOG_ENABLE_CODEX_AUTORUN`
- backup script/env fallback paths

**Step 2: Decide the source-of-truth policy**

Recommended policy:
- code defaults should be conservative and safe for unattended execution;
- the sample env should explicitly override defaults only when the safer first rollout requires it;
- docs should state when the sample env intentionally differs from internal defaults.

**Step 3: Apply one consistent policy**

Either unify the values or clearly document the intended divergence. Avoid a state where users cannot tell whether a behavior is “default” or “sample override.”

**Step 4: Verify config loading behavior**

Run focused checks that print or inspect loaded config under:
- no env file present;
- sample env file present;
- explicit `--env` path present.

**Step 5: Commit**

```bash
git add openclaw_watchdog/config.py config/openclaw-watchdog.env.example README.md docs/first-deployment.md docs/compatibility-and-deprecations.md
git commit -m "docs: align config defaults and sample env semantics"
```

---

### Task 5: Publish a true first-deployment path

**Files:**
- Modify: `docs/first-deployment.md`
- Modify: `README.md`
- Modify: `docs/faq.md`
- Verify with: `config/openclaw-watchdog.env.example`
- Verify with: `scripts/install-openclaw-watchdog-units.sh`

**Week:** 2

**Step 1: Define a “minimum safe rollout”**

Recommended sections:
- prerequisites;
- copy sample env;
- disable risky automation for first run;
- run `detect`;
- run `check`;
- inspect `status --summary` and `report`;
- only then enable timer/service.

**Step 2: Add a short operator checklist**

Document which settings are required, which are recommended, and which should stay off for the first live deployment.

**Step 3: Cross-link from top-level docs**

Update `README.md` and `docs/faq.md` so the new-user path is obvious.

**Step 4: Dry-run the guide literally**

Read the guide as if you are a first-time user and confirm every referenced file and command exists.

**Step 5: Commit**

```bash
git add docs/first-deployment.md README.md docs/faq.md
git commit -m "docs: clarify minimal production rollout path"
```

---

### Task 6: Add focused regression coverage around config and reporting

**Files:**
- Create: `tests/test_config.py`
- Create: `tests/test_reporting.py`
- Create: `tests/test_cli_smoke.py`
- Modify: `pyproject.toml`
- Verify with: `openclaw_watchdog/config.py`
- Verify with: `openclaw_watchdog/reporting.py`
- Verify with: `openclaw_watchdog/cli.py`

**Week:** 2

**Step 1: Write the failing tests**

Add tests for:
- env parsing and boolean/int/path coercion;
- report/metrics payload stability for representative fields;
- CLI parser smoke checks for key commands.

**Step 2: Run tests to verify they fail for missing harness or assertions**

Run: `pytest tests/test_config.py tests/test_reporting.py tests/test_cli_smoke.py -v`
Expected: initial failures until fixtures/helpers are in place.

**Step 3: Add minimal harness support**

Only add the smallest pytest configuration needed in `pyproject.toml` or local fixtures. Do not overbuild a large testing framework.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py tests/test_reporting.py tests/test_cli_smoke.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_config.py tests/test_reporting.py tests/test_cli_smoke.py pyproject.toml
git commit -m "test: add focused config and reporting coverage"
```

---

### Task 7: Thin the orchestration layer in `engine.py`

**Files:**
- Modify: `openclaw_watchdog/engine.py`
- Create: `openclaw_watchdog/runtime.py`
- Create: `openclaw_watchdog/state_store.py`
- Verify with: `openclaw_watchdog/incidents.py`
- Verify with: `openclaw_watchdog/reporting.py`
- Verify with: `openclaw_watchdog/repair.py`

**Week:** 3

**Step 1: Identify responsibilities to extract first**

Recommended first split:
- shell/subprocess execution and file capture helpers → `openclaw_watchdog/runtime.py`
- run-state/event-history persistence helpers → `openclaw_watchdog/state_store.py`

Keep recovery decision logic in `engine.py` during the first refactor.

**Step 2: Write failing regression tests for preserved behavior**

Add or extend tests to lock down:
- event history writing;
- run-state writing;
- command result shaping;
- listener/service helper behavior where feasible with stubs.

**Step 3: Move one responsibility at a time**

Refactor incrementally. After each extraction, rerun the focused test set before moving the next responsibility.

**Step 4: Run focused verification**

Run: `pytest tests/test_config.py tests/test_reporting.py tests/test_cli_smoke.py -v`
Then run the highest-signal rehearsal scenarios you rely on for regressions.

**Step 5: Commit**

```bash
git add openclaw_watchdog/engine.py openclaw_watchdog/runtime.py openclaw_watchdog/state_store.py tests/
git commit -m "refactor: extract runtime and state helpers from engine"
```

---

### Task 8: Stabilize CLI surface and operator quick path

**Files:**
- Modify: `openclaw_watchdog/cli.py`
- Modify: `README.md`
- Modify: `docs/faq.md`
- Modify: `docs/live-acceptance-checklist.md`

**Week:** 3

**Step 1: Identify the “operator quick path” commands**

Recommended quick path:
- `detect`
- `check`
- `status --summary`
- `report --message`
- `incidents queue`
- `maintenance on|off`

**Step 2: Improve help text and grouping**

Tighten parser help text so first-time operators can see the common path without reading every advanced subcommand first.

**Step 3: Align docs to the quick path**

Update README and operator docs so the main path is short, while advanced incident workflow remains available.

**Step 4: Verify help output**

Run: `./scripts/openclaw-watchdog --help`
Run: `./scripts/openclaw-watchdog incidents --help`
Expected: top-level help is more scannable and advanced controls remain discoverable.

**Step 5: Commit**

```bash
git add openclaw_watchdog/cli.py README.md docs/faq.md docs/live-acceptance-checklist.md
git commit -m "docs: highlight operator quick path in cli and docs"
```

---

### Task 9: Add schema-stability notes for reports and metrics

**Files:**
- Modify: `openclaw_watchdog/reporting.py`
- Create: `docs/reporting-contract.md`
- Modify: `README.md`
- Modify: `docs/README.md`

**Week:** 3

**Step 1: Decide the public contract level**

Recommended contract:
- stable top-level keys for `report --json` and `metrics --json` within minor releases;
- additive changes preferred;
- removals/renames documented in changelog and compatibility docs.

**Step 2: Document the contract**

Create `docs/reporting-contract.md` with example payload fragments and compatibility promises.

**Step 3: Reflect the contract in code comments or shaping helpers**

Keep changes minimal; the main goal is to make future edits deliberate and reviewable.

**Step 4: Verify against acceptance docs**

Ensure `docs/live-acceptance-checklist.md` and the new contract doc agree on the important keys.

**Step 5: Commit**

```bash
git add openclaw_watchdog/reporting.py docs/reporting-contract.md README.md docs/README.md
 git commit -m "docs: define report and metrics compatibility contract"
```

---

### Task 10: Close the loop with release notes and contributor guidance

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `CONTRIBUTING.md`
- Modify: `README.md`
- Verify with: `.github/pull_request_template.md`

**Week:** 3

**Step 1: Update contributor expectations**

Document the new baseline:
- supported Python version handling;
- CI requirements;
- doc-truth rule;
- preferred verification commands before PRs.

**Step 2: Update release notes**

Record the runtime, CI, docs, and compatibility improvements in `CHANGELOG.md`.

**Step 3: Verify contribution flow**

Read `CONTRIBUTING.md` and `.github/pull_request_template.md` together and make sure they ask contributors for the same evidence.

**Step 4: Final verification**

Run the full validation set chosen for this hardening effort and capture the commands in the docs.

**Step 5: Commit**

```bash
git add CHANGELOG.md CONTRIBUTING.md README.md .github/pull_request_template.md
git commit -m "docs: align contributor and release guidance with hardening work"
```

---

## Verification ladder

Run these from smallest to broadest after each task cluster:

1. `./scripts/openclaw-watchdog --help`
2. `./scripts/openclaw-watchdog detect --help`
3. `./scripts/openclaw-watchdog incidents --help`
4. `python3.11 -m py_compile openclaw_watchdog/*.py rehearsal/lib/*.py rehearsal/tools/*.py`
5. `pytest tests/test_config.py tests/test_reporting.py tests/test_cli_smoke.py -v`
6. Selected rehearsal scenario commands that match changed behavior

If any broader step fails, stop and fix before continuing.

---

## Suggested schedule summary

- **Week 1 output:** project is runnable, CI exists, docs stop lying
- **Week 2 output:** onboarding is safer, config semantics are understandable, fast tests exist
- **Week 3 output:** codebase is easier to extend, CLI is easier to approach, compatibility expectations are explicit

## Stop conditions

Pause the plan and re-scope if any of these happen:
- adding pytest coverage requires a large invasive harness rather than a minimal setup;
- `engine.py` extraction starts changing recovery behavior rather than just moving responsibilities;
- missing Docker assets turn out to be intentionally unpublished and restoring them becomes a separate project.
