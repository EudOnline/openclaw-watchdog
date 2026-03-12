# OpenClaw Watchdog rehearsal harness

This harness exercises the OpenClaw Watchdog source tree in a deterministic, repo-local rehearsal environment.

It still requires a compatible local Python 3.11+ interpreter. The rehearsal helper scripts prepare repo-local command shims for whichever supported `python3.11+` executable names are available on the host.

## What it gives you

- A rehearsal flow that runs directly from this repo checkout.
- Fake `openclaw`, `systemctl`, `journalctl`, `ss`, `ps`, `node`, `opencode`, and optional `codex` shims.
- Scenario setup scripts for bootstrap and watchdog paths.
- No dependency on a real OpenClaw service or on the host machine's OpenClaw state.
- All mutable state lives under `rehearsal/runtime`.

## Layout

- `rehearsal/env/openclaw-watchdog.rehearsal.env`: safe in-repo env file for bootstrap/watchdog runs.
- `rehearsal/bin/`: stable repo-local host-command shims used by the watchdog engine.
- `rehearsal/runtime/system-bin/`: ephemeral host-command links prepared per run for commands discovered on the current machine.
- `rehearsal/shims/`: fake `openclaw`, `opencode`, and `codex` binaries installed into `rehearsal/runtime/bin`.
- `rehearsal/scripts/reset-runtime.sh`: wipe and recreate deterministic runtime state.
- `rehearsal/scripts/apply-scenario.sh`: prepare a named scenario.
- `rehearsal/scripts/run-scenario.sh`: run a named scenario and verify the expected output.
- `rehearsal/scenarios/`: scenario expectations.

Implementation map:
- `watchdog_v2/engine.py` remains the orchestration entrypoint for the unified OpenClaw rescue chain.
- `watchdog_v2/incidents.py` contains incident snapshot/workflow logic delegated from the engine.
- `watchdog_v2/reporting.py` contains report/message/metrics rendering delegated from the engine.
- `watchdog_v2/repair.py` contains repair/rollback helpers delegated from the engine, including manifest-based `last-good` selection.
- `watchdog_v2/health.py` contains service-level probing, conversation-aware probe aggregation, and status shaping delegated from the engine.
- External executors now return structured rescue plans only; host mutation stays inside the local rescue action boundary.

## Run locally

Reset rehearsal state:

```bash
bash rehearsal/scripts/reset-runtime.sh
```

Run a single scripted scenario:

```bash
bash rehearsal/scripts/run-scenario.sh bootstrap-missing-openclaw
bash rehearsal/scripts/run-scenario.sh bootstrap-openclaw-missing-plugin
bash rehearsal/scripts/run-scenario.sh watchdog-recovery
bash rehearsal/scripts/run-scenario.sh watchdog-failed-fallback
bash rehearsal/scripts/run-scenario.sh watchdog-active-no-listener-grace
bash rehearsal/scripts/run-scenario.sh watchdog-service-layer-degraded
bash rehearsal/scripts/run-scenario.sh watchdog-service-layer-threshold-recovery
bash rehearsal/scripts/run-scenario.sh watchdog-conversation-probe-ready
bash rehearsal/scripts/run-scenario.sh watchdog-conversation-probe-minimal
bash rehearsal/scripts/run-scenario.sh watchdog-conversation-probe-down
bash rehearsal/scripts/run-scenario.sh watchdog-restart-priority-recovery
bash rehearsal/scripts/run-scenario.sh watchdog-rollback-priority-before-doctor
bash rehearsal/scripts/run-scenario.sh watchdog-doctor-deferred-until-survival-fails
bash rehearsal/scripts/run-scenario.sh watchdog-recovery-notify-normal
bash rehearsal/scripts/run-scenario.sh watchdog-last-good-generation-selection
bash rehearsal/scripts/run-scenario.sh watchdog-config-invalid-rollback
bash rehearsal/scripts/run-scenario.sh watchdog-incidents-open
bash rehearsal/scripts/run-scenario.sh watchdog-incidents-resolved
bash rehearsal/scripts/run-scenario.sh watchdog-metrics-healthy
bash rehearsal/scripts/run-scenario.sh watchdog-metrics-open-incident
bash rehearsal/scripts/run-scenario.sh watchdog-metrics-resolved
bash rehearsal/scripts/run-scenario.sh watchdog-incident-operator-open
bash rehearsal/scripts/run-scenario.sh watchdog-incident-operator-resolved
bash rehearsal/scripts/run-scenario.sh watchdog-incident-operator-reset
```

