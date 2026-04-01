# FAQ

## Why is the repository called OpenClaw Watchdog but the Python package is still `openclaw_watchdog`?

Because the public project name and the internal implementation name solve different problems. The repo, scripts, systemd units, and docs now describe the OpenClaw fallback system as **OpenClaw Watchdog**. The internal package name remains `openclaw_watchdog` because that is the stable implementation namespace.

## Should I use any legacy wrapper scripts?

No. The supported command surface is:

- `scripts/openclaw-watchdog`
- `scripts/install-openclaw-watchdog-units.sh`
- `scripts/openclaw-watchdog-live-acceptance.sh`

## Why does `scripts/openclaw-watchdog --help` ask for Python 3.11+?

The project requires Python 3.11 or newer. The wrapper script now checks the interpreter before importing `openclaw_watchdog`, so on hosts that only have older Python versions you should see a short requirement message instead of a traceback. It prefers discovered `python3.11`, `python3.12`, `python3.13`, or a compatible `python3`.

You can either install Python 3.11+ or run the module explicitly with a compatible interpreter, for example `python3.11 -m openclaw_watchdog --help`.

## Is this meant to be installed from PyPI?

Not today. The current release shape is source-first: clone the repo, copy the example env file, and run the scripts or Python module entrypoint from the checkout.

## Does this replace OpenClaw itself?

No. It is an external OpenClaw fallback system. You still need OpenClaw installed on the target machine.

## Will it install Codex, Claude Code, Gemini CLI, OpenCode, or LiteLLM for me?

No. The supported operating model is detect-only for tool availability. The fallback system inventories what is already installed, then uses the configured rescue order: `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`.

If a tier is not installed or not configured, watchdog skips it and continues to the next tier. This is intentional: operators stay in control of what software exists on the host.

## Is this only for Linux + systemd?

The included sample deployment path is oriented around Linux with `systemd --user`. The core Python code and rehearsal harness are useful beyond that, but the documented operational path currently centers on Linux hosts.

## How cautious is the watchdog during planned OpenClaw upgrades?

By default it is intentionally patient. The example config and built-in defaults now favor showing `degraded` while delaying entry into failure-driven repair. On Linux, the bundled timer runs every 5 minutes, and the default `WATCHDOG_SERVICE_LEVEL_FAILURE_THRESHOLD=6` means a planned rollout can stay degraded for about 30 minutes before the watchdog escalates into the more aggressive failure path.

If your rollout windows are shorter and you want faster unattended intervention, you can lower the service retry grace and failure threshold. If planned upgrades can legitimately take 20-30 minutes, keep the defaults or make them even more tolerant.

## What keeps model failover from switching forever?

Two guards bound the automatic model rewrite path:

- `WATCHDOG_MODEL_HTTP_ERROR_COOLDOWN_SECONDS` prevents another switch immediately after a recent apply;
- `WATCHDOG_MODEL_FAILOVER_MAX_APPLIES_PER_DAY` caps the number of automatic rewrites in a rolling 24-hour window and reports `rate-limited` when the cap is reached.

Operators can watch this path through `status --summary`, `report --message`, `report --json`, `metrics --json`, and `metrics --prometheus`.

## How do I turn model failover off quickly?

Set:

```bash
WATCHDOG_ENABLE_MODEL_HTTP_ERROR_FAILOVER="false"
```

Then restart or reload the watchdog service. Future runs will stop rewriting the OpenClaw primary model, while the rest of the deterministic recovery chain stays available.

## Where should I start?

A good reading order is:

1. `README.md`
2. `docs/README.md`
3. `docs/first-deployment.md`
4. `docs/live-acceptance-checklist.md`
5. `rehearsal/README.md`
6. `docs/history/migration-legacy-rollout.md` if you need old rollout context

If you just want the operator quick path, use `detect`, `check`, `status --summary`, `report --message`, and `incidents queue` before enabling unattended runs.

For the first live host rollout, add `./scripts/openclaw-watchdog-live-acceptance.sh` before you enable or trust unattended timer runs.

## Are the incident and reporting features the main point of the project?

They matter, but the project’s main purpose is fallback recovery: restoring a usable OpenClaw conversation path safely and quickly. Incident, metrics, and reporting features exist to support that operational goal, not to turn the project into a generic watchdog platform.
