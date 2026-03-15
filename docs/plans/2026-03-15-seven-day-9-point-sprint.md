# 7-Day 9-Point Sprint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the repository from its current `8.6/10` state to a `9.0+` release-ready state by closing the remaining release-proof, quality-gate, and operator-trust gaps around `v0.2.0`.

**Architecture:** Treat the current `main` branch as the verified baseline: repo-local tests, critical rehearsal, release-readiness docs, and the `v0.2.0` metadata are already in place. This sprint should not invent a new product surface. It should finish the last-mile release workflow, tighten the highest-value verification layers, and flip the repository surface from "planned next release" to "latest published release" only after real-host evidence exists.

**Tech Stack:** Python 3.11 and 3.13, stdlib `unittest`, GitHub Actions, `ruff`, `mypy`, Markdown docs, Git tags, GitHub Releases, Linux + `systemd --user`, repo-local rehearsal harness.

---

### Task 1: Day 1 - Lock the release candidate baseline and host checklist

**Files:**
- Review: `README.md`
- Review: `docs/release-readiness.md`
- Review: `docs/release-v0.2.0-runbook.md`
- Review: `docs/release-notes-v0.2.0-draft.md`
- Review: `config/openclaw-watchdog.env.example`
- Review: `scripts/openclaw-watchdog-live-acceptance.sh`

**Step 1: Confirm the branch state is clean**

Run:

```bash
git status --short
git branch --show-current
git rev-parse --short HEAD
```

Expected: clean worktree on `main`, with the intended release-prep commit checked out.

**Step 2: Re-run the repo-local release gate**

Run:

```bash
python3 -m unittest discover -s tests -q
bash rehearsal/scripts/run-scenario.sh critical
```

Expected: PASS. Do not continue the sprint if either command fails.

**Step 3: Review the host rollout assumptions**

Read the conservative rollout toggles and required host assumptions from:

- `docs/release-readiness.md`
- `docs/release-v0.2.0-runbook.md`
- `config/openclaw-watchdog.env.example`

Expected outcome: one concrete target host is selected, and it is already compatible with Linux + `systemd --user` and has OpenClaw installed.

**Step 4: Prepare the host execution checklist**

Create a local operator checklist outside the repo issue tracker or release ticket that contains:

- the real host name;
- who will run the commands;
- where `docs/p7a-live/` artifacts will be copied from;
- rollback owner if live acceptance fails.

Expected outcome: the release no longer depends on memory or ad-hoc coordination.

**Step 5: Commit only if repo changes were needed**

```bash
git add README.md docs/release-readiness.md docs/release-v0.2.0-runbook.md docs/release-notes-v0.2.0-draft.md
git commit -m "docs: tighten v0.2.0 host release checklist"
```

If no repo files changed, do not create a no-op commit.

### Task 2: Day 2 - Execute real-host conservative rollout and capture evidence

**Files:**
- Generate on host: `docs/p7a-live/acceptance-summary.json`
- Generate on host: `docs/p7a-live/status-summary.txt`
- Generate on host: `docs/p7a-live/report-message.txt`
- Review: `docs/first-deployment.md`
- Review: `docs/live-acceptance-checklist.md`
- Review: `docs/release-v0.2.0-runbook.md`

**Step 1: Verify conservative feature toggles on the real host**

Run:

```bash
grep -E 'WATCHDOG_ENABLE_(PRE_REPAIR_BACKUP|SURVIVABILITY_FLOW|SURVIVAL_MODE)=' config/openclaw-watchdog.env
```

Expected:

- `WATCHDOG_ENABLE_PRE_REPAIR_BACKUP=false`
- `WATCHDOG_ENABLE_SURVIVABILITY_FLOW=false`
- `WATCHDOG_ENABLE_SURVIVAL_MODE=false`

**Step 2: Execute the real-host gate in the documented order**

Run:

```bash
scripts/openclaw-watchdog detect
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
scripts/openclaw-watchdog status --env config/openclaw-watchdog.env --summary
scripts/openclaw-watchdog report --env config/openclaw-watchdog.env --message
./scripts/openclaw-watchdog-live-acceptance.sh
```

Expected: no traceback, no missing critical artifact, and no operator-facing contradiction between status and report output.

**Step 3: Inspect the generated live-acceptance bundle**

Run:

```bash
ls -la docs/p7a-live/
cat docs/p7a-live/acceptance-summary.json
```

Expected: `all_checks_passed=true` in the acceptance summary and the expected companion files present.

**Step 4: Stop immediately if host evidence is not green**

If any command failed, or if `all_checks_passed` is not true:

- do not cut a tag;
- do not change README to claim `v0.2.0` is published;
- open a follow-up issue with the failed command, host context, and retained artifacts.

