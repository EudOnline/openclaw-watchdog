# OpenClaw Watchdog

[![Release](https://img.shields.io/github/v/release/EudOnline/openclaw-watchdog?display_name=tag)](https://github.com/EudOnline/openclaw-watchdog/releases/tag/v0.1.0)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)
[![CI](https://github.com/EudOnline/openclaw-watchdog/actions/workflows/ci.yml/badge.svg)](https://github.com/EudOnline/openclaw-watchdog/actions/workflows/ci.yml)

A production-oriented external watchdog and recovery toolkit for OpenClaw.

> This repository publishes the watchdog project as a standalone, sanitized open-source package. Private workspace state, live incidents, memory files, and real credentials are intentionally excluded.

## TL;DR

OpenClaw Watchdog is designed to help operators recover a usable OpenClaw conversation path safely and quickly.

It combines:

- health checks across process, service, and conversation readiness
- conservative recovery and rollback-oriented workflows
- operator-facing incident, report, and metrics outputs
- source-first deployment with sample `systemd --user` units
- rehearsal scenarios for validation before relying on changes on a live host

## Quick links

- [Release notes](https://github.com/EudOnline/openclaw-watchdog/releases/tag/v0.1.0)
- [Documentation index](docs/README.md)
- [Supported environments](docs/supported-environments.md)
- [Operational reporting outputs](docs/reporting-contract.md)
- [First deployment guide](docs/first-deployment.md)
- [Roadmap](docs/roadmap.md)
- [FAQ](docs/faq.md)
- [Rehearsal guide](rehearsal/README.md)

## Highlights

- **External watchdog loop** for OpenClaw gateway health and remediation
- **Layered health model**: process, service probe, and conversation readiness
- **Incident workflow** with queueing, ownership, acknowledgement, notes, and timelines
- **Safety rails** for rollback, drift detection, and repair sequencing
- **Bootstrap / fallback helpers** for OpenClaw, Codex, and OpenCode handoff flows
- **Rehearsal scenarios** for testing expected failure and recovery paths
- **Systemd user units** for unattended timer-based execution on Linux

## Status

This repository is the standalone public home of **OpenClaw Watchdog**.

The public-facing interface uses the non-`v2` names throughout the repo. The internal Python package name remains `watchdog_v2` because import churn is not worth prioritizing over clear fallback flows, rehearsal coverage, and operator docs.

## Repository layout

```text
watchdog_v2/   Python implementation
scripts/       CLI wrappers and install helpers
systemd/       sample user service + timer units
docs/          current guides, validation docs, and historical notes
config/        sanitized example env files
rehearsal/     fixtures, shims, scenarios, and test flows
```

## Internal architecture

The codebase is organized around fallback-first seams so recovery logic stays explicit and testable:

- `watchdog_v2/models.py` for typed state models at serialization boundaries
- `watchdog_v2/presenters/` for human-readable CLI formatting
- `watchdog_v2/run_context.py` for mutable per-run state
- `watchdog_v2/flows/` for run orchestration paths
- `watchdog_v2/bootstrap_steps.py` for ordered bootstrap step execution
- `watchdog_v2/engine.py` as the runtime facade and dependency hub

For the fuller package map and validation story, see `docs/internal-architecture.md`.

## Requirements

For the supported environment matrix and release expectations, see `docs/supported-environments.md`.

- Python 3.11+
- `scripts/openclaw-watchdog` checks for a compatible interpreter before importing the package and prefers `python3.11`, `python3.12`, `python3.13`, or a compatible `python3`
- OpenClaw installed on the target machine
- Linux with `systemd --user` if you want the provided timer units
- Standard host tools used by the watchdog or rehearsal flows, depending on features enabled:
  - `systemctl`
  - `ss`
  - `ps`
  - `journalctl`

## Installation

### Option 1: Run from a cloned repo

```bash
git clone https://github.com/EudOnline/openclaw-watchdog ~/openclaw-watchdog
cd ~/openclaw-watchdog
cp config/openclaw-watchdog.env.example config/openclaw-watchdog.env
chmod +x scripts/openclaw-watchdog scripts/install-openclaw-watchdog-units.sh
```

Quick sanity check:

```bash
scripts/openclaw-watchdog --help
scripts/openclaw-watchdog detect
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
```

If the wrapper reports that no compatible interpreter was found, install Python 3.11+ first and rerun the same command. The wrapper accepts any compatible `python3.11+` interpreter name it can discover, including `python3.11`, `python3.12`, `python3.13`, or a compatible `python3`. For the first live rollout, follow `docs/first-deployment.md` before enabling the timer.

### Option 2: Python module entrypoint

If you are working from a source checkout, you can also invoke the package directly:

```bash
python3.11 -m watchdog_v2 --help
```

## Configuration

Start from:

- `config/openclaw-watchdog.env.example`

Important knobs include:

- OpenClaw config path and gateway service name
- watchdog state / incident directories
- restart and probe grace periods
- service-level failure threshold
- notification target/channel
- backup / rollback behavior
- Codex / OpenCode fallback settings

The example config is intentionally sanitized. Its paths and conservative rollout toggles are now aligned with the built-in defaults so a missing env file does not silently fall back to `/root/...`-style paths or enable aggressive automation. You must still set values appropriate for your own host.

## Common commands

Operator quick path for the first live rollout: `detect` -> `check` -> `status --summary` -> `report --message` -> `incidents queue` -> `maintenance on|off`.

```bash
# one remediation pass
scripts/openclaw-watchdog run-once

# health check without remediation
scripts/openclaw-watchdog check

# human status summary
scripts/openclaw-watchdog status --summary

# compact operator report
scripts/openclaw-watchdog report

# inspect incident queue
scripts/openclaw-watchdog incidents queue

# show one incident
scripts/openclaw-watchdog incidents show <incident_id>

# enable maintenance mode
scripts/openclaw-watchdog maintenance on --reason "planned maintenance"
```

## Install systemd user units

The sample units assume the repo lives at `~/openclaw-watchdog`.

```bash
git clone https://github.com/EudOnline/openclaw-watchdog ~/openclaw-watchdog
cd ~/openclaw-watchdog
cp config/openclaw-watchdog.env.example config/openclaw-watchdog.env
scripts/install-openclaw-watchdog-units.sh
systemctl --user enable --now openclaw-watchdog.timer
```

Check status:

```bash
systemctl --user status openclaw-watchdog.timer
systemctl --user status openclaw-watchdog.service
```

## Rehearsal and validation

This repo includes a repo-local rehearsal harness for validating flows without using a live production gateway. The recommended validation order is:

1. fast unit and output-shape tests (`python -m unittest discover -s tests -v`)
2. direct orchestration tests for flows and bootstrap steps
3. bounded rehearsal smoke scenarios under `rehearsal/scripts/run-scenario.sh`
4. live acceptance only after the earlier layers are green

Start with:

- `docs/README.md`
- `rehearsal/README.md`
- `docs/live-acceptance-checklist.md`
- `docs/live-samples.md`
- `docs/supported-environments.md`
- `docs/roadmap.md`
- `docs/faq.md`
- `docs/history/MIGRATION-v2.md` (historical migration notes)

## Design notes

The watchdog is designed around a few principles:

1. **Repair only after evidence collection**
2. **Prefer reversible changes**
3. **Separate process health from actual usability**
4. **Keep an operator-visible incident trail**
5. **Support staged automation instead of blind restart loops**

## Repository notes

- Canonical CLI wrapper: `scripts/openclaw-watchdog`
- Canonical env example: `config/openclaw-watchdog.env.example`
- Canonical systemd units: `systemd/openclaw-watchdog.service` and `systemd/openclaw-watchdog.timer`
- Internal Python package name remains `watchdog_v2` for implementation stability
- Legacy shim scripts remain only as migration aids and are not part of the primary fallback path:
  - `scripts/openclaw-watchdog-v2`
  - `scripts/install-openclaw-watchdog-v2-units.sh`
  - `scripts/openclaw-watchdog-v2-live-acceptance.sh`
- Historical migration notes remain in `docs/history/MIGRATION-v2.md`

## Security

Please do **not** publish live `.env` files, incident bundles, or host-specific status dumps. See [SECURITY.md](SECURITY.md) for reporting guidance and repository hygiene notes.

## Contributing

Contributions, bug reports, and cleanup PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
