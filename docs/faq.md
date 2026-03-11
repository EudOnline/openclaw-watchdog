# FAQ

## Why is the repository called OpenClaw Watchdog but the Python package is still `watchdog_v2`?

Because the public project name and the internal implementation name solve different problems. The repo, scripts, systemd units, and docs now use **OpenClaw Watchdog**. The internal package name remains `watchdog_v2` to avoid unnecessary churn across imports, rehearsal tooling, and historical implementation notes.

## Should I use the `-v2` scripts?

No for new usage. New installs and new docs should use:

- `scripts/openclaw-watchdog`
- `scripts/install-openclaw-watchdog-units.sh`
- `scripts/openclaw-watchdog-live-acceptance.sh`

The `-v2` scripts remain only as migration shims.

## Why does `scripts/openclaw-watchdog --help` ask for Python 3.11+?

The project requires Python 3.11 or newer. The wrapper script now checks the interpreter before importing `watchdog_v2`, so on hosts that only have older Python versions you should see a short requirement message instead of a traceback. It prefers discovered `python3.11`, `python3.12`, `python3.13`, or a compatible `python3`.

You can either install Python 3.11+ or run the module explicitly with a compatible interpreter, for example `python3.11 -m watchdog_v2 --help`.

## Is this meant to be installed from PyPI?

Not today. The current release shape is source-first: clone the repo, copy the example env file, and run the scripts or Python module entrypoint from the checkout.

## Does this replace OpenClaw itself?

No. It is an external watchdog and recovery toolkit for OpenClaw. You still need OpenClaw installed on the target machine.

## Is this only for Linux + systemd?

The included sample deployment path is oriented around Linux with `systemd --user`. The core Python code and rehearsal harness are useful beyond that, but the documented operational path currently centers on Linux hosts.

## Where should I start?

A good reading order is:

1. `README.md`
2. `docs/README.md`
3. `docs/compatibility-and-deprecations.md`
4. `docs/first-deployment.md`
5. `docs/live-acceptance-checklist.md`
6. `rehearsal/README.md`

If you just want the operator quick path, use `detect`, `check`, `status --summary`, `report --message`, and `incidents queue` before enabling unattended runs.

## Are the incident and reporting features the main point of the project?

They matter, but the project’s main purpose is recovery: restoring a usable OpenClaw conversation path safely and quickly. Incident, metrics, and reporting features exist to support that operational goal.