**Step 5: Commit only if repo-tracked evidence or notes changed**

```bash
git add docs/p7a-live/ docs/release-notes-v0.2.0-draft.md
git commit -m "docs: capture v0.2.0 live acceptance evidence"
```

If the evidence should stay outside the public repo, commit only the sanitized release-notes summary.

### Task 3: Day 3 - Finalize release notes and operator-facing release story

**Files:**
- Modify: `docs/release-notes-v0.2.0-draft.md`
- Modify: `CHANGELOG.md`
- Review: `README.md`
- Review: `docs/README.md`
- Test: `tests/test_docs_surface.py`

**Step 1: Write the failing post-release docs-surface assertions**

Add assertions to `tests/test_docs_surface.py` that expect the published-state surface:

```python
def test_readme_points_to_v020_as_latest_published_release(self) -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")

    self.assertIn("Latest published release (`v0.2.0`)", readme_text)
    self.assertNotIn("Planned next release (`v0.2.0`)", readme_text)
```

```python
def test_docs_index_archives_v020_release_prep_after_publication(self) -> None:
    docs_index_text = Path("docs/README.md").read_text(encoding="utf-8")

    self.assertIn("history/release-notes-v0.2.0.md", docs_index_text)
    self.assertNotIn("release-notes-v0.2.0-draft.md", docs_index_text)
```

**Step 2: Run the focused docs test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_docs_surface -v
```

Expected: FAIL because the repo still truthfully treats `v0.2.0` as unpublished.

**Step 3: Finalize the release narrative**

Update `docs/release-notes-v0.2.0-draft.md` and `CHANGELOG.md` so they contain:

- the actual live-host evidence summary;
- the final release highlights;
- any operator cautions discovered during the real-host pass.

Do not switch current docs to published state yet. This task is only about final wording.

**Step 4: Re-run the focused docs test to confirm it still fails**

Run:

```bash
python3 -m unittest tests.test_docs_surface -v
```

Expected: still FAIL on the published-state assertions, proving the repo has not been prematurely flipped.

**Step 5: Commit the finalized release notes draft**

```bash
git add tests/test_docs_surface.py docs/release-notes-v0.2.0-draft.md CHANGELOG.md
git commit -m "docs: finalize v0.2.0 release notes content"
```

### Task 4: Day 4 - Publish `v0.2.0` and flip the repository surface

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/release-readiness.md`
- Modify: `docs/release-notes-v0.2.0-draft.md`
- Modify: `CHANGELOG.md`
- Create: `docs/history/release-notes-v0.2.0.md`
- Create: `docs/history/release-v0.2.0-runbook.md`
- Test: `tests/test_docs_surface.py`

**Step 1: Confirm the final pre-tag gate**

Run:

```bash
git status --short
git log --oneline --decorate -n 5
python3 -m unittest discover -s tests -q
bash rehearsal/scripts/run-scenario.sh critical
```

Expected: clean checkout and all release-gated checks pass.

**Step 2: Cut and push the annotated tag**

Run:

```bash
git push origin main
git tag -a v0.2.0 -m "OpenClaw Watchdog v0.2.0"
git show --stat v0.2.0
git push origin v0.2.0
```

Expected: tag exists locally and on origin.

**Step 3: Publish the GitHub release**

Use the final title and body from `docs/release-v0.2.0-runbook.md` and `docs/release-notes-v0.2.0-draft.md`.

Expected: the GitHub release page shows `v0.2.0` as the current published release.

**Step 4: Flip the repo surface from draft-state to published-state**

Update:

- `README.md` so `v0.2.0` is the latest published release;
- `docs/README.md` so the draft/runbook move into historical references;
- `docs/release-readiness.md` so it no longer frames `v0.2.0` as future work;
- `CHANGELOG.md` so `0.2.0` gets a dated release section;
- `docs/history/` with the final notes and runbook snapshots.

**Step 5: Re-run docs tests and commit**

Run:

```bash
python3 -m unittest tests.test_docs_surface -v
```

Expected: PASS with the new published-state assertions.

Then commit:

```bash
git add README.md docs/README.md docs/release-readiness.md docs/release-notes-v0.2.0-draft.md docs/history/release-notes-v0.2.0.md docs/history/release-v0.2.0-runbook.md CHANGELOG.md tests/test_docs_surface.py
git commit -m "docs: close v0.2.0 release and archive prep artifacts"
```

