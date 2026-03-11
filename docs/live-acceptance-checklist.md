# OpenClaw Watchdog live acceptance checklist

This checklist is the operator-facing closure for the fallback-first watchdog design.

## Recommended validation order

Before running live acceptance on a host, keep this sequence:

1. `python -m unittest discover -s tests -v`
2. direct flow/bootstrap tests for any code you changed
3. bounded rehearsal smoke scenarios from `rehearsal/scripts/run-scenario.sh`
4. this live acceptance checklist on a real host

Live acceptance is the final operator-facing gate, not the first regression check.

## One-command acceptance

Before running the full acceptance script on a new host, the operator quick path should already look sane: `status --summary`, `report --message`, and `incidents current --json` should all be readable and internally consistent.

```bash
./scripts/openclaw-watchdog-live-acceptance.sh
```

Default output directory:

- `docs/p7a-live/`

## Files produced

- `status-summary.txt`
- `status.json`
- `report-message.txt`
- `report.json`
- `metrics.json`
- `metrics.prom`
- `incidents-list.txt`
- `incidents-current.json`
- `openclaw-status.txt`
- `acceptance-summary.json`
- `acceptance-summary.txt`

## Required checks

The script automatically validates these consistency checks:

1. `status.last_status == report.status`
2. `status.last_status == metrics.status`
3. `status.health_level == metrics.health_level`
4. `status.conversation_ready == report.conversation_ready == metrics.conversation_ready`
5. `status.minimal_usable_ready == report.minimal_usable_ready == metrics.minimal_usable_ready`
6. `status.last_recovery_strategy == report.last_recovery_strategy == metrics.last_recovery_strategy`
7. `status.last_recovery_path == report.last_recovery_path == metrics.last_recovery_path`
8. `metrics.prom` contains `openclaw_watchdog_info`
9. `metrics.prom` contains `openclaw_watchdog_service_active`
10. `metrics.prom` contains the fallback gauges (`conversation_ready`, `minimal_usable_ready`, `survival_mode_active`, `last_recovery_action_count`, `config_drift_detected`)
11. `metrics.prom` contains the incident-context gauges that still drive operator awareness
12. `status --summary` contains `probe=`
13. `status --summary` contains `conversation=`
14. `status --summary` contains `recovery=`
15. `incidents current --json` is consistent with `status.current_incident_id`
16. `report.json` exposes `operator_attention_items` in list form
17. when there is no current incident, `report.operator_attention_needed == false`
18. `report.json` exposes the fallback-first fields (`conversation_*`, `survival_mode_*`, `last_recovery_*`, `rollback_candidate_used`, `config_drift_detected`, `drift_*`)
19. `metrics.json` exposes the fallback-first, drift-guard, and last-good fields
20. `metrics.json` still exposes the current-incident operator fields (`current_incident_owner`, `current_incident_owner_assigned`, `current_incident_acknowledged`, `current_incident_notes_count`)

If any check fails, the script exits non-zero.

## Manual operator review

After the script passes, quickly review:

- `status-summary.txt` is concise, readable, and starts with fallback/recovery signals
- `report-message.txt` clearly answers whether conversation is restored, what recovery path was used, and whether rollback/degradation is still in effect
- `metrics.json` has current timestamps/counters plus fallback signals such as `conversation_status`, `survival_mode_reason`, `drift_scope`, and `last_good_generation_*`
- `metrics.prom` is scrape-ready text and includes the fallback gauges
- `incidents-list.txt` still matches the current healthy/incident window
- `openclaw-status.txt` may include plugin/banner lines before the status card; this is acceptable as long as the watchdog commands above remain clean

## Pass criteria

A live read-only acceptance is considered passed when:

- the script exits `0`
- `acceptance-summary.json` shows `all_checks_passed=true`
- no watchdog command returns a traceback or malformed JSON
- output is archived under `docs/p7a-live/` for later comparison
