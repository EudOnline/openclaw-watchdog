# P0 Technical Debt Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the three highest-priority technical debt items before or as part of the `v0.2.0` release: add CI quality gates, align package metadata with the documented support matrix, and complete the `v0.2.0` release closure on both the operational and repository surfaces.

**Architecture:** Treat the current OpenClaw fallback runtime, docs, and release-readiness work as the baseline. This plan should not add new recovery behavior. It should tighten release confidence around the existing product by improving static quality gates, removing Python-version metadata drift, and turning the current `v0.2.0` draft state into a published-state repository surface once real-host acceptance evidence exists.

**Tech Stack:** Python 3.11 and 3.13, stdlib `unittest`, GitHub Actions, `ruff`, `mypy`, Markdown docs, Git tags, existing release-readiness and runbook docs.

---

### Task 1: Add release-gated lint and minimal type checks to CI

**Files:**
- Create: `tests/test_ci_contract.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`

**Step 1: Write the failing test**

Create `tests/test_ci_contract.py` with focused assertions that the workflow and project config declare the new quality gates:

```python
from pathlib import Path
import unittest


class CiContractTest(unittest.TestCase):
    def test_ci_workflow_installs_and_runs_ruff_and_mypy(self) -> None:
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

        self.assertIn('python -m pip install ruff mypy', workflow_text)
        self.assertIn('python -m ruff check', workflow_text)
        self.assertIn('python -m mypy', workflow_text)

    def test_pyproject_declares_quality_tool_configuration(self) -> None:
        pyproject_text = Path('pyproject.toml').read_text(encoding='utf-8')

        self.assertIn('[tool.ruff]', pyproject_text)
        self.assertIn('[tool.mypy]', pyproject_text)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_ci_contract -v
```

Expected: FAIL because the workflow does not run `ruff` or `mypy`, and `pyproject.toml` does not declare those tool sections yet.

**Step 3: Write the minimal implementation**

- Add a quality-tools install step to `.github/workflows/ci.yml`:

```yaml
- name: Install quality tools
  run: python -m pip install ruff mypy
```

- Add a lint step:

```yaml
- name: Ruff
  run: python -m ruff check openclaw_watchdog tests scripts
```

- Add a narrow type-check step that only gates the most stable current modules first:

```yaml
- name: Mypy
  run: python -m mypy openclaw_watchdog/config.py openclaw_watchdog/presenters
```

- Add minimal tool config to `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.mypy]
python_version = "3.11"
warn_unused_configs = true
disallow_untyped_defs = false
check_untyped_defs = true
files = ["openclaw_watchdog/config.py", "openclaw_watchdog/presenters"]
```

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_ci_contract -v
```

Expected: PASS.

**Step 5: Run the new local quality commands**

Run:

```bash
python3 -m ruff check openclaw_watchdog tests scripts
python3 -m mypy openclaw_watchdog/config.py openclaw_watchdog/presenters
```

Expected: PASS.

**Step 6: Commit**

```bash
git add tests/test_ci_contract.py .github/workflows/ci.yml pyproject.toml
git commit -m "ci: add lint and minimal type gates"
```

### Task 2: Align packaging metadata with the documented support matrix

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `docs/supported-environments.md`
- Modify: `tests/test_docs_surface.py`

**Step 1: Write the failing test**

Add a focused assertion to `tests/test_docs_surface.py`:

```python
def test_python_classifiers_match_the_documented_ci_versions(self) -> None:
    pyproject_text = Path('pyproject.toml').read_text(encoding='utf-8')
    readme_text = Path('README.md').read_text(encoding='utf-8')
    workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

    self.assertIn("Programming Language :: Python :: 3.13", pyproject_text)
    self.assertIn("python3.13", readme_text.lower())
    self.assertIn("'3.13'", workflow_text)
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_docs_surface -v
```

Expected: FAIL because `pyproject.toml` does not currently advertise Python 3.13 even though the README and CI surface already treat it as part of the validated path.

**Step 3: Write the minimal implementation**

- Add the Python 3.13 classifier to `pyproject.toml`.
- Review `README.md` and `docs/supported-environments.md` so they explicitly say:
  - runtime baseline is Python `3.11+`;
  - CI/release-gated validation runs on Python `3.11` and `3.13`;
  - packaging metadata matches those claims.

If wording drift appears, normalize it while keeping the current support scope unchanged.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_docs_surface -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml README.md docs/supported-environments.md tests/test_docs_surface.py
git commit -m "chore: align package metadata with supported python versions"
```

