# OpenClaw watchdog v2 migration

## What changed

- The original snapshot remains at `scripts/openclaw-watchdog.sh`.
- The new implementation lives in `watchdog_v2/` and is invoked by `scripts/openclaw-watchdog-v2`.
- The timer/service entrypoint is now a Python CLI with subcommands:
  - `run-once`
  - `check`
  - `status`
  - `report`
  - `metrics`
  - `incidents list|show|current|assign|unassign|ack|unack|note`
  - `bootstrap` / `provision`
  - `maintenance on|off|status`

## Layout

- `watchdog_v2/config.py`: env loading and defaults.
- `watchdog_v2/engine.py`: orchestration shell that wires together health checks, repair flow, rollback, incidents, reporting, and AI handoff.
- `watchdog_v2/incidents.py`: incident snapshot/index/workflow helpers used by the engine.
- `watchdog_v2/reporting.py`: report/message/metrics rendering and snapshot export helpers used by the engine.
- `watchdog_v2/repair.py`: repair/rollback helpers (doctor invocation, last-good backup/restore, rollback summaries, pre-repair backup, service restart helpers) delegated from the engine.
- `watchdog_v2/survival.py`: survival-mode state/config generation and sticky degraded-mode coordination.
- `watchdog_v2/health.py`: service-level probing, live probe aggregation, maintenance/status payload assembly, and last-event loading delegated from the engine.
- `watchdog_v2/handoff.py`: incident evidence bundle creation plus Codex/OpenCode handoff prompt/launcher helpers delegated from the engine.
- `docs/watchdog-v2-live-samples.md`: P7-A real-host read-only acceptance samples for `status` / `report` / `metrics` / `incidents`.
- `docs/watchdog-v2-live-acceptance-checklist.md`: operator checklist for P7-A live read-only acceptance.
- `scripts/openclaw-watchdog-v2-live-acceptance.sh`: one-command live read-only acceptance runner that captures outputs and writes an acceptance summary.
- `docs/p8-summary.md`: P8 incident timeline/query delivery summary.
- `docs/p9-summary.md`: P9 metrics/exporter integration summary for operator/timeline context.
- `watchdog_v2/cli.py`: operator-facing CLI.
- `watchdog_v2/bootstrap.py`: OpenClaw/bootstrap provisioning helpers.
- `config/openclaw-watchdog-v2.env`: v2 environment file.
- `systemd/openclaw-watchdog-v2.service`: sample v2 oneshot service kept in the workspace.
- `systemd/openclaw-watchdog-v2.timer`: sample v2 timer kept in the workspace.
- `scripts/install-openclaw-watchdog-v2-units.sh`: helper to copy the sample units into `~/.config/systemd/user/` and reload systemd.

## Bootstrap flow

- `scripts/openclaw-watchdog-v2 bootstrap --json` now starts by ensuring `opencode` exists.
- If `opencode` is missing, bootstrap automatically runs `OPENCODE_INSTALL_COMMAND` with no extra confirmation. The sample env defaults this to `npm install -g opencode-ai@latest`, but you can replace it with any host-specific installer.
- After `opencode` is available, bootstrap safely ensures a global OpenCode config at `OPENCODE_BOOTSTRAP_CONFIG_PATH` (or `OPENCODE_CONFIG`, or the default `~/.config/opencode/opencode.json`). Existing configs are backed up before edits, JSON and JSONC inputs are accepted, and the default model is forced to `OPENCODE_BOOTSTRAP_MODEL` so there is always a free fallback model configured.
- Bootstrap then reports Codex availability only. It does not install Codex or mutate Codex-specific files.
- After the OpenCode/Codex tooling pass, bootstrap probes whether `openclaw` is available.
- If `openclaw` is missing, the command still exits with a machine-readable `confirmation-required` result and does **not** execute `OPENCLAW_INSTALL_COMMAND` unless you add `--install-openclaw`.
- When OpenClaw is available, the bootstrap flow ensures the QQ plugin with the exact command `openclaw plugins install @sliverp/qqbot@latest`.
- The bootstrap flow then safely scaffolds `channels.qqbot` and `channels.feishu` in `OPENCLAW_CONFIG`, making a timestamped backup first when editing an existing config file.
- If bootstrap credentials are not provided, placeholder values are written and the affected channel stays disabled until you replace them and review the enabled flag.
- The bootstrap command does not touch live systemd units and does not restart the gateway for you; restart it manually after filling placeholders or applying changes.
- Human-readable bootstrap output now ends with a concise `files_changed` summary and the ordered `bootstrap_flow`.

## Bootstrap env knobs

