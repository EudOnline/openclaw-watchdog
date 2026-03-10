# OpenClaw Watchdog Docker rehearsal harness

This harness wraps the existing `watchdog_v2` bootstrap/watchdog code with a deterministic container-safe rehearsal environment.

## What it gives you

- A Docker image that runs entirely inside this repo copy.
- Fake `openclaw`, `systemctl`, `journalctl`, `ss`, `ps`, `node`, `opencode`, and optional `codex` shims.
- Scenario setup scripts for bootstrap and watchdog paths.
- No dependency on a real OpenClaw service or on the host machine's OpenClaw state.
- All mutable state lives under `rehearsal/runtime`.

## Layout

- `Dockerfile`: container image for the rehearsal environment.
- `compose.yaml`: optional compose wrapper.
- `rehearsal/env/openclaw-watchdog.rehearsal.env`: safe in-repo env file for bootstrap/watchdog runs.
- `rehearsal/bin/`: host-command shims used by the watchdog engine.
- `rehearsal/shims/`: fake `openclaw`, `opencode`, and `codex` binaries installed into `rehearsal/runtime/bin`.
- `rehearsal/scripts/reset-runtime.sh`: wipe and recreate deterministic runtime state.
- `rehearsal/scripts/apply-scenario.sh`: prepare a named scenario.
- `rehearsal/scripts/run-scenario.sh`: run a named scenario and verify the expected output.
- `rehearsal/scenarios/`: scenario expectations.

Current P0/P6-C structure note:
- `watchdog_v2/engine.py` remains the orchestration entrypoint and now supports a survivability-first recovery flow behind a feature flag.
- `watchdog_v2/incidents.py` contains incident snapshot/workflow logic delegated from the engine.
- `watchdog_v2/reporting.py` contains report/message/metrics rendering delegated from the engine.
- `watchdog_v2/repair.py` contains repair/rollback helpers delegated from the engine, including manifest-based `last-good` selection.
- `watchdog_v2/health.py` contains service-level probing, conversation-aware probe aggregation, and status shaping delegated from the engine.
- `watchdog_v2/handoff.py` contains incident evidence bundle plus Codex/OpenCode handoff helpers delegated from the engine.

## Build later on a Docker-capable machine

```bash
docker build -t openclaw-watchdog-rehearsal .
```

## Run later with plain Docker

Interactive shell in the rehearsal image:

```bash
docker run --rm -it openclaw-watchdog-rehearsal
```

Run a single scripted scenario:

```bash
docker run --rm -it openclaw-watchdog-rehearsal scenario bootstrap-missing-openclaw
docker run --rm -it openclaw-watchdog-rehearsal scenario bootstrap-openclaw-missing-plugin
docker run --rm -it openclaw-watchdog-rehearsal scenario bootstrap-install-openclaw
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-recovery
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-failed-fallback
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-active-no-listener-grace
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-service-layer-degraded
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-service-layer-threshold-recovery
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-conversation-probe-ready
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-conversation-probe-minimal
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-conversation-probe-down
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-restart-priority-recovery
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-rollback-priority-before-doctor
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-doctor-deferred-until-survival-fails
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-recovery-notify-normal
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-last-good-generation-selection
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-config-invalid-rollback
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-incidents-open
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-incidents-resolved
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-metrics-healthy
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-metrics-open-incident
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-metrics-resolved
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-incident-operator-open
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-incident-operator-resolved
docker run --rm -it openclaw-watchdog-rehearsal scenario watchdog-incident-operator-reset
```

Run all scripted scenarios:

```bash
docker run --rm -it openclaw-watchdog-rehearsal scenario all
```

Run the watchdog/bootstrap CLI directly in the container:

```bash
docker run --rm -it openclaw-watchdog-rehearsal bootstrap
docker run --rm -it openclaw-watchdog-rehearsal bootstrap --install-openclaw
docker run --rm -it openclaw-watchdog-rehearsal check
docker run --rm -it openclaw-watchdog-rehearsal run-once
docker run --rm -it openclaw-watchdog-rehearsal status
docker run --rm -it openclaw-watchdog-rehearsal report --message
docker run --rm -it openclaw-watchdog-rehearsal metrics --json
docker run --rm -it openclaw-watchdog-rehearsal metrics --prometheus
docker run --rm -it openclaw-watchdog-rehearsal incidents list --state resolved
docker run --rm -it openclaw-watchdog-rehearsal incidents current
docker run --rm -it openclaw-watchdog-rehearsal incidents assign 20260309-001613 --owner alice
docker run --rm -it openclaw-watchdog-rehearsal incidents unassign 20260309-001613
docker run --rm -it openclaw-watchdog-rehearsal incidents ack 20260309-001613 --by alice --note "investigating"
docker run --rm -it openclaw-watchdog-rehearsal incidents unack 20260309-001613
docker run --rm -it openclaw-watchdog-rehearsal incidents note 20260309-001613 --by bob --message "waiting for fallback"
docker run --rm -it openclaw-watchdog-rehearsal incidents list --owner alice --ack yes
docker run --rm -it openclaw-watchdog-rehearsal maintenance on --reason "rehearsal"
```

If you want container writes to appear in your local checkout, bind-mount the repo:

```bash
docker run --rm -it -v "$PWD:/workspace" openclaw-watchdog-rehearsal scenario all
```

## Run later with Compose

```bash
docker compose run --rm rehearsal scenario all
docker compose run --rm rehearsal bootstrap
```

## Supported rehearsal paths

- `bootstrap-missing-openclaw`: `opencode` auto-installs, OpenClaw stays confirmation-required.
- `bootstrap-openclaw-missing-plugin`: OpenClaw exists, QQ plugin gets installed, QQ/Feishu config is scaffolded.
- `bootstrap-install-openclaw`: same as above, but exercises the explicit `--install-openclaw` path.
- `watchdog-recovery`: watchdog repairs and restarts the simulated gateway.
- `watchdog-failed-fallback`: deterministic remediation fails, Codex is detect-only/missing, OpenCode fallback launches.
- `watchdog-active-no-listener-grace`: a short active-without-listener window is tolerated and settles healthy without remediation.
- `watchdog-service-layer-degraded`: process layer stays healthy, service layer degrades, threshold is not met, and watchdog reports degraded without remediation.
- `watchdog-service-layer-threshold-recovery`: service layer degrades across the configured threshold, watchdog remediates, and the service recovers.
- `watchdog-conversation-probe-ready`: the gateway is reachable and the conversation path is fully ready.
- `watchdog-conversation-probe-minimal`: optional conversation targets fail, but the minimal usable path is still available.
- `watchdog-conversation-probe-down`: the service looks partially alive, but the conversation path is not usable and `check --json` exits non-zero.
- `watchdog-restart-priority-recovery`: the survivability flow restores conversation through restart before considering rollback or doctor repair.
- `watchdog-rollback-priority-before-doctor`: restart is insufficient, so the survivability flow rolls back to `last-good` before attempting doctor repair.
- `watchdog-doctor-deferred-until-survival-fails`: doctor repair is deferred until restart, rollback, and survival-mode placeholders all fail.
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
- The real repo code is unchanged in host behavior until the survivability flow flag is enabled.
- `Codex` stays detect-only unless you manually install the rehearsal shim with `rehearsal/scripts/install-codex-shim.sh` for experiments.
- `OpenCode` can auto-install in bootstrap because `OPENCODE_INSTALL_COMMAND` points to the local shim installer.
- `OpenClaw` still requires explicit `--install-openclaw` before the local shim installer runs.
- Expected outputs for stable scenarios live in `rehearsal/scenarios/`.