### Task 5: Day 5 - Expand static quality coverage beyond the stable subset

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`
- Modify: `tests/test_ci_contract.py`
- Add or modify targeted tests under `tests/`

**Step 1: Choose the next safe static-quality expansion target**

Start with one or two high-value modules that already have solid test coverage, for example:

- `openclaw_watchdog/executor_registry.py`
- `openclaw_watchdog/models.py`
- one additional presenter module

**Step 2: Write the failing CI-contract test**

Extend `tests/test_ci_contract.py` with an assertion for the broader command surface:

```python
self.assertIn("openclaw_watchdog/executor_registry.py", workflow_text)
```

**Step 3: Run the focused test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_ci_contract -v
```

Expected: FAIL until the workflow and tool config are expanded.

**Step 4: Make the minimal implementation**

Update:

- `.github/workflows/ci.yml`
- `[tool.mypy]` in `pyproject.toml`
- any required typing or lint fixes in the newly included modules

Keep the scope deliberately small enough to pass in one day.

**Step 5: Verify and commit**

Run:

```bash
python3 -m unittest tests.test_ci_contract -v
/tmp/openclaw-p0-tools/bin/ruff check <expanded-targets>
/tmp/openclaw-p0-tools/bin/mypy <expanded-targets>
```

Expected: PASS.

Then commit:

```bash
git add .github/workflows/ci.yml pyproject.toml tests/test_ci_contract.py openclaw_watchdog/
git commit -m "ci: expand static quality gates to core runtime modules"
```

### Task 6: Day 6 - Add install and packaging smoke coverage

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_ci_contract.py`
- Create: `tests/test_packaging_smoke.py`
- Review: `pyproject.toml`

**Step 1: Write the failing packaging smoke test**

Create `tests/test_packaging_smoke.py` with assertions that the package metadata and console script stay wired correctly:

```python
from pathlib import Path
import unittest


class PackagingSmokeTest(unittest.TestCase):
    def test_pyproject_declares_console_script(self) -> None:
        pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('openclaw-watchdog = "openclaw_watchdog.cli:main"', pyproject_text)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run the test to verify it passes, then add a CI requirement that fails**

Run:

```bash
python3 -m unittest tests.test_packaging_smoke -v
```

Expected: PASS for the metadata assertion.

Then extend `tests/test_ci_contract.py` to assert that CI runs a packaging smoke command, such as:

```python
self.assertIn("python -m pip install .", workflow_text)
```

Run:

```bash
python3 -m unittest tests.test_ci_contract -v
```

Expected: FAIL because CI does not yet install the package from the repo root.

**Step 3: Add the minimal packaging smoke step to CI**

In `.github/workflows/ci.yml`, add a dedicated packaging smoke sequence in a temporary environment:

```bash
python -m pip install .
python -m openclaw_watchdog --help
```

Keep it small. Do not add a heavyweight build pipeline unless needed.

**Step 4: Verify the new coverage**

Run:

```bash
python3 -m unittest tests.test_packaging_smoke tests.test_ci_contract -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml tests/test_ci_contract.py tests/test_packaging_smoke.py
git commit -m "ci: add packaging smoke coverage"
```

### Task 7: Day 7 - Polish release hygiene and clear the final trust gaps

**Files:**
- Review: `README.md`
- Review: `docs/README.md`
- Review: `docs/history/release-notes-v0.2.0.md`
- Review: `docs/history/release-v0.2.0-runbook.md`
- Review: local git stash state

**Step 1: Run the final post-release verification sweep**

Run:

```bash
python3 -m unittest discover -s tests -q
bash rehearsal/scripts/run-scenario.sh critical
/tmp/openclaw-p0-tools/bin/ruff check openclaw_watchdog/config.py openclaw_watchdog/presenters tests/test_ci_contract.py tests/test_docs_surface.py
/tmp/openclaw-p0-tools/bin/mypy openclaw_watchdog/config.py
```

Expected: PASS.

**Step 2: Verify the public surface matches the published-state story**

Manually confirm:

- README links point to the real `v0.2.0` release;
- `docs/history/` contains the archived release artifacts;
- no current doc still says `v0.2.0` is only "planned next release";
- the support matrix still matches CI and package metadata.

**Step 3: Review and clear any leftover local-only safety state**

Run:

```bash
git stash list
```

If the pre-merge safety stash is no longer needed, drop it explicitly:

```bash
git stash drop stash@{0}
```

Only do this after confirming the current `main` already contains the intended work.

**Step 4: Capture the 9-point acceptance note**

Write a short maintainer note in the release issue, project board, or internal changelog stating:

- published release is live;
- repo-local gate is green;
- host gate is green;
- static quality gate is broader than before;
- no known blocker remains for the current support surface.

**Step 5: Commit only if repo files changed**

```bash
git add README.md docs/README.md docs/history/ tests/ .github/workflows/ci.yml
git commit -m "chore: finalize v0.2.0 release hygiene"
```

If no repo files changed on Day 7, do not create a no-op commit.
