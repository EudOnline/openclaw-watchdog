# Release readiness

This guide closes the gap between "the repo tests are green" and "the next OpenClaw Watchdog release is actually safe to publish and roll out on a real host."

The current planned next release is `v0.2.0`.

If you are ready for the final copy-paste execution path, use [release-v0.2.0-runbook.md](release-v0.2.0-runbook.md). This guide stays focused on the gate and decision points; the runbook is the step-by-step operator-maintainer checklist.

## What this guide is for

Use this guide when you need to:

- sign off a real-host rollout candidate;
- gather evidence for the next public release;
- confirm that repo-local validation, live acceptance, and release notes all describe the same product behavior.

This guide assumes the current support baseline from [supported-environments.md](supported-environments.md): Python 3.11+, Linux, `systemd --user`, and a host that already has OpenClaw plus any desired rescue executors installed.

If you are validating the experimental macOS adapter path, keep the scope to the narrow `LaunchAgent` contract documented in [macos-launchd-rollout.md](macos-launchd-rollout.md): user-session `gui/$UID`, explicit `launchd` labels, and release evidence before any wider support claim.

## Release gate order

Keep the gate in this order. Do not skip ahead to tagging or publishing.

1. repo-local validation
2. critical rehearsal validation
3. real-host conservative rollout and live acceptance
4. release packaging
5. post-release follow-up

## 1. Repo-local validation

Before touching a real host, run the same core checks the repository treats as release-gated:

```bash
python -m openclaw_watchdog --help
python -m unittest tests/test_cli_smoke.py -v
python -m unittest discover -s tests -v
python -m py_compile openclaw_watchdog/*.py openclaw_watchdog/presenters/*.py openclaw_watchdog/flows/*.py rehearsal/lib/*.py rehearsal/tools/*.py tests/*.py
```

Expectations:

- the CLI help path works on Python `3.11+`;
- the full `unittest` suite passes cleanly;
- byte compilation succeeds for shipped modules, rehearsal helpers, and tests;
- `CHANGELOG.md`, `README.md`, and current docs still describe the same OpenClaw fallback surface.

## 2. Critical rehearsal validation

Run the bounded critical rehearsal tier before treating a candidate as releasable:

```bash
bash rehearsal/scripts/run-scenario.sh critical
```

This is the critical rehearsal gate for the current product contract. It should keep proving:

- canonical rescue-chain selection across `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`;
- conversation-aware readiness checks;
- rollback-before-doctor behavior;
- survival-mode recovery;
- config-drift protection.

If a change only affects docs, still confirm that the current documented gate is the same one CI and rehearsal are enforcing.

## 3. Real-host rollout and live acceptance

Follow [first-deployment.md](first-deployment.md) on a real Linux + `systemd --user` host that already has OpenClaw installed.

Keep the first candidate rollout conservative:

- `WATCHDOG_ENABLE_PRE_REPAIR_BACKUP=false`
- `WATCHDOG_ENABLE_SURVIVABILITY_FLOW=false`
- `WATCHDOG_ENABLE_SURVIVAL_MODE=false`

Run the host gate in this order:

```bash
scripts/openclaw-watchdog detect
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
scripts/openclaw-watchdog status --env config/openclaw-watchdog.env --summary
scripts/openclaw-watchdog report --env config/openclaw-watchdog.env --message
./scripts/openclaw-watchdog-live-acceptance.sh
```

Release evidence is not complete until live acceptance passes. Keep the generated `docs/p7a-live/` artifacts from the candidate host so the release summary can point at concrete evidence.

## 4. Release packaging

After the repo gate and live acceptance are both green:

1. confirm `pyproject.toml` carries the intended release version;
2. move or summarize the relevant `CHANGELOG.md` entries into the public release announcement;
3. update [release-notes-v0.2.0-draft.md](release-notes-v0.2.0-draft.md) with host-specific evidence and any operator cautions;
4. make sure README quick links still point to the correct published release and the next planned release draft;
5. cut the Git tag and publish the release only after the evidence above is attached or referenced.

For the exact commands, Git tag, and release body handoff, use [release-v0.2.0-runbook.md](release-v0.2.0-runbook.md).

The release announcement should call out:

- Python `3.11+` baseline;
- Linux + `systemd --user` production path;
- detect-only bootstrap posture;
- fixed rescue-chain order;
- live acceptance as the last operator-facing gate.

## 5. Post-release follow-up

Immediately after publishing:

- verify that the GitHub release page points at the intended tag and notes;
- run one more `status --summary` and `report --message` check on the rollout host;
- archive the accepted `docs/p7a-live/` bundle alongside the release notes or release issue;
- watch early operator feedback for gaps between docs, status output, and real-host behavior.

## Exit criteria for `v0.2.0`

Treat `v0.2.0` as ready only when all of these are true:

- repo-local validation is green;
- the critical rehearsal tier is green;
- live acceptance passed on a real supported host;
- release notes describe the actual validated behavior;
- README, docs, and `CHANGELOG.md` all point at the same rollout and support story.
