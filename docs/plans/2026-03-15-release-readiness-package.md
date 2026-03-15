# Release Readiness Package Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a release-readiness package that closes the gap between repo-local validation, real-host rollout, and the next public release announcement.

**Architecture:** Keep the current OpenClaw fallback system behavior unchanged and improve the operator/release surface around it. Add one new current-guide document for rollout and release gating, add one draft release-notes document for the next version, and wire both into the existing README/docs index/test surface so release prep becomes discoverable and regression-protected.

**Tech Stack:** Markdown docs, stdlib `unittest`, existing docs-surface coverage, repository metadata under `pyproject.toml` and `CHANGELOG.md`.

---

### Task 1: Add docs-surface tests for release-readiness artifacts

**Files:**
- Modify: `tests/test_docs_surface.py`
- Test: `tests/test_docs_surface.py`

**Step 1: Write the failing test**

Add focused assertions that current docs expose the new release-readiness path:

```python
def test_release_readiness_docs_are_linked_from_current_surfaces(self) -> None:
    readme_text = Path('README.md').read_text(encoding='utf-8')
    docs_index_text = Path('docs/README.md').read_text(encoding='utf-8')

    self.assertIn('docs/release-readiness.md', readme_text)
    self.assertIn('release-readiness.md', docs_index_text)
```

```python
def test_release_readiness_docs_cover_live_rollout_and_next_release(self) -> None:
    readiness_text = Path('docs/release-readiness.md').read_text(encoding='utf-8')
    release_notes_text = Path('docs/release-notes-v0.2.0-draft.md').read_text(encoding='utf-8')

    self.assertIn('live acceptance', readiness_text.lower())
    self.assertIn('v0.2.0', release_notes_text)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_docs_surface -v`

Expected: FAIL because the release-readiness docs and links do not exist yet.

**Step 3: Write minimal implementation**

- Add `docs/release-readiness.md` with repo gate, real-host rollout gate, release-cut checklist, and post-release follow-up.
- Add `docs/release-notes-v0.2.0-draft.md` summarizing the next release scope and operator-impacting changes.
- Wire both docs into `README.md`, `docs/README.md`, and `CHANGELOG.md`.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_docs_surface -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_docs_surface.py README.md docs/README.md docs/release-readiness.md docs/release-notes-v0.2.0-draft.md CHANGELOG.md
git commit -m "docs: add release readiness package"
```

### Task 2: Align package metadata and operator docs with the next release story

**Files:**
- Modify: `README.md`
- Modify: `docs/first-deployment.md`
- Modify: `docs/supported-environments.md`
- Modify: `pyproject.toml`
- Modify: `CHANGELOG.md`
- Test: `tests/test_docs_surface.py`

**Step 1: Write the failing test**

Add assertions that the public docs and metadata agree about release preparation:

```python
def test_release_surfaces_identify_the_next_release_candidate(self) -> None:
    readme_text = Path('README.md').read_text(encoding='utf-8')
    changelog_text = Path('CHANGELOG.md').read_text(encoding='utf-8')
    pyproject_text = Path('pyproject.toml').read_text(encoding='utf-8')

    self.assertIn('v0.2.0', readme_text)
    self.assertIn('planned next release', changelog_text.lower())
    self.assertIn('version = "0.2.0"', pyproject_text)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_docs_surface -v`

Expected: FAIL because the repo still points at `0.1.0` metadata and has no next-release packaging guidance.

**Step 3: Write minimal implementation**

- Bump `pyproject.toml` to `0.2.0`.
- Update `README.md` quick links so published `v0.1.0` and planned `v0.2.0` are both explicit.
- Update `docs/first-deployment.md` and `docs/supported-environments.md` with a short “release gate” framing that points operators and maintainers to the new release-readiness guide.
- Add a short “planned next release: v0.2.0” note under `CHANGELOG.md` `Unreleased`.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_docs_surface -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/first-deployment.md docs/supported-environments.md pyproject.toml CHANGELOG.md tests/test_docs_surface.py
git commit -m "chore: prepare metadata for v0.2.0 release"
```

### Task 3: Verify the release-readiness package end-to-end

**Files:**
- Test: `tests/test_docs_surface.py`
- Test: `tests/test_reporting.py`

**Step 1: Run focused verification**

Run:

```bash
python3 -m unittest tests.test_docs_surface tests.test_reporting -v
```

Expected: PASS.

**Step 2: Run the broad regression suite**

Run:

```bash
python3 -m unittest discover -s tests -q
```

Expected: PASS.

**Step 3: Run the rehearsal release gate**

Run:

```bash
bash rehearsal/scripts/run-scenario.sh critical
```

Expected: PASS.

**Step 4: Commit**

```bash
git add README.md docs/README.md docs/first-deployment.md docs/supported-environments.md docs/release-readiness.md docs/release-notes-v0.2.0-draft.md pyproject.toml CHANGELOG.md tests/test_docs_surface.py
git commit -m "docs: finalize v0.2.0 release readiness package"
```
