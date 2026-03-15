# Technical Debt Priority Backlog

This document captures the current technical-debt order after the platform-adapter and OpenClaw upstream-contract refactors landed on `main`.

## Current score snapshot

- Overall project health: `8.2/10`
- Architecture: `8.8/10`
- Testability: `8.5/10`
- Maintainability: `7.8/10`
- Release readiness: `6.2/10`
- Platform extensibility: `8.6/10`

## What is already strong

- Recovery behavior now flows through a clearer composition model instead of Linux-specific inline assumptions.
- `openclaw_watchdog/platforms/` and `openclaw_watchdog/openclaw_runtime/` isolate the two fastest-changing seams in the project.
- The repo has a large unit-test surface, a bounded rehearsal gate, and explicit release-readiness docs.

## Priority order

### P0: Expand static quality gates to match the real code surface

Why it matters:

- CI still needs to police the newer packages with the same discipline applied to the earlier core modules.
- Without broader `ruff`, `mypy`, and `py_compile` coverage, regression detection depends too heavily on runtime-style tests alone.

What to close:

- keep `openclaw_watchdog/platforms/` under lint, type-check, and byte-compile coverage
- keep `openclaw_watchdog/openclaw_runtime/` under lint, type-check, and byte-compile coverage
- treat quality-gate drift as release debt, not cleanup work

### P0: Complete real-host release evidence for the supported production path

Why it matters:

- The repo-local suite is strong, but the release story still explicitly depends on Linux + `systemd --user` live acceptance.
- Until that evidence exists, the release-readiness gap is operational, not architectural.

What to close:

- run the documented conservative rollout and live acceptance on a real Linux host
- archive the resulting `docs/p7a-live/` evidence with the release package
- do not widen production claims until the evidence is attached

### P1: Finish slimming the CLI output layer

Why it matters:

- `openclaw_watchdog/cli_output.py` is still a large formatting hub even though the repo now has dedicated presenters.
- This is not breaking release quality today, but it is a friction point for future operator-surface changes.

What to close:

- keep command dispatch in `cli.py`
- move remaining text formatting responsibilities into focused presenter owners or command-local output helpers
- avoid re-growing one large print-surface module

### P1: Reduce hotspot concentration in a few runtime and test files

Why it matters:

- A small number of files still carry a large share of complexity, especially incident, generation, and rescue-flow areas.
- The direction is healthy, but hotspot concentration still raises change risk for future refactors.

What to close:

- continue splitting read/write incident concerns when practical
- keep `generation_runtime.py` and rescue-flow orchestration under active simplification review
- prefer smaller owner modules over adding more helper wrappers back into `engine.py`

### P2: Clean repository hygiene leftovers from earlier phases

Why it matters:

- The repo still contains non-product leftovers such as the empty historical `watchdog_v2/` tree with only ignored `__pycache__` content on disk.
- This is low-risk debt, but it adds noise when navigating the repository.

What to close:

- remove stale leftover directories that no longer belong to the active source surface
- keep `.gitignore` and local cleanup habits aligned so generated artifacts do not distract from real project structure

## Decision rule for the next batch

If the goal is shipping confidence, take `P0` items first.

If the goal is long-term maintainability after release evidence is complete, move to the `P1` items.

If the goal is repo cleanliness only, defer `P2` until it does not compete with validation or release work.