- `OPENCODE_INSTALL_COMMAND`: command bootstrap uses automatically when `opencode` is missing.
- `OPENCODE_BOOTSTRAP_CONFIG_PATH`: target OpenCode config file to create or merge. If unset, bootstrap honors `OPENCODE_CONFIG`, then falls back to `~/.config/opencode/opencode.json`.
- `OPENCODE_BOOTSTRAP_MODEL`: OpenCode default model bootstrap writes into the global config. The sample default is `opencode/minimax-m2.5-free`.
- `OPENCLAW_INSTALL_COMMAND`: required only when you want `bootstrap --install-openclaw` to run a real host install.
- `OPENCLAW_BOOTSTRAP_QQBOT_APP_ID` and `OPENCLAW_BOOTSTRAP_QQBOT_CLIENT_SECRET`: optional values used to prefill `channels.qqbot`.
- `OPENCLAW_BOOTSTRAP_FEISHU_APP_ID` and `OPENCLAW_BOOTSTRAP_FEISHU_APP_SECRET`: optional values used to prefill `channels.feishu`.
- `OPENCLAW_BOOTSTRAP_LOG_FILE`: optional explicit log file for Feishu runtime marker detection.
- `OPENCLAW_BOOTSTRAP_TIMEOUT_SECONDS`: shared timeout for OpenCode install, OpenClaw install, and QQ plugin install shell commands.
- `WATCHDOG_OPENCODE_FALLBACK_BIN`: runtime OpenCode binary used by the watchdog fallback path. On this host we keep it pinned to `/root/.opencode/bin/opencode` for reliability; on other hosts you can switch it to a PATH-resolved `opencode` if that install path is stable.
- `WATCHDOG_ACTIVE_NO_LISTENER_GRACE_SECONDS`: short grace window used when systemd reports the gateway as active but the listener has not yet rebound to the `MainPID`.
- `WATCHDOG_EVENT_HISTORY_FILE`: rolling JSONL event history used by `status` for recent-event observability.
- `WATCHDOG_EVENT_HISTORY_LIMIT`: maximum number of recent events retained in the rolling history file.
- `WATCHDOG_NOTIFY_ON_DEGRADED`: controls whether watchdog sends a notification the first time it enters degraded state.
- `WATCHDOG_INCIDENT_INDEX_FILE`: rolling JSON index for recent incidents.
- `WATCHDOG_INCIDENT_INDEX_LIMIT`: maximum number of incidents retained in the index.
- `WATCHDOG_LAST_REPORT_FILE`: latest compact report snapshot written by the `report` command.
- `WATCHDOG_LAST_METRICS_FILE`: latest normalized metrics snapshot written by the `metrics` command, plus a sibling Prometheus `.prom` export.

## Smoke-testable paths

- Probe-only bootstrap: `scripts/openclaw-watchdog-v2 bootstrap --json`
- Planned bootstrap with OpenCode/OpenClaw changes but no edits: `scripts/openclaw-watchdog-v2 bootstrap --dry-run --install-openclaw --json`
- Planned bootstrap that still preserves OpenClaw confirmation: `scripts/openclaw-watchdog-v2 bootstrap --dry-run --json`
- Real bootstrap after you set an OpenClaw install command if needed: `scripts/openclaw-watchdog-v2 bootstrap --install-openclaw`

## Safe switch plan

1. Review `config/openclaw-watchdog-v2.env` and confirm the paths still match the live host.
2. Dry-run manual checks before changing timers:
   - `scripts/openclaw-watchdog-v2 check`
   - `scripts/openclaw-watchdog-v2 status`
   - `scripts/openclaw-watchdog-v2 bootstrap --dry-run --json`
3. If you want to suppress Codex autorun during rollout, enable maintenance first:
   - `scripts/openclaw-watchdog-v2 maintenance on --reason "v2 rollout"`
4. Install the sample units by copying the files from `systemd/` into the real user unit directory, or use:
   - `scripts/install-openclaw-watchdog-v2-units.sh`
5. Reload and switch timers carefully:
   - `systemctl --user daemon-reload`
   - `systemctl --user disable --now openclaw-watchdog.timer`
   - `systemctl --user enable --now openclaw-watchdog-v2.timer`
6. Run one manual service start and inspect logs:
   - `systemctl --user start openclaw-watchdog-v2.service`
   - `journalctl --user -u openclaw-watchdog-v2.service -n 100 --no-pager`
7. After the first healthy v2 runs, turn maintenance back off if you enabled it:
   - `scripts/openclaw-watchdog-v2 maintenance off`

## Compatibility notes

