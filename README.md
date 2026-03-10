# OpenClaw Watchdog

A production-oriented external watchdog for OpenClaw, focused on service recovery, incident capture, operator workflow, and rehearsal-driven validation.

> This repository publishes the watchdog project as a standalone, sanitized open-source package. Private workspace state, live incidents, memory files, and real credentials are intentionally excluded.

## Highlights

- **External watchdog loop** for OpenClaw gateway health and remediation
- **Layered health model**: process, service probe, and conversation readiness
- **Incident workflow** with queueing, ownership, acknowledgement, notes, and timelines
- **Safety rails** for rollback, drift detection, and repair sequencing
- **Bootstrap / fallback helpers** for OpenClaw, Codex, and OpenCode handoff flows
- **Rehearsal scenarios** for testing expected failure and recovery paths
- **Systemd user units** for unattended timer-based execution on Linux

## Status

This repo packages the newer Python watchdog engine. Internally the module name remains `watchdog_v2` for compatibility with the original workspace history, but the project and repo name are now simply **OpenClaw Watchdog**.

## Repository layout

```text
watchdog_v2/   Python implementation
scripts/       CLI wrappers and install helpers
systemd/       sample user service + timer units
docs/          migration notes, samples, acceptance checklists
config/        sanitized example env files
rehearsal/     fixtures, shims, scenarios, and test flows
```

## Requirements

- Python 3.11+
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
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
```

### Option 2: Python entrypoint

A lightweight `pyproject.toml` is included so the package can be installed or invoked as a Python project:

```bash
python3 -m watchdog_v2 --help
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

The example config is intentionally sanitized. You must set values appropriate for your own host.

## Common commands

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

This repo includes a rehearsal harness for validating flows without using a live production gateway.

Start with:

- `rehearsal/README.md`
- `docs/live-acceptance-checklist.md`
- `docs/live-samples.md`
- `MIGRATION-v2.md`

## Design notes

The watchdog is designed around a few principles:

1. **Repair only after evidence collection**
2. **Prefer reversible changes**
3. **Separate process health from actual usability**
4. **Keep an operator-visible incident trail**
5. **Support staged automation instead of blind restart loops**

## Compatibility notes

- Canonical CLI wrapper: `scripts/openclaw-watchdog`
- Canonical env example: `config/openclaw-watchdog.env.example`
- Canonical systemd units: `systemd/openclaw-watchdog.service` and `systemd/openclaw-watchdog.timer`
- Internal Python package name remains `watchdog_v2` for implementation stability
- Deprecated compatibility shims are still shipped for migration:
  - `scripts/openclaw-watchdog-v2`
  - `scripts/install-openclaw-watchdog-v2-units.sh`
  - `scripts/openclaw-watchdog-v2-live-acceptance.sh`
- Historical migration notes remain in `MIGRATION-v2.md`
- See also: [docs/compatibility-and-deprecations.md](docs/compatibility-and-deprecations.md)

## Security

Please do **not** publish live `.env` files, incident bundles, or host-specific status dumps. See [SECURITY.md](SECURITY.md) for reporting guidance and repository hygiene notes.

## Contributing

Contributions, bug reports, and cleanup PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
