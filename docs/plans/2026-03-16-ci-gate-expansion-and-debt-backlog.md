# CI Gate Expansion And Debt Backlog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the repo's static quality gates so they cover the newly added platform and upstream-contract seams, and publish a current technical-debt backlog that reflects the post-refactor project state.

**Architecture:** Treat the current runtime and test suite as the baseline. This work should not change recovery behavior. It should tighten the release gate around the code that was just added, and make the remaining debt explicit in repo docs so future hardening work follows a shared priority order.

**Tech Stack:** Python 3.11 and 3.13, stdlib `unittest`, GitHub Actions, `ruff`, `mypy`, `py_compile`, Markdown docs.

---

### Task 1: Expand CI contract coverage for new platform and upstream seams

**Files:**
- Modify: `tests/test_ci_contract.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`

**Step 1: Write the failing test**

Add assertions that CI now:

- lints `openclaw_watchdog/platforms` and `openclaw_watchdog/openclaw_runtime`
- type-checks those same packages
- byte-compiles those same packages

**Step 2: Run test to verify it fails**

Run:

```bash
python3.13 -m unittest tests.test_ci_contract -v
```

Expected: FAIL because the workflow and mypy config still only cover a narrow subset of files.

**Step 3: Write the minimal implementation**

- Expand the `ruff` command in `.github/workflows/ci.yml`
- Expand the `mypy` command in `.github/workflows/ci.yml`
- Expand the `py_compile` command in `.github/workflows/ci.yml`
- Update `[tool.mypy]` in `pyproject.toml` so the checked file set matches the workflow

**Step 4: Run the focused test to verify it passes**

Run:

```bash
python3.13 -m unittest tests.test_ci_contract -v
```

Expected: PASS.

### Task 2: Publish the current technical-debt priority backlog

**Files:**
- Modify: `tests/test_docs_surface.py`
- Modify: `docs/README.md`
- Create: `docs/technical-debt-priority-backlog.md`

**Step 1: Write the failing test**

Add assertions that:

- the new technical-debt document exists
- it contains priority markers like `P0`, `P1`, and `P2`
- it is linked from `docs/README.md`

**Step 2: Run test to verify it fails**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: FAIL because the document and docs index link do not exist yet.

**Step 3: Write the minimal implementation**

- Create a concise technical-debt backlog doc that reflects the current project state after the platform/upstream seam work
- Include a short scoring snapshot, current strengths, and the highest-priority debt items
- Link the new document from `docs/README.md`

**Step 4: Run the focused test to verify it passes**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: PASS.

### Task 3: Verify the expanded quality gate locally and commit

**Files:**
- Modify as needed from Tasks 1-2

**Step 1: Run focused verification**

Run:

```bash
python3.13 -m unittest tests.test_ci_contract tests.test_docs_surface -v
```

Expected: PASS.

**Step 2: Run local quality commands that mirror the updated workflow**

Run:

```bash
python3.13 -m pip install ruff mypy
python3.13 -m ruff check openclaw_watchdog/config.py openclaw_watchdog/executor_registry.py openclaw_watchdog/platforms openclaw_watchdog/openclaw_runtime openclaw_watchdog/presenters tests/test_ci_contract.py tests/test_docs_surface.py tests/test_packaging_smoke.py
python3.13 -m mypy openclaw_watchdog/config.py openclaw_watchdog/executor_registry.py openclaw_watchdog/platforms openclaw_watchdog/openclaw_runtime
python3.13 -m py_compile openclaw_watchdog/*.py openclaw_watchdog/platforms/*.py openclaw_watchdog/openclaw_runtime/*.py openclaw_watchdog/presenters/*.py openclaw_watchdog/flows/*.py rehearsal/lib/*.py rehearsal/tools/*.py tests/*.py
python3.13 -m unittest discover -s tests -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add .github/workflows/ci.yml pyproject.toml tests/test_ci_contract.py tests/test_docs_surface.py docs/README.md docs/technical-debt-priority-backlog.md docs/plans/2026-03-16-ci-gate-expansion-and-debt-backlog.md
git commit -m "ci: expand static gates for new runtime seams"
```
