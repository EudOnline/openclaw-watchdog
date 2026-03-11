# Changelog

All notable changes to this public repository will be documented here.

## Unreleased

### Changed
- split CLI text rendering into `watchdog_v2/presenters/` so parser/dispatch stay separate from human-readable formatting
- extract mutable per-run engine state into `watchdog_v2/run_context.py` and bridge legacy `engine.<field>` access through `engine.ctx`
- move legacy and survivability `run-once` orchestration into `watchdog_v2/flows/` while keeping public behavior stable
- split bootstrap orchestration into ordered helpers under `watchdog_v2/bootstrap_steps.py`
- expand CI to verify Python 3.11 and 3.13 while keeping rehearsal smoke scenarios on the baseline lane

- freeze the public refactor boundary around canonical CLI entrypoints, stable report/metrics keys, and rehearsal scenario intent before deeper internal cleanup
- expand CI quality gates to run Python 3.11 CLI smoke coverage plus higher-signal rehearsal scenarios
- formalize the supported environment baseline around Python 3.11+, Linux + `systemd --user`, and release-gated repo-local rehearsal expectations
- continue thinning `watchdog_v2/engine.py` by extracting event shaping and incident/report context helpers
- add explicit Python 3.11+ wrapper checks so unsupported hosts see a clear requirement message instead of a traceback
- align built-in config defaults with the sample env file for home-directory paths and conservative first-rollout toggles
- rewrite rehearsal docs around the repo-local entrypoints that actually ship in this repository
- publish a clearer first-deployment checklist and a reporting contract document for operator/integration consumers
- extract subprocess and state-persistence helpers from `watchdog_v2/engine.py` into focused modules

### Added
- `docs/supported-environments.md` to define the current support matrix and release discipline
- focused regression tests for extracted event and incident-context helpers
- a minimal GitHub Actions workflow plus focused local regression tests for runtime wrapper, config defaults, reporting, CLI smoke, runtime helpers, and state-store helpers


## 0.1.0 - 2026-03-10

### Added
- Initial public export of the OpenClaw watchdog project
- Python watchdog engine under `watchdog_v2/`
- CLI wrappers and sample systemd units
- Rehearsal harness, fixtures, and scenarios
- Public project metadata and contribution docs

### Changed
- Public-facing project name standardized to **OpenClaw Watchdog**
- README rewritten for standalone repository usage
- Added generic install path examples using `~/openclaw-watchdog`
- Canonical CLI, env, and systemd entrypoints now use the non-`v2` names
- Deprecated `v2` wrappers were reduced to migration shims instead of parallel primary entrypoints

### Removed
- Duplicate `v2` sample systemd units from the primary public surface
- Duplicate `v2` env example from the primary public surface

### Notes
- Internal module naming remains `watchdog_v2` for compatibility with the original workspace history
- Historical migration notes remain in `docs/history/MIGRATION-v2.md`
- Deprecated shim scripts remain available for transition, but are no longer part of the primary public installation path
- Current and historical docs are now separated under `docs/` and `docs/history/`