### Task 3: Close the `v0.2.0` release and update the repository surface to published state

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/release-readiness.md`
- Modify: `docs/release-notes-v0.2.0-draft.md`
- Modify: `docs/release-v0.2.0-runbook.md`
- Create: `docs/history/release-notes-v0.2.0.md`
- Create: `docs/history/release-v0.2.0-runbook.md`
- Modify: `tests/test_docs_surface.py`

**Step 1: Write the failing test**

Add release-closure assertions to `tests/test_docs_surface.py`:

```python
def test_readme_points_to_v020_as_the_latest_published_release(self) -> None:
    readme_text = Path('README.md').read_text(encoding='utf-8')

    self.assertIn("Latest published release (`v0.2.0`)", readme_text)
    self.assertNotIn("Planned next release (`v0.2.0`)", readme_text)
```

```python
def test_current_docs_no_longer_present_v020_draft_release_prep_as_active(self) -> None:
    docs_index_text = Path('docs/README.md').read_text(encoding='utf-8')

    self.assertNotIn('release-notes-v0.2.0-draft.md', docs_index_text)
    self.assertNotIn('release-v0.2.0-runbook.md', docs_index_text)
    self.assertIn('history/release-notes-v0.2.0.md', docs_index_text)
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_docs_surface -v
```

Expected: FAIL because the current surface still treats `v0.2.0` as the planned next release.

**Step 3: Run the real-host release gate**

On the supported real host, run:

```bash
scripts/openclaw-watchdog detect
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
scripts/openclaw-watchdog status --env config/openclaw-watchdog.env --summary
scripts/openclaw-watchdog report --env config/openclaw-watchdog.env --message
./scripts/openclaw-watchdog-live-acceptance.sh
```

Expected:

- `docs/p7a-live/acceptance-summary.json` shows `all_checks_passed=true`;
- no command returns a traceback;
- the generated artifacts are suitable to summarize in the release notes.

**Step 4: Update the repository surface to published state**

- Summarize the real-host evidence in `docs/release-notes-v0.2.0-draft.md`.
- Copy the finalized release notes to `docs/history/release-notes-v0.2.0.md`.
- Copy the final release runbook to `docs/history/release-v0.2.0-runbook.md`.
- Update `README.md` so `v0.2.0` is the latest published release and remove the “planned next release” wording.
- Update `docs/README.md` so the draft/runbook are no longer listed as active release-prep docs.
- Update `docs/release-readiness.md` so it no longer describes `v0.2.0` as future work.
- Update `CHANGELOG.md` so the current `Unreleased` section is split from a new `## 0.2.0 - 2026-03-15` section.

**Step 5: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_docs_surface -v
```

Expected: PASS.

**Step 6: Commit the published-state repository surface**

```bash
git add README.md docs/README.md CHANGELOG.md docs/release-readiness.md docs/release-notes-v0.2.0-draft.md docs/release-v0.2.0-runbook.md docs/history/release-notes-v0.2.0.md docs/history/release-v0.2.0-runbook.md tests/test_docs_surface.py
git commit -m "docs: close v0.2.0 release surface"
```

**Step 7: Create and push the release tag**

Run:

```bash
git push origin main
git tag -a v0.2.0 -m "OpenClaw Watchdog v0.2.0"
git push origin v0.2.0
```

Expected: tag exists remotely and points at the published-state release commit.

**Step 8: Publish the GitHub release**

Use the text finalized from `docs/history/release-notes-v0.2.0.md` or the published-state release notes file.

Expected: the GitHub release page shows `OpenClaw Watchdog v0.2.0` and includes the real-host acceptance summary.

### Task 4: Verify the entire P0 closure set end-to-end

**Files:**
- Test: `tests/test_ci_contract.py`
- Test: `tests/test_docs_surface.py`
- Test: `.github/workflows/ci.yml`

**Step 1: Run focused verification**

Run:

```bash
python3 -m unittest tests.test_ci_contract tests.test_docs_surface -v
```

Expected: PASS.

**Step 2: Run full regression verification**

Run:

```bash
python3 -m unittest discover -s tests -q
bash rehearsal/scripts/run-scenario.sh critical
```

Expected: PASS.

**Step 3: Run the release-prep commands one last time on the local repo**

Run:

```bash
python3 -m openclaw_watchdog --help
git status --short
git tag --list | tail -n 20
```

Expected:

- CLI help works;
- working tree is clean before or immediately after tag creation, depending on timing;
- `v0.2.0` appears in the tag list after the release step.

**Step 4: Commit**

```bash
git add .github/workflows/ci.yml pyproject.toml README.md docs/README.md docs/supported-environments.md CHANGELOG.md docs/release-readiness.md docs/release-notes-v0.2.0-draft.md docs/release-v0.2.0-runbook.md docs/history/release-notes-v0.2.0.md docs/history/release-v0.2.0-runbook.md tests/test_ci_contract.py tests/test_docs_surface.py
git commit -m "chore: close p0 release-quality debt"
```
