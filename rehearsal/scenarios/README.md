# Rehearsal scenario tiers

This directory keeps the bounded scenario fixtures used by the local rehearsal harness.

## Critical tier

These scenarios are the release gate and must stay fast, stable, and directly aligned with the OpenClaw-specific fallback contract:

- `bootstrap-missing-openclaw`
- `watchdog-rescue-chain-codex`
- `watchdog-rescue-chain-claude-code`
- `watchdog-rescue-chain-gemini-cli`
- `watchdog-rescue-chain-opencode`
- `watchdog-rescue-chain-litellm`
- `watchdog-rescue-chain-rule-agent`
- `watchdog-candidate-rule-auto-promotion`
- `watchdog-candidate-rule-review-pending`
- `watchdog-conversation-probe-ready`
- `watchdog-rollback-priority-before-doctor`
- `watchdog-survival-mode-recovery`
- `watchdog-config-drift-guard`

Run locally with:

```bash
bash rehearsal/scripts/run-scenario.sh critical
```

## Extended tier

These scenarios are still valuable, but they are slower, broader, or more operator-workflow-oriented and therefore stay out of the CI release gate:

- `bootstrap-openclaw-missing-plugin`
- `watchdog-recovery`
- `watchdog-failed-fallback`
- `watchdog-active-no-listener-grace`
- `watchdog-service-layer-degraded`
- `watchdog-service-layer-threshold-recovery`
- `watchdog-service-layer-transient-retry`
- `watchdog-conversation-probe-minimal`
- `watchdog-conversation-probe-down`
- `watchdog-restart-priority-recovery`
- `watchdog-doctor-deferred-until-survival-fails`
- `watchdog-survival-mode-sticky-until-stable`
- `watchdog-survival-mode-exit`
- `watchdog-env-drift-rollback`
- `watchdog-plugin-drift-rollback`
- `watchdog-recovery-notify-normal`
- `watchdog-last-good-generation-selection`
- `watchdog-config-invalid-rollback`
- `watchdog-incidents-open`
- `watchdog-incidents-resolved`
- `watchdog-metrics-healthy`
- `watchdog-metrics-open-incident`
- `watchdog-metrics-resolved`
- `watchdog-metrics-operator-context`
- `watchdog-model-http-error-failover`
- `watchdog-report-operator-attention`
- `watchdog-report-operator-attention-cleared`
- `watchdog-incident-attention-filter`
- `watchdog-incident-queue`
- `watchdog-incident-operator-open`
- `watchdog-incident-operator-resolved`
- `watchdog-incident-operator-reset`
- `watchdog-incident-timeline-open`
- `watchdog-incident-timeline-resolved`
- `watchdog-incident-notes-query`

Run locally with:

```bash
bash rehearsal/scripts/run-scenario.sh extended
```

## Full sweep

For a complete bounded local sweep, run:

```bash
bash rehearsal/scripts/run-scenario.sh all
```
