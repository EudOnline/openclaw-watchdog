# Changelog

All notable changes to this public repository will be documented here.

## Unreleased

Planned next release: `v0.2.0` after the repo-local release gate and real-host live acceptance both pass.

### Changed
- surface recent model HTTP non-200 and last model-failover state in `report --json`, `report --message`, `metrics --json`, and Prometheus output so operators can confirm watchdog-driven model rotation
- surface actionable model-failover state in `status --summary` so operators can scan `model_failover=...`, recent non-200 count, and the current switch target without opening the full JSON payloads
- add a bounded daily rate limit for automatic model rotation with `WATCHDOG_MODEL_FAILOVER_MAX_APPLIES_PER_DAY`, preserving the existing cooldown while preventing repeated rewrite churn on one host
- add a release-readiness guide plus draft `v0.2.0` release notes so rollout validation and release packaging follow one documented path
- align the rehearsal harness with the fixed rescue-order contract by removing legacy priority-override injection from repo-local scenarios
- promote core survivability scenarios such as conversation readiness, rollback-before-doctor, survival recovery, and drift guard into the critical rehearsal gate
- make deterministic recovery stop carrying stale `config_invalid` state past a successful rollback and restart the service after survival-mode activation before re-probing
- tighten external rescue adapter parsing so plans with unexpected top-level keys are rejected instead of being treated as valid structured rescue plans
- align `status --summary` wording with live-acceptance checks by using `conversation=...` in the compact operator summary
- split CLI text rendering into `openclaw_watchdog/presenters/` so parser/dispatch stay separate from human-readable formatting
- extract mutable per-run engine state into `openclaw_watchdog/run_context.py`; runtime state now lives under `engine.ctx` without a legacy attribute bridge
- move `run-once` orchestration into `openclaw_watchdog/flows/` so OpenClaw fallback behavior is explicit and directly testable
- keep bootstrap orchestration object-first under `openclaw_watchdog/bootstrap_steps.py` and serialize only at output boundaries
- stop treating typed models as dicts; reporting and incident shaping now use typed objects internally
- remove compatibility-only report/metrics fields such as `recent_incident_summaries`, `current_incident_events_count`, and `current_incident_latest_event_type`
- rewrite reporting and architecture docs around the OpenClaw fallback system instead of broad compatibility promises
- expand CI to verify Python 3.11 and 3.13 while keeping rehearsal smoke scenarios on the baseline lane
- formalize the supported environment baseline around Python 3.11+, Linux + `systemd --user`, and release-gated repo-local rehearsal expectations
- add explicit Python 3.11+ wrapper checks so unsupported hosts see a clear requirement message instead of a traceback
- align built-in config defaults with the sample env file for home-directory paths and conservative first-rollout toggles
- rewrite rehearsal docs around the repo-local entrypoints that actually ship in this repository
- publish a clearer first-deployment checklist and an operational reporting-output document for OpenClaw fallback operators and integration consumers
- continue thinning `openclaw_watchdog/engine.py` by extracting event shaping and incident/report context helpers
- extract subprocess and state-persistence helpers from `openclaw_watchdog/engine.py` into focused modules

### Added
- `docs/supported-environments.md` to define the current support matrix and release discipline
- a deterministic rehearsal scenario for `watchdog-model-http-error-failover` so bounded local validation covers config rewrite, recovery attribution, and operator output consistency
- rollout, rollback, and live-acceptance guidance for model HTTP non-200 failover across `README.md`, deployment docs, and reporting-contract docs
- focused regression tests for extracted event and incident-context helpers
- a minimal GitHub Actions workflow plus focused local regression tests for runtime wrapper, config defaults, reporting, CLI smoke, runtime helpers, and state-store helpers
- docs and config guidance for the fixed OpenClaw fallback rescue chain and detect-only operating model


## 0.1.0 - 2026-03-10

### Added
- Initial public export of the OpenClaw fallback project
- Python fallback engine under `openclaw_watchdog/`
- CLI wrappers and sample systemd units
- Rehearsal harness, fixtures, and scenarios
- Public project metadata and contribution docs

### Changed
- Public-facing project name standardized to **OpenClaw Watchdog**
- README rewritten for standalone repository usage
- Added source-first install path examples using `~/openclaw-watchdog`
- Canonical CLI, env, and systemd entrypoints now use one OpenClaw Watchdog surface
- Legacy wrapper names were removed from the active installation path

### Removed
- Duplicate legacy sample systemd units from the primary public surface
- Duplicate legacy env examples from the primary public surface

### Notes
- Internal module naming remains `openclaw_watchdog`; import renaming is intentionally deprioritized relative to fallback correctness and rehearsal confidence
- Historical migration notes remain in `docs/history/migration-legacy-rollout.md`
- Current and historical docs are now separated under `docs/` and `docs/history/`
