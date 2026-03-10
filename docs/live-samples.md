# OpenClaw Watchdog live samples

Generated: 2026-03-09 10:24 CST
Scope: P7-A real-host read-only acceptance for OpenClaw Watchdog (`watchdog_v2` internals)
Source files: `docs/p7a-live/*`

## One-command acceptance

```bash
./scripts/openclaw-watchdog-live-acceptance.sh
```

See also:
- `docs/live-acceptance-checklist.md`
- raw outputs under `docs/p7a-live/`
- refreshed P9 acceptance outputs under `docs/p9-live/`

## Underlying acceptance commands

```bash
./scripts/openclaw-watchdog status --summary
./scripts/openclaw-watchdog status --json
./scripts/openclaw-watchdog report --message
./scripts/openclaw-watchdog report --json --limit 3
./scripts/openclaw-watchdog metrics --json
./scripts/openclaw-watchdog metrics --prometheus
./scripts/openclaw-watchdog incidents list --limit 5
./scripts/openclaw-watchdog incidents current --json
openclaw status
```

## Observed live state

Current host was in a clean healthy window during acceptance:

- watchdog status: `healthy`
- health level: `healthy`
- current mode: `normal`
- service probe: `gateway.reachable=true`
- consecutive failures: `0`
- current incident: none
- recent incidents: `0`
- 24h recent counts: `healthy=20 degraded=0 recovered=0 failed=0`
- metrics timestamp sample: `last_success_timestamp=1773022797`

## Sample: `status --summary`

```text
status=healthy | health=healthy | mode=normal | service=true | probe=gateway.reachable=true | recent=healthy:20,degraded:0,recovered:0,failed:0 | incident_tail=none | last=watchdog 健康检查正常：service active and listener matches main pid
```

## Sample: `report --message`

```text
OpenClaw watchdog：healthy / healthy / mode=normal
service_active=true | probe=gateway.reachable=true
24h recent：healthy=20 degraded=0 recovered=0 failed=0
last_event：watchdog 健康检查正常：service active and listener matches main pid
recent_incidents: none
attention: none
```

## Sample: `metrics --json` highlights

```json
{
  "status": "healthy",
  "health_level": "healthy",
  "current_mode": "normal",
  "service_active": true,
  "process_layer_healthy": true,
  "service_layer_healthy": true,
  "service_probe_summary": "gateway.reachable=true",
  "consecutive_failures": 0,
  "recent_healthy_total": 20,
  "recent_degraded_total": 0,
  "recent_recovered_total": 0,
  "recent_failed_total": 0,
  "recent_incidents_count": 0,
  "current_incident_open": false,
  "current_incident_owner": "",
  "current_incident_owner_assigned": false,
  "current_incident_acknowledged": false,
  "current_incident_notes_count": 0,
  "current_incident_events_count": 0,
  "last_success_at": "2026-03-09 10:19:57 CST",
  "last_success_timestamp": 1773022797
}
```

## Sample: `incidents`

### `incidents list --limit 5`

```text
state_filter=all
owner_filter=all
ack_filter=all
incident_count=0
```

### `incidents current --json`

```json
{}
```

## Snapshot files produced during acceptance

- `docs/p7a-live/status-summary.txt`
- `docs/p7a-live/status.json`
- `docs/p7a-live/report-message.txt`
- `docs/p7a-live/report.json`
- `docs/p7a-live/metrics.json`
- `docs/p7a-live/metrics.prom`
- `docs/p7a-live/incidents-list.txt`
- `docs/p7a-live/incidents-current.json`
- `docs/p7a-live/openclaw-status.txt`

## Notes

- `metrics --prometheus` executed successfully and refreshed a scrape-ready text sample under `docs/p7a-live/metrics.prom`.
- `openclaw status` output currently includes plugin/banner lines before the main status card; this does not affect watchdog status/report/metrics commands, but it is worth remembering when copying operator-facing samples verbatim.
- This acceptance was read-only: no repair, restart, maintenance toggle, or incident mutation was performed.