- State file names, rollback archives, failure counts, maintenance mode, and incident bundle concepts are preserved.
- The repair order remains the same in spirit: pre-repair backup, rollback if config is invalid, doctor repair, restart, then incident + AI handoff.
- Codex stays the primary autorun path when it is installed and configured; OpenCode remains the fallback path.
- Bootstrap now prepares OpenCode earlier so a free model is configured before the watchdog ever needs the fallback path.
- Cooldowns and failure thresholds stay env-configurable with the same variable names.
- Event metadata is now written as both the legacy text format (`last-event.txt`, `incident-meta.txt`) and JSON companions (`last-event.json`, `incident-meta.json`) for easier automation.
- v2 also keeps a rolling JSONL event history so `status` can surface recent incidents/recoveries without reading the full log.
- `status` now computes a 24h recent-event summary (`recent_event_stats`) including degraded/recovered/failed counts, healthy streak info, longest healthy gap, and last recovery duration.
- Survival mode is now a first-class degraded recovery path: when restart/rollback still cannot restore a minimal usable conversation path, watchdog can apply a conservative channel-minimized config and surface the mode/reason/actions in `status`, `report`, `report --message`, and `metrics`.
- Drift guard now records before/after protected-path snapshots in `WATCHDOG_GUARD_MANIFEST_FILE`, carries protected-path fingerprints in last-good generations, and exposes drift scope/baseline metadata in `status` / `report` / `metrics`.
- Incident bundles now include `operator-summary.txt` so an operator can read the high-level failure context without digging through every artifact.
- v2 also maintains a rolling `incident-index.json`, and `status` can surface recent incidents directly.
- `incidents list|show|current` are now available for direct incident-bundle inspection, including open vs resolved lifecycle state plus artifact listings for operator workflows.
- `status --summary` provides a compact single-line snapshot suitable for cron, notifications, or dashboards.
- `report` is a new compact operator/machine-friendly subcommand that focuses on current health plus recent incident summaries.
- `report --message` emits a message-ready multiline summary, and each `report` run also refreshes `last-report.json` plus a sibling text snapshot for downstream consumers.
- `metrics --json` exposes a normalized machine-friendly snapshot of current state, counters, cooldowns, recent 24h aggregates, and incident status.
- `metrics --prometheus` writes the same state as Prometheus text exposition and refreshes `last-metrics.json` plus a sibling `last-metrics.prom` snapshot for dashboard/collector consumers.
- Metrics/exporter output now also includes current-incident operator context (`owner assigned`, `acknowledged`, `notes count`, `events count`) so dashboards can distinguish untouched incidents from actively handled ones without parsing full bundles.
- Incident operator workflow metadata is now persisted per incident in `operator-workflow.json`: owner assignment, acknowledgement, and appended operator notes survive across `open -> resolved` lifecycle transitions.
- New CLI workflow commands are available: `incidents assign <id> --owner <name>`, `incidents unassign <id>`, `incidents ack <id> --by <name> [--note ...]`, `incidents unack <id>`, and `incidents note <id> --by <name> --message ...`.
- `incidents list` now supports `--owner <name>` and `--ack all|yes|no` filtering for operator views.
- `incidents list/show/current`, plus `status` / `report` recent incident lines and `report --message`, now surface owner/ack metadata so operators can see whether an incident has already been picked up.
- Recent incident summaries now preserve resolved-state transitions, so a previously failed incident can later appear as `resolved | healthy` in reports without losing the original bundle artifacts.
- State-change notifications now reuse the same message-ready report body, so degraded/recovered/failed alerts and `last-report.*` stay aligned.
- `report --message` now adds operator attention prompts for open incidents that are still unowned, unacknowledged, or missing notes; those prompts disappear automatically once the workflow state shows the incident has been picked up.
- Incident queue views now also expose and filter the same triage state: `incidents list --attention yes|no` plus `show/current/status/report` attention fields make “needs pickup vs already handled” visible without opening full bundles.
- A first-class `incidents queue` view and matching `status/report` queue summary counters now expose open/attention/handled totals directly, turning incident triage into a readable operator queue instead of just a filtered list.
- Last-event payloads now include `severity` and `human_summary` fields for more operator-friendly alerting.
- Health probing now includes a short configurable grace window before treating an active-but-not-yet-listening gateway as unhealthy.

## Known differences

- `check` is new and does not mutate state.
- `status` is new and combines live checks with persisted watchdog state.
- `bootstrap` now auto-installs/configures OpenCode, reports Codex availability, and only asks for explicit confirmation when OpenClaw itself is missing.
- v2 always prepares incident directories on failed deterministic remediation so the bundle exists even when operator workflows change later.
