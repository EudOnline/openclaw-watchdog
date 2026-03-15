# OpenClaw Watchdog v0.2.0 release runbook

This runbook is the final copy-paste checklist for releasing `v0.2.0`.

Use it together with:

- [release-readiness.md](release-readiness.md) for the gate rationale;
- [release-notes-v0.2.0-draft.md](release-notes-v0.2.0-draft.md) for the release summary text;
- [first-deployment.md](first-deployment.md) and [live-acceptance-checklist.md](live-acceptance-checklist.md) for the real-host validation path.

## Release identity

- Release tag: `v0.2.0`
- Release title: `OpenClaw Watchdog v0.2.0`
- Release target branch: `main`
- Latest published release at the start of this runbook: `v0.1.0`

## 1. Local preflight

Work from a clean checkout after reviewing any intentional local edits:

```bash
git status --short
git branch --show-current
git fetch origin --tags
git tag --list | tail -n 20
```

Expected checks:

- you are on `main` unless you intentionally plan to merge first;
- `v0.1.0` is the latest published tag in this repository;
- there are no unexpected local changes;
- `pyproject.toml` still carries `version = "0.2.0"`.

## 2. Repo-local release gate

Run the repo-local verification steps before touching a real host:

```bash
python3 -m openclaw_watchdog --help
python3 -m unittest tests.test_docs_surface -v
python3 -m unittest discover -s tests -q
bash rehearsal/scripts/run-scenario.sh critical
```

Do not continue if any command fails.

## 3. Real-host conservative rollout gate

On the real supported Linux + `systemd --user` host, run the conservative validation path:

```bash
scripts/openclaw-watchdog detect
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
scripts/openclaw-watchdog status --env config/openclaw-watchdog.env --summary
scripts/openclaw-watchdog report --env config/openclaw-watchdog.env --message
./scripts/openclaw-watchdog-live-acceptance.sh
```

Before trusting the output, confirm these first-rollout toggles remain conservative:

```bash
grep -E 'WATCHDOG_ENABLE_(PRE_REPAIR_BACKUP|SURVIVABILITY_FLOW|SURVIVAL_MODE)=' config/openclaw-watchdog.env
```

Expected values:

- `WATCHDOG_ENABLE_PRE_REPAIR_BACKUP=false`
- `WATCHDOG_ENABLE_SURVIVABILITY_FLOW=false`
- `WATCHDOG_ENABLE_SURVIVAL_MODE=false`

## 4. Evidence capture

Before tagging, capture the real-host acceptance evidence:

```bash
ls -la docs/p7a-live/
```

Manual checks:

- `docs/p7a-live/acceptance-summary.json` shows `all_checks_passed=true`;
- `docs/p7a-live/status-summary.txt` and `docs/p7a-live/report-message.txt` match the expected operator story;
- no host-specific secrets or sensitive dumps are included in anything you plan to publish.

Add a short evidence summary into `docs/release-notes-v0.2.0-draft.md` before publishing.

## 5. Final git checks

Right before tagging:

```bash
git status --short
git log --oneline --decorate -n 5
git diff --stat origin/main..HEAD
```

If `HEAD` is already on the intended release commit and `main` is up to date, push the branch tip first:

```bash
git push origin main
```

## 6. Create and push the release tag

Create the annotated tag:

```bash
git tag -a v0.2.0 -m "OpenClaw Watchdog v0.2.0"
```

Confirm it locally:

```bash
git show --stat v0.2.0
```

Push the tag:

```bash
git push origin v0.2.0
```

## 7. GitHub release body handoff

Use this title in GitHub Releases:

```text
OpenClaw Watchdog v0.2.0
```

Use this body as the starting point, then replace the bracketed evidence note with the real-host acceptance summary from `docs/p7a-live/`:

```markdown
OpenClaw Watchdog `v0.2.0` turns the current fallback path into a clearer release-gated operating surface.

## Highlights

- promote core survivability scenarios into the critical rehearsal gate;
- tighten deterministic recovery markers around rollback, survival, and doctor repair;
- harden structured rescue-plan parsing and clean fallback across the canonical rescue chain;
- align status, report, metrics, and live acceptance wording around the current operator surface;
- publish clearer rollout and release-readiness documentation for Linux + `systemd --user` hosts.

## Support baseline

- Python `3.11+`
- Linux
- `systemd --user`
- OpenClaw already installed on the target host
- rescue executors installed separately if you want those tiers available

## Validation

- `python3 -m unittest discover -s tests -q`
- `bash rehearsal/scripts/run-scenario.sh critical`
- real-host live acceptance via `./scripts/openclaw-watchdog-live-acceptance.sh`
- [replace with one or two sentences summarizing `docs/p7a-live/acceptance-summary.json`]
```

If you prefer, start from [release-notes-v0.2.0-draft.md](release-notes-v0.2.0-draft.md) and paste the refined version into the GitHub release UI.

## 8. Post-publish checks

After the GitHub release is published:

```bash
git ls-remote --tags origin | tail -n 10
```

Then manually confirm:

- the GitHub release page shows `v0.2.0` and the intended notes;
- README release links still make sense relative to the new published tag;
- the rollout host still returns sensible `status --summary` and `report --message` output;
- the accepted `docs/p7a-live/` bundle is archived somewhere your maintainers can find later.

## 9. If something looks wrong

Stop before pushing the tag if any of these are true:

- repo-local tests or critical rehearsal fail;
- live acceptance is missing or non-green;
- `git status --short` contains unexpected changes;
- the release notes still describe behavior that was not actually validated;
- the intended release commit is not on `main`.