Run all scripted scenarios:

```bash
bash rehearsal/scripts/run-scenario.sh all
```

Run the rehearsal entrypoint directly:

```bash
bash rehearsal/entrypoint.sh bootstrap
bash rehearsal/entrypoint.sh bootstrap
bash rehearsal/entrypoint.sh check
bash rehearsal/entrypoint.sh run-once
bash rehearsal/entrypoint.sh status
bash rehearsal/entrypoint.sh report --message
bash rehearsal/entrypoint.sh metrics --json
bash rehearsal/entrypoint.sh metrics --prometheus
bash rehearsal/entrypoint.sh incidents list --state resolved
bash rehearsal/entrypoint.sh incidents current
bash rehearsal/entrypoint.sh incidents assign 20260309-001613 --owner alice
bash rehearsal/entrypoint.sh incidents unassign 20260309-001613
bash rehearsal/entrypoint.sh incidents ack 20260309-001613 --by alice --note "investigating"
bash rehearsal/entrypoint.sh incidents unack 20260309-001613
bash rehearsal/entrypoint.sh incidents note 20260309-001613 --by bob --message "waiting for fallback"
bash rehearsal/entrypoint.sh incidents list --owner alice --ack yes
```

## Scenario coverage

The rehearsal scenarios cover:

- `bootstrap-missing-openclaw`: bootstrap stays detect-only, reports that OpenClaw is missing, and lists the rescue inventory without installing anything.
- `bootstrap-openclaw-missing-plugin`: OpenClaw exists but the required plugin/config wiring is missing, so bootstrap reports the missing setup without trying to mutate the host.
- `watchdog-recovery`: a straightforward unhealthy service becomes healthy after the normal restart path.
- `watchdog-failed-fallback`: the service stays unhealthy through restart/repair attempts, so the watchdog records a failure and fallback context.
- `watchdog-active-no-listener-grace`: the service is active while the listener is still warming up, so the watchdog stays patient instead of immediately restarting.
- `watchdog-service-layer-degraded`: process health looks fine but the service-level probe is still degraded, so status/report output shows the degraded layer clearly.
- `watchdog-service-layer-threshold-recovery`: a transient service-layer failure only triggers recovery after the configured threshold is crossed.
- `watchdog-service-layer-transient-retry`: a temporary service-layer miss recovers before remediation and remains a check-only warning.
- `watchdog-conversation-probe-ready`: both gateway and required channels are conversation-ready, so the conversation probe reports fully healthy.
- `watchdog-conversation-probe-minimal`: the gateway is degraded but the configured minimal usable path still works, so status/report output marks minimal readiness separately from full readiness.
- `watchdog-conversation-probe-down`: neither the gateway nor the minimal path is usable, so the conversation probe fails hard and surfaces the blocking reasons.
- `watchdog-restart-priority-recovery`: the deterministic rescue path prefers a restart first and only escalates if the restart does not restore conversation readiness.
- `watchdog-rollback-priority-before-doctor`: the deterministic rescue path prefers rolling back to `last-good` before invoking doctor repair when drift or bad config is detected.
- `watchdog-doctor-deferred-until-survival-fails`: doctor repair is intentionally deferred until restart, rollback, and survival-mode placeholders all fail.
- `watchdog-survival-mode-recovery`: restart/rollback do not restore the service, so watchdog applies survival mode and recovers a degraded-but-usable conversation path.
- `watchdog-config-drift-guard`: a drifted config differs from the last-good protected-path fingerprints, so watchdog records drift context and rolls back before doctor repair.
- `watchdog-recovery-notify-normal`: after recovery, report/metrics/message outputs surface the recovery path and restored conversation state.
- `watchdog-last-good-generation-selection`: when the newest `last-good` candidate is bad, the manifest falls back to an older validated generation.
- `watchdog-config-invalid-rollback`: invalid config is rolled back from `last-good` and the gateway recovers.
- `watchdog-incidents-open`: failed deterministic remediation is followed by `incidents current --json`, verifying the active incident bundle metadata.
- `watchdog-incidents-resolved`: a failed run is followed by a healthy run, then `incidents show <id> --json` verifies the incident resolved state is queryable.
- `watchdog-metrics-healthy`: a healthy run is followed by `metrics --json`, verifying the normalized export and Prometheus snapshot for a no-incident state.
- `watchdog-metrics-open-incident`: a failed run is followed by `metrics --json`, verifying current open-incident metrics and failed counters.
- `watchdog-metrics-resolved`: a failed run plus a later healthy run is followed by `metrics --json`, verifying resolved-incident metrics and recent counters.
- `watchdog-metrics-operator-context`: a failed/open incident is assigned, acknowledged, and annotated with notes before `metrics --json`, verifying exporter-visible operator context for dashboards/collectors.
- `watchdog-report-operator-attention`: a failed/open incident is left unowned/unacked/without notes, verifying `report --json` and `report --message` surface operator attention prompts.
- `watchdog-report-operator-attention-cleared`: a failed/open incident is then owned, acknowledged, and annotated, verifying operator attention prompts disappear automatically.
- `watchdog-incident-attention-filter`: verifies `incidents list --attention yes|no` plus `show/current/status/report` attention fields move with operator workflow state.
- `watchdog-incident-queue`: verifies `incidents queue` plus `status/report` queue summaries track open-vs-handled triage state.
- `watchdog-incident-operator-open`: a failed run is followed by owner assignment, ack, and note updates; `incidents show --json` verifies workflow metadata persists on an open incident.
- `watchdog-incident-operator-resolved`: a failed run plus healthy recovery is followed by owner assignment, ack, and note updates; `incidents show --json` verifies workflow metadata persists after resolution.
- `watchdog-incident-operator-reset`: an open incident is assigned and acknowledged, then unassigned/unacked; JSON assertions verify owner/ack filters and `report --message` reflect the cleared workflow state while notes remain intact.
- `watchdog-incident-timeline-open`: verifies append-only operator/workflow history is visible through `incidents timeline` for an open incident.
- `watchdog-incident-timeline-resolved`: verifies the timeline keeps both failure/opening context and later resolved context for a recovered incident.
- `watchdog-incident-notes-query`: verifies `--notes yes|no`, timeline limiting, default note truncation, `--notes-all`, and latest-note report/message rendering.

