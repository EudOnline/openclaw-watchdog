# Operational reporting outputs

This document describes the current machine-readable output surface for the watchdog.

It is intentionally narrower than a broad compatibility promise: these JSON keys and Prometheus metric names matter because rehearsals, dashboards, and operator automation depend on them for OpenClaw fallback visibility. Fields that are redundant, fake, or only preserved for migration should be removed instead of being carried forever.

## Scope

This guidance applies to:

- `scripts/openclaw-watchdog report --json`
- `scripts/openclaw-watchdog metrics --json`
- `scripts/openclaw-watchdog metrics --prometheus`

Human-readable text such as `report --message` and `status --summary` should stay readable for operators, but they are not treated as strict API surfaces.

## Change discipline

When changing report or metrics output:

1. protect the fields used by rehearsals, live acceptance, dashboards, or active automation;
2. prefer removing stale or migration-only fields over preserving them indefinitely;
3. update focused regression tests together with the implementation;
4. update `docs/live-acceptance-checklist.md` and `CHANGELOG.md` when the operational surface changes.

## Operational report keys

These top-level `report --json` fields are treated as the current operational minimum:

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
- `rescue_attempt_count`
- `rescue_executor_selected`
- `rescue_plan_generated`
- `rescue_plan_source`
- `rescue_plan_status`
- `rescue_tier`
- `case_ingest_result`
- `candidate_rule_status`
- `rescue_attempt_order`
- `rescue_rejected_executors`
- `rescue_learning_summary`
- `rescue_mutation_scope`
- `rollback_candidate_used`
- `config_drift_detected`
- `current_incident_id`
- `operator_attention_needed`
- `operator_attention_items`
- `recent_incidents`
- `message_text`

## Operational metrics keys

These top-level `metrics --json` fields are treated as the current operational minimum:

- `status`
- `health_level`
- `service_active`
- `conversation_ready`
- `minimal_usable_ready`
- `survival_mode_active`
- `survival_mode_exit_ready`
- `last_recovery_action_count`
- `rescue_attempt_count`
- `rescue_executor_selected`
- `rescue_plan_generated`
- `rescue_plan_status`
- `rescue_tier`
- `candidate_rule_status`
- `config_drift_detected`
- `current_incident_open`
- `current_incident_acknowledged`
- `current_incident_notes_count`
- `current_incident_owner_assigned`
- `recent_healthy_total`
- `recent_degraded_total`
- `recent_recovered_total`
- `recent_failed_total`

## Prometheus guidance

The Prometheus exposition should preserve metric names that are likely to be scraped by dashboards or alerts, especially:

- `openclaw_watchdog_info`
- `openclaw_watchdog_service_active`
- `openclaw_watchdog_conversation_ready`
- `openclaw_watchdog_minimal_usable_ready`
- `openclaw_watchdog_survival_mode_active`
- `openclaw_watchdog_last_recovery_action_count`
- `openclaw_watchdog_config_drift_detected`
- `openclaw_watchdog_current_incident_open`

## Intentionally unprotected details

The watchdog no longer protects stale reporting details such as:

- `recent_incident_summaries`
- `current_incident_events_count`
- `current_incident_latest_event_type`

If a future field is not tied to fallback behavior, rehearsal assertions, operator workflows, or dashboards, it should be treated the same way.
