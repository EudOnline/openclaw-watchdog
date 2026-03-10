# OpenClaw Watchdog v2

External watchdog + incident workflow for OpenClaw, with:
- Python watchdog engine (`watchdog_v2/`)
- CLI launcher (`scripts/openclaw-watchdog-v2`)
- sample systemd user units (`systemd/`)
- rehearsal fixtures and scenario scripts (`rehearsal/`)
- migration / acceptance docs (`docs/`, `MIGRATION-v2.md`)

## What is included
This public repo is a curated export of the watchdog project only.
It intentionally excludes private workspace files, live incident data, memory files, and real `.env` configs.

## Quick start
```bash
cp config/openclaw-watchdog-v2.env.example config/openclaw-watchdog-v2.env
chmod +x scripts/openclaw-watchdog-v2 scripts/install-openclaw-watchdog-v2-units.sh
scripts/openclaw-watchdog-v2 --help
```

## Install sample user units
The sample unit assumes this repo lives at `~/openclaw-watchdog-v2`.
```bash
git clone <this-repo-url> ~/openclaw-watchdog-v2
cd ~/openclaw-watchdog-v2
scripts/install-openclaw-watchdog-v2-units.sh
systemctl --user enable --now openclaw-watchdog-v2.timer
```

## Notes
- `systemd/openclaw-watchdog-v2.service` is a sample unit built around `~/openclaw-watchdog-v2`.
- The example env file is sanitized and intended as a starting point only.
- No license file is included yet.
