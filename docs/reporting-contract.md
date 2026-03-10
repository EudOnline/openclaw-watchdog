# Reporting contract

This document defines the compatibility expectations for the machine-readable watchdog outputs.

## Scope

The contract applies to:

- `scripts/openclaw-watchdog report --json`
- `scripts/openclaw-watchdog metrics --json`
- `scripts/openclaw-watchdog metrics --prometheus`

Human-readable text such as `report --message` and `status --summary` should stay readable for operators, but they are not treated as strict API surfaces.

## Compatibility level

Within a minor release line:

- existing top-level JSON keys should remain present;
- additive keys are preferred over renames or removals;
- renamed or removed keys should be called out in `CHANGELOG.md` and `docs/compatibility-and-deprecations.md`;
- Prometheus metric names should remain stable unless there is a compelling correctness reason to change them.

## Stable report keys

These top-level `report --json` fields are treated as stable operator/integration fields:

- `status`
- `health_level`
- `current_mode`
- `conversation_status`
- `conversation_ready`
- `minimal_usable_ready`
- `last_recovery_strategy`
- `last_recovery_path`
- `last_recovery_action_count`
- `last_recovery_restored_conversation`
- `rollback_candidate_used`
- `config_drift_detected`
- `current_incident_id`
- `operator_attention_needed`
- `operator_attention_items`
- `recent_incidents`
- `message_text`

## Stable metrics keys

These top-level `metrics --json` fields are treated as stable integration fields:

- `status`
- `health_level`
- `service_active`
- `conversation_ready`
- `minimal_usable_ready`
- `survival_mode_active`
- `survival_mode_exit_ready`
- `last_recovery_action_count`
- `config_drift_detected`
- `current_incident_open`
- `current_incident_acknowledged`
- `current_incident_notes_count`
- `current_incident_owner_assigned`
- `cooldown_remaining_seconds`
- `recent_healthy_total`
- `recent_degraded_total`
- `recent_recovered_total`
- `recent_failed_total`

## Prometheus guidance

The Prometheus exposition should preserve metric names that external dashboards or alerts are likely to scrape, especially:

- `openclaw_watchdog_info`
- `openclaw_watchdog_service_active`
- `openclaw_watchdog_conversation_ready`
- `openclaw_watchdog_minimal_usable_ready`
- `openclaw_watchdog_survival_mode_active`
- `openclaw_watchdog_last_recovery_action_count`
- `openclaw_watchdog_config_drift_detected`
- `openclaw_watchdog_current_incident_open`

## Change policy

When changing report or metrics output:

1. prefer additive changes;
2. update or add focused regression tests;
3. update `docs/live-acceptance-checklist.md` if acceptance expectations change;
4. record the change in `CHANGELOG.md` if compatibility may be affected.
