# OpenClaw Watchdog v0.2.0 draft release notes

This document is the working draft for the next planned public release. It is not the published announcement yet.

Latest published release: `v0.1.0`

Planned next release: `v0.2.0`

Final execution checklist: [release-v0.2.0-runbook.md](release-v0.2.0-runbook.md)

## Release summary

`v0.2.0` packages the current hardening wave into a more release-gated and operator-trustworthy OpenClaw fallback surface. The main theme is not new recovery primitives. It is tightening the verified path that already exists: stronger critical rehearsal coverage, safer rescue-adapter parsing, clearer deterministic recovery markers, and cleaner rollout guidance for real hosts.

## Highlights

### Release gate and survivability

- promote the core survivability scenarios into the critical rehearsal gate;
- keep the CI path anchored on Python `3.11` and `3.13` with critical rehearsal on the baseline lane;
- make the release story explicitly include live acceptance on a real host rather than stopping at repo-local tests.

### Recovery-path hardening

- clear stale `config_invalid` state after successful rollback or doctor-assisted recovery;
- restart the service after survival-mode activation before the next re-probe;
- keep the recovery order explicit as `restart -> rollback -> survival -> doctor -> rescue`.

### Rescue-chain safety

- keep the canonical rescue chain fixed as `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`;
- reject malformed structured rescue plans more aggressively;
- fall through cleanly when an external adapter returns unusable output.

### Operator-facing consistency

- align `status --summary` with live acceptance wording around `conversation=...`;
- keep report, metrics, and incident outputs focused on the fields that rehearsals, dashboards, and operators still use;
- publish a release readiness guide so rollout signoff and release packaging follow the same checklist.

## Operator notes

- Production-path support remains Linux + `systemd --user` with Python `3.11+`.
- The project is still source-first. Operators should clone the repo and run the shipped scripts rather than expect automatic installation of OpenClaw or rescue executors.
- `detect` and `bootstrap` remain detect-only readiness surfaces. They do not install missing tools.
- Live acceptance stays the last operator-facing gate before trusting unattended timer runs.

## Current repo-local validation snapshot

As of `2026-03-15`, the current release candidate branch has cleared the repo-local gates that can be verified in-repo:

- `python3 -m unittest discover -s tests -q` passed with `Ran 256 tests ... OK`
- `bash rehearsal/scripts/run-scenario.sh critical` passed across the critical scenario set
- focused docs and CI contract checks passed alongside the new `ruff` and `mypy` gates

This is not sufficient for publication yet. Real-host live acceptance and the actual `v0.2.0` tag/release still remain outstanding.

## Validation required before publication

Do not publish these notes as final until the following evidence exists:

- `python -m unittest discover -s tests -v`
- `bash rehearsal/scripts/run-scenario.sh critical`
- one real-host live acceptance pass via `./scripts/openclaw-watchdog-live-acceptance.sh`

When the candidate host pass is available, attach or summarize the relevant `docs/p7a-live/` artifacts here.

Use [release-v0.2.0-runbook.md](release-v0.2.0-runbook.md) when you are ready to turn this draft into the published GitHub release.

## Suggested public release framing

Use language close to this in the published release:

"OpenClaw Watchdog `v0.2.0` turns the current fallback path into a clearer release-gated operating surface. The release strengthens critical rehearsal coverage, deterministic recovery markers, rescue-adapter validation, and first-rollout guidance for real Linux + `systemd --user` hosts."