## Notes

- `WATCHDOG_ENABLE_SURVIVABILITY_FLOW` is kept `false` in the shared env files for conservative rollout; the new P0 survivability scenarios enable it explicitly per run.
- `WATCHDOG_ENABLE_SURVIVAL_MODE` is also kept `false` in the shared env files; the new P1 survival-mode rehearsal enables it only inside the scenario process.
- `WATCHDOG_ENABLE_CONVERSATION_PROBE` remains on in rehearsal so conversation/minimal-usable state is always available to assertions.
- `WATCHDOG_GUARD_MANIFEST_FILE` captures drift-guard snapshots and recent before/after validation events for bootstrap, rollback, and survival-mode config rewrites.
- The repo now centers on one OpenClaw-specific rescue flow; rehearsal just constrains it with local shims and fixtures.
- External CLI rescue rehearsal is explicit: each scenario installs only the local shim it needs, and the project no longer relies on automatic software installation.
- `OpenClaw` must already be installed or otherwise available on PATH before the live rescue chain can act on it.
- Expected outputs for stable scenarios live in `rehearsal/scenarios/`.


## Rescue-chain smoke scenarios

The rehearsal harness now treats these rescue-first scenarios as critical smoke coverage:

- `watchdog-rescue-chain-codex`
- `watchdog-rescue-chain-claude-code`
- `watchdog-rescue-chain-gemini-cli`
- `watchdog-rescue-chain-opencode`
- `watchdog-rescue-chain-litellm`
- `watchdog-rescue-chain-rule-agent`
- `watchdog-candidate-rule-auto-promotion`
- `watchdog-candidate-rule-review-pending`

They exercise the post-deterministic rescue chain, the `LiteLLM` specialist tier, the offline rule-agent tier, and the learning/promotion loop without installing extra software.

## Scenario tiers

The rehearsal matrix is now split into two tiers:

- `critical`: the CI release gate for the OpenClaw-specific rescue chain and the learning/promotion loop
- `extended`: slower or broader operator-flow coverage that should still be run before larger releases, but is not required on every CI pass

Recommended commands:

```bash
bash rehearsal/scripts/run-scenario.sh critical
bash rehearsal/scripts/run-scenario.sh extended
bash rehearsal/scripts/run-scenario.sh all
```

For the exact scenario inventory and the rationale for each tier, see `rehearsal/scenarios/README.md`.
