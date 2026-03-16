# OpenClaw Watchdog

[![Release](https://img.shields.io/github/v/release/EudOnline/openclaw-watchdog?display_name=tag)](https://github.com/EudOnline/openclaw-watchdog/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)
[![CI](https://github.com/EudOnline/openclaw-watchdog/actions/workflows/ci.yml/badge.svg)](https://github.com/EudOnline/openclaw-watchdog/actions/workflows/ci.yml)

A production-oriented OpenClaw fallback and recovery system.

> This repository publishes the OpenClaw fallback system as a standalone, sanitized open-source package. Private workspace state, live incidents, memory files, and real credentials are intentionally excluded.

## TL;DR

OpenClaw Watchdog is an OpenClaw fallback system designed to restore a usable conversation path safely and quickly.

It combines:

- health checks across process, service, and conversation readiness
- conservative recovery and rollback-oriented workflows
- operator-facing incident, report, and metrics outputs
- source-first deployment with sample `systemd --user` units
- experimental `launchd` assets for macOS adapter testing
- rehearsal scenarios for validation before relying on changes on a live host

## Quick links

- [Rescue lifecycle guide](docs/rescue-lifecycle.md)
- [Latest published release (`v0.1.0`)](https://github.com/EudOnline/openclaw-watchdog/releases/tag/v0.1.0)
- [Planned next release (`v0.2.0`) draft notes](docs/release-notes-v0.2.0-draft.md)
- [Release readiness guide](docs/release-readiness.md)
- [Final `v0.2.0` release runbook](docs/release-v0.2.0-runbook.md)
- [Documentation index](docs/README.md)
- [Supported environments](docs/supported-environments.md)
- [Operational reporting outputs](docs/reporting-contract.md)
- [First deployment guide](docs/first-deployment.md)
- [macOS launchd rollout guide](docs/macos-launchd-rollout.md)
- [Roadmap](docs/roadmap.md)
- [FAQ](docs/faq.md)
- [Rehearsal guide](rehearsal/README.md)

## Highlights

- **OpenClaw fallback loop** for gateway health and remediation
- **Layered health model**: process, service probe, and conversation readiness
- **Incident workflow** with queueing, ownership, acknowledgement, notes, and timelines
- **Safety rails** for rollback, drift detection, and repair sequencing
- **Detect-only bootstrap and rescue inventory** for the prioritized executor chain
- **Rehearsal scenarios** for testing expected failure and recovery paths
- **Systemd user units** for unattended timer-based execution on Linux
- **Experimental macOS `launchd` path** for adapter validation before live acceptance

## Status

This repository is the standalone public home of the **OpenClaw fallback system**.

The repository now uses one canonical name throughout the public surface and Python implementation: `openclaw_watchdog`.

The repository metadata and current release-prep docs now target the planned next release, `v0.2.0`. The latest published GitHub release remains `v0.1.0` until the next tag is cut.

Linux + `systemd --user` remains the only live-validated deployment path today. macOS + `launchd` is now present as an experimental path for platform-adapter validation, but it is not yet claimed as a production-ready rollout target.

## Repository layout

```text
openclaw_watchdog/   Python implementation
scripts/       CLI wrappers and install helpers
systemd/       sample user service + timer units
launchd/       experimental macOS launch agent sample
docs/          current guides, validation docs, and historical notes
config/        sanitized example env files
rehearsal/     fixtures, shims, scenarios, and test flows
```

## Internal architecture

The codebase is organized around OpenClaw fallback seams so recovery logic stays explicit and testable:

- `openclaw_watchdog/engine_support_runtime.py` for state-dir prep, file locking, logging, notifications, failure counters, and small engine host helpers
- `openclaw_watchdog/doctor_runtime.py` for `openclaw doctor --non-interactive` execution and config-invalid parsing
- `openclaw_watchdog/models.py` for typed state models at serialization boundaries
- `openclaw_watchdog/presenters/` for human-readable CLI formatting
- `openclaw_watchdog/run_context.py` for mutable per-run state
- `openclaw_watchdog/flows/` for rescue-first run orchestration
- `openclaw_watchdog/executor_registry.py` for canonical rescue-chain order, availability checks, and runtime settings
- `openclaw_watchdog/maintenance_runtime.py` for maintenance mode file toggles and operator-facing state handoff
- `openclaw_watchdog/last_good_runtime.py` for last-good generations, drift context, and protected-path guard snapshots
- `openclaw_watchdog/rollback_runtime.py` for rollback summaries, rollback archive pruning, and last-good restore execution
- `openclaw_watchdog/repair_action_runtime.py` for pre-repair backup, service restart, stray-listener cleanup, and doctor-repair actions
- `openclaw_watchdog/service_runtime.py` for platform-adapter based service probing
- `openclaw_watchdog/platforms/` for Linux `systemd` and experimental macOS `launchd` host adapters
- `openclaw_watchdog/bootstrap_steps.py` for ordered bootstrap step execution
- `openclaw_watchdog/bootstrap_inventory.py` and `openclaw_watchdog/bootstrap_inspectors.py` for read-only bootstrap checks
- `openclaw_watchdog/engine.py` as the runtime facade and dependency hub

For the fuller package map and validation story, see `docs/internal-architecture.md`.

## Requirements

For the supported environment matrix and release expectations, see `docs/supported-environments.md`.

- Python 3.11+
- release-gated CI validation currently runs on Python 3.11 and 3.13
- `scripts/openclaw-watchdog` checks for a compatible interpreter before importing the package and prefers `python3.11`, `python3.12`, `python3.13`, or a compatible `python3`
- OpenClaw installed on the target machine
- Linux with `systemd --user` if you want the provided timer units
- macOS with `launchd` only if you are explicitly validating the experimental host adapter path
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
chmod +x scripts/openclaw-watchdog scripts/install-openclaw-watchdog-units.sh scripts/install-openclaw-watchdog-launchd.sh
```

Quick sanity check:

```bash
scripts/openclaw-watchdog --help
scripts/openclaw-watchdog detect
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
```

If the wrapper reports that no compatible interpreter was found, install Python 3.11+ first and rerun the same command. The wrapper accepts any compatible `python3.11+` interpreter name it can discover, including `python3.11`, `python3.12`, `python3.13`, or a compatible `python3`. For the first live rollout, follow `docs/first-deployment.md` before enabling the timer.

For the narrow macOS `launchd` path, start from `config/openclaw-watchdog.macos.env.example` so `OPENCLAW_GATEWAY_SERVICE` uses a `launchd` label such as `com.openclaw.gateway` instead of a Linux `.service` unit name.

### Option 2: Python module entrypoint

If you are working from a source checkout, you can also invoke the package directly:

```bash
python3.11 -m openclaw_watchdog --help
```

## Configuration

Start from:

- `config/openclaw-watchdog.env.example`
- `config/openclaw-watchdog.macos.env.example` for the experimental macOS `LaunchAgent` path

Important knobs include:

- OpenClaw config path and gateway service name
- watchdog state / incident directories
- restart and probe grace periods
- service-level failure threshold
- opt-in message-loop probe settings for a real transport echo check
- notification target/channel
- backup / rollback behavior
- fixed rescue order (`Codex -> Claude Code -> Gemini CLI -> OpenCode -> LiteLLM -> rule-agent`)
- remote-model settings for the `LiteLLM` specialist agent
- editable OpenClaw file/key boundaries for controlled rescue mutation

The example config is intentionally sanitized. Its paths and conservative rollout toggles are now aligned with the built-in defaults so a missing env file does not silently fall back to `/root/...`-style paths or enable aggressive automation. Bootstrap and `detect` inventory available rescue executors, but they do not install missing tools for you. OpenClaw and any external rescue CLI must already be installed on the host you operate.

The controlled mutation surface is intentionally narrow:

- rescue config writes are limited to an explicit file allowlist
- by default that allowlist contains only `~/.openclaw/openclaw.json` and `~/.openclaw-backup/watchdog/openclaw.survival.json`
- editable keys use exact-or-descendant dotted-path matching, so allowing `channels` also allows `channels.qqbot.enabled`
- rescue plans that exceed those file/key bounds are rejected during dispatch before execution, and execution re-checks the same policy before writing

### Optional real message-loop probe

If you want a stronger, low-false-positive conversation signal, enable the message-loop probe:

- set `WATCHDOG_ENABLE_MESSAGE_LOOP_PROBE=true`
- point `WATCHDOG_MESSAGE_LOOP_PROBE_CHANNEL` and `WATCHDOG_MESSAGE_LOOP_PROBE_TARGET` at a dedicated echo bot or test chat
- set `WATCHDOG_MESSAGE_LOOP_PROBE_EVENTS_FILE` to a JSONL path shared by the watchdog and the OpenClaw hook
- install the sample hook under `openclaw_hooks/message-loop-probe-v1/`

When enabled, the watchdog sends a nonce-tagged probe message and only marks the conversation path ready when it observes a matching echoed nonce in hook events. This is intentionally stricter than the default heuristic probe and is designed to reduce false positives.

## Common commands

Operator quick path for the first live rollout: `detect` -> `check` -> `status --summary` -> `report --message` -> `incidents queue` -> `maintenance on|off`.

For the first real host rollout, follow `detect -> check -> status --summary -> report --message -> ./scripts/openclaw-watchdog-live-acceptance.sh` before enabling unattended timer runs. The fuller step-by-step path lives in `docs/first-deployment.md`.

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

## Experimental macOS launchd path

The repository now includes an experimental macOS `launchd` path for platform-adapter validation:

```bash
scripts/install-openclaw-watchdog-launchd.sh
launchctl print gui/$UID/com.eudonline.openclaw-watchdog
```

Treat this as experimental until live acceptance has been captured on a real macOS host. The narrow supported macOS path in this repo is a user-session `LaunchAgent` in `gui/$UID`; see the [macOS launchd rollout guide](docs/macos-launchd-rollout.md). Linux + `systemd --user` remains the only documented production path today.

## Rehearsal and validation

This repo includes a repo-local rehearsal harness for validating flows without using a live production gateway. The recommended validation order is:

1. fast unit and output-shape tests (`python -m unittest discover -s tests -v`)
2. direct orchestration tests for flows and bootstrap steps
3. bounded rehearsal smoke scenarios under `rehearsal/scripts/run-scenario.sh`
4. live acceptance only after the earlier layers are green

Start with:

- `docs/README.md`
- `docs/release-readiness.md`
- `rehearsal/README.md`
- `docs/live-acceptance-checklist.md`
- `docs/live-samples.md`
- `docs/supported-environments.md`
- `docs/roadmap.md`
- `docs/faq.md`
- `docs/history/migration-legacy-rollout.md` (historical rollout notes)

## Design notes

The fallback system is designed around a few principles:

1. **Repair only after evidence collection**
2. **Prefer reversible changes**
3. **Separate process health from actual usability**
4. **Keep an operator-visible incident trail**
5. **Support staged automation instead of blind restart loops**

## Repository notes

- Canonical CLI wrapper: `scripts/openclaw-watchdog`
- Canonical env example: `config/openclaw-watchdog.env.example`
- Canonical systemd units: `systemd/openclaw-watchdog.service` and `systemd/openclaw-watchdog.timer`
- Internal Python package name remains `openclaw_watchdog` for implementation stability
- Historical migration notes remain in `docs/history/migration-legacy-rollout.md`

## Security

Please do **not** publish live `.env` files, incident bundles, or host-specific status dumps. See [SECURITY.md](SECURITY.md) for reporting guidance and repository hygiene notes.

## Contributing

Contributions, bug reports, and cleanup PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
