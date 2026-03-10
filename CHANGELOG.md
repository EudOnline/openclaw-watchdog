# Changelog

All notable changes to this public repository will be documented here.

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
- Historical migration notes remain in `MIGRATION-v2.md`
- Deprecated shim scripts remain available for transition, but are no longer part of the primary public installation path
