# Contributing

Thanks for your interest in improving OpenClaw Watchdog.

## Scope

Good contributions include:

- bug fixes in the watchdog engine
- safer recovery / rollback behavior
- clearer operator reporting
- better rehearsal scenarios and fixtures
- documentation cleanup and installation improvements

## Before opening a PR

1. Read the current README and relevant docs under `docs/`
2. Check whether the behavior is already covered by a rehearsal scenario
3. Keep changes small and focused where possible
4. Avoid committing host-specific paths, live incident bundles, or real credentials

## Development tips

- Main implementation: `watchdog_v2/`
- CLI wrapper: `scripts/openclaw-watchdog`
- Rehearsal harness: `rehearsal/`
- Sample units: `systemd/`

## Safety expectations

Please do not submit changes that:

- remove rollback or incident-safety behavior without strong justification
- hard-code secrets, tokens, hostnames, or operator identifiers
- assume a single host path unless the path is clearly an example
- silently weaken operator visibility or auditability

## Testing

At minimum, contributors should run targeted checks relevant to their change, for example:

```bash
python3 -m py_compile watchdog_v2/*.py
python3 -m watchdog_v2 --help
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env.example
```

If your change touches incident logic, rehearsal flows, or reporting, also run the corresponding rehearsal scripts.

## Pull request guidance

A good PR description should explain:

- what changed
- why it changed
- operational risk
- rollback considerations
- how it was validated

## Security-sensitive changes

If a change touches credentials, notification routing, backup handling, repair automation, or remote execution handoff, please call that out explicitly in the PR.
