# Compatibility and deprecations

This repository now presents a single public-facing product name: **OpenClaw Watchdog**.

This document is for migration clarity. New users should follow the canonical entrypoints below and can ignore the deprecated shim names.

## Canonical entrypoints

Use these for all new documentation, examples, and deployments:

- CLI wrapper: `scripts/openclaw-watchdog`
- Example config: `config/openclaw-watchdog.env.example`
- Sample systemd service: `systemd/openclaw-watchdog.service`
- Sample systemd timer: `systemd/openclaw-watchdog.timer`
- Live acceptance helper: `scripts/openclaw-watchdog-live-acceptance.sh`
- Rehearsal env file: `rehearsal/env/openclaw-watchdog.rehearsal.env`

## Deprecated compatibility shims

These are still kept for migration, but should not be used in new docs or new installations:

- `scripts/openclaw-watchdog-v2`
- `scripts/install-openclaw-watchdog-v2-units.sh`
- `scripts/openclaw-watchdog-v2-live-acceptance.sh`

They currently print a deprecation warning and delegate to the canonical non-`v2` scripts.

## Intentionally retained historical naming

The internal Python package name remains:

- `watchdog_v2`

This is intentional. Renaming the package would create unnecessary churn across imports, rehearsal tooling, and historical implementation notes without improving the public user experience.

## Removed from the primary public surface

These duplicate public-facing files were removed so the repository has one obvious installation path:

- `config/openclaw-watchdog-v2.env.example`
- `systemd/openclaw-watchdog-v2.service`
- `systemd/openclaw-watchdog-v2.timer`

## Historical docs

`MIGRATION-v2.md` is retained as a historical migration record. Its filename is intentionally unchanged.
