# Upstream tracking

This repository treats OpenClaw as a fast-moving upstream dependency. The goal of upstream tracking is to detect output drift before it becomes an operator-visible regression.

## What we track

- normalized status payload shapes under `tests/fixtures/openclaw_contracts/status`
- doctor help and flag surface under `tests/fixtures/openclaw_contracts/doctor`
- current scout outputs from `scripts/scout-openclaw-upstream.sh`
- scheduled scout execution from `.github/workflows/openclaw-upstream-scout.yml`

## How the fixture corpus is used

The fixture corpus is the replayable contract layer for upstream changes:

- `current.json` captures the shape we expect from the present-day OpenClaw status path
- `legacy.json` preserves a string-heavy or older-style payload shape
- `edge-missing-gateway.json` protects the watchdog from partial or degraded payloads
- doctor help fixtures preserve flag-surface differences such as whether `--non-interactive` and `--yes` are available together

When an upstream regression is discovered, add the failing raw sample to `tests/fixtures/openclaw_contracts/` before changing parser code.

## Scout workflow

Run locally:

```bash
bash scripts/scout-openclaw-upstream.sh
```

The scout writes artifacts to `.tmp/openclaw-upstream-scout` by default. That directory is ignored by git, so local runs do not dirty the working tree.

The script captures:

- `openclaw --help`
- `openclaw doctor --help`
- `openclaw status --json --timeout 5000`
- `openclaw health --json`
- top-level key summaries when JSON output is parseable

If `openclaw` is not available on `PATH`, the script still succeeds and emits metadata plus a `openclaw-missing.txt` marker. This keeps scheduled automation from failing only because the host is missing the binary.

## Scheduled checks

The `.github/workflows/openclaw-upstream-scout.yml` workflow runs on a schedule and by manual dispatch. Its current job is to produce a scout artifact for review, not to hard-fail the main CI gate.

Recommended maintainer workflow:

1. Review the uploaded artifact from the latest scout run.
2. If the payload or flag surface changed, add or update fixtures under `tests/fixtures/openclaw_contracts/`.
3. Adjust `openclaw_watchdog/openclaw_runtime/` normalization only after the new fixture is committed.

This keeps upstream follow-up fast while preventing one-off fixes from bypassing contract coverage.
