# Documentation index

This directory is split into two layers:

## Current guides

These are the documents new users and operators should start with when treating this repo as the OpenClaw fallback system:

- [internal-architecture.md](internal-architecture.md)
- [upstream-tracking.md](upstream-tracking.md)
- [supported-environments.md](supported-environments.md)
- [first-deployment.md](first-deployment.md)
- [macos-launchd-rollout.md](macos-launchd-rollout.md)
- [release-readiness.md](release-readiness.md)
- [rescue-lifecycle.md](rescue-lifecycle.md)
- [live-acceptance-checklist.md](live-acceptance-checklist.md)
- [reporting-contract.md](reporting-contract.md) — current operational output surface
- [live-samples.md](live-samples.md)
- [roadmap.md](roadmap.md)
- [technical-debt-priority-backlog.md](technical-debt-priority-backlog.md)
- [faq.md](faq.md)

## Release prep

- [release-notes-v0.2.0-draft.md](release-notes-v0.2.0-draft.md)
- [release-v0.2.0-runbook.md](release-v0.2.0-runbook.md)

## Historical notes

These documents are retained only for historical and implementation context:

- [history/migration-legacy-rollout.md](history/migration-legacy-rollout.md)
- [history/watchdog-next-phase-survivability-plan.md](history/watchdog-next-phase-survivability-plan.md)

## Suggested reading order

1. Start with the project [README](../README.md) for the OpenClaw-specific fallback model
2. Confirm the supported baseline in [supported-environments.md](supported-environments.md)
3. Read [first-deployment.md](first-deployment.md) for the safest initial rollout path
4. Read [release-readiness.md](release-readiness.md) if you are preparing a real-host rollout signoff or the next public release
5. Read [rescue-lifecycle.md](rescue-lifecycle.md) for the fixed rescue-chain and mutation-boundary model
6. Read [faq.md](faq.md) if you want the quick orientation version
7. Use [live-acceptance-checklist.md](live-acceptance-checklist.md) and [live-samples.md](live-samples.md) for validation work
8. Read [internal-architecture.md](internal-architecture.md) if you are changing internals or tests
9. Read [upstream-tracking.md](upstream-tracking.md) if you are touching OpenClaw payload parsing or scout automation
10. Read [technical-debt-priority-backlog.md](technical-debt-priority-backlog.md) if you are choosing the next hardening target
11. Read [rehearsal/README.md](../rehearsal/README.md) if you want the repo-local rehearsal flow
12. Use [release-v0.2.0-runbook.md](release-v0.2.0-runbook.md) for the copy-paste release execution path
13. Use [release-notes-v0.2.0-draft.md](release-notes-v0.2.0-draft.md) when assembling the next public release notes
14. Only consult [history/migration-legacy-rollout.md](history/migration-legacy-rollout.md) or `history/` if you need migration background
