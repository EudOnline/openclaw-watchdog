from __future__ import annotations

import json

from openclaw_watchdog import health as health_ops
from openclaw_watchdog import incident_context as incident_context_ops
from openclaw_watchdog import incidents as incident_ops
from openclaw_watchdog import operator_snapshot
from openclaw_watchdog.models import IncidentSummary, ProbeSnapshot, RunStateSnapshot


def report_attention_items(report: dict[str, object]) -> list[str]:
    return incident_context_ops.report_attention_items(report)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _list_value(payload: dict[str, object], key: str, *, joiner: str, fallback: str = 'none') -> str:
    value = payload.get(key, [])
    if isinstance(value, list) and value:
        return joiner.join(str(item) for item in value if str(item).strip()) or fallback
    return fallback


def _incident_summary(value: object) -> IncidentSummary:
    if isinstance(value, IncidentSummary):
        return value
    if isinstance(value, dict):
        return IncidentSummary.from_dict(value)
    return IncidentSummary()


def _run_state_snapshot(payload: dict[str, object]) -> RunStateSnapshot:
    raw_run_state = payload.get("run_state")
    if isinstance(raw_run_state, RunStateSnapshot):
        return raw_run_state
    if isinstance(raw_run_state, dict):
        return RunStateSnapshot.from_dict(raw_run_state)
    return RunStateSnapshot.from_dict(payload)


def _rescue_fields(run_state: RunStateSnapshot) -> dict[str, object]:
    return {
        'rescue_attempt_count': run_state.rescue_attempt_count,
        'rescue_executor_selected': run_state.rescue_executor_selected,
        'rescue_plan_generated': run_state.rescue_plan_generated,
        'rescue_plan_source': run_state.rescue_plan_source,
        'rescue_plan_id': run_state.rescue_plan_id,
        'rescue_plan_status': run_state.rescue_plan_status,
        'rescue_tier': run_state.rescue_tier,
        'case_ingest_result': run_state.case_ingest_result,
        'candidate_rule_status': run_state.candidate_rule_status,
        'rescue_attempt_order': list(run_state.rescue_attempt_order),
        'rescue_rejected_executors': list(run_state.rescue_rejected_executors),
        'rescue_learning_summary': run_state.rescue_learning_summary,
        'rescue_mutation_scope': list(run_state.rescue_mutation_scope),
    }


def _model_failover_fields(run_state: RunStateSnapshot) -> dict[str, object]:
    return {
        'model_http_error_count': run_state.model_http_error_count,
        'model_http_error_latest_at': run_state.model_http_error_latest_at,
        'model_http_error_latest_status': run_state.model_http_error_latest_status,
        'model_failover_last_applied_at': run_state.model_failover_last_applied_at,
        'model_failover_last_from_model': run_state.model_failover_last_from_model,
        'model_failover_last_to_model': run_state.model_failover_last_to_model,
        'model_failover_last_status': run_state.model_failover_last_status,
        'model_failover_last_summary': run_state.model_failover_last_summary,
    }


def message_report_text(report: dict[str, object]) -> str:
    recent_stats = report.get("recent_event_stats", {})
    counts = recent_stats.get("counts", {}) if isinstance(recent_stats, dict) else {}
    last_event = report.get("last_event", {})
    recent_incidents = report.get("recent_incidents", [])
    attention_items = report.get("operator_attention_items", []) if isinstance(report.get("operator_attention_items", []), list) else []
    queue_summary = report.get("incident_queue_summary", {}) if isinstance(report.get("incident_queue_summary", {}), dict) else {}
    lines = [
        f"OpenClaw watchdog：conversation={report.get('conversation_status', 'down')} / status={report.get('status', 'unknown')} / mode={report.get('current_mode', 'unknown')}",
        f"recovery={report.get('last_recovery_strategy', 'none')} | rollback={report.get('rollback_candidate_used', '') or 'none'} | restored={str(bool(report.get('last_recovery_restored_conversation', False))).lower()}",
        (
            f"rescue=executor:{report.get('rescue_executor_selected', '') or 'none'}"
            f" | attempts={int(report.get('rescue_attempt_count', 0) or 0)}"
            f" | plan={str(bool(report.get('rescue_plan_generated', False))).lower()}/{report.get('rescue_plan_status', 'not-run')}"
            f" | tier={report.get('rescue_tier', 'none')}"
            f" | learn={report.get('rescue_learning_summary', '') or report.get('candidate_rule_status', 'none')}"
        ),
        (
            f"rescue_chain=chain={_list_value(report, 'rescue_attempt_order', joiner=' -> ')}"
            f" | rejected={_list_value(report, 'rescue_rejected_executors', joiner=',')}"
            f" | mutate={_list_value(report, 'rescue_mutation_scope', joiner=',')}"
            f" | learning={report.get('rescue_learning_summary', '') or 'not-run / none'}"
        ),
        (
            f"model_failover=status={report.get('model_failover_last_status', 'not-run') or 'not-run'}"
            f" | recent_non_200={int(report.get('model_http_error_count', 0) or 0)}"
            f" | latest_status={int(report.get('model_http_error_latest_status', 0) or 0)}"
            f" | from={report.get('model_failover_last_from_model', '') or 'none'}"
            f" | to={report.get('model_failover_last_to_model', '') or 'none'}"
        ),
        (
            f"service_active={str(bool(report.get('service_active', False))).lower()}"
            f" | probe={report.get('service_probe_summary', 'n/a')}"
            f" | conv_probe={report.get('conversation_probe_summary', 'n/a')}"
            f" | msg_loop={(report.get('message_loop_probe_summary', '') or 'off') if report.get('message_loop_probe_enabled', False) else 'off'}"
        ),
        f"queue：open={queue_summary.get('open_total', 0)} attention={queue_summary.get('attention_total', 0)} handled={queue_summary.get('handled_total', 0)}",
        (
            "24h recent："
            f"healthy={counts.get('healthy', 0)} degraded={counts.get('degraded', 0)} "
            f"recovered={counts.get('recovered', 0)} failed={counts.get('failed', 0)}"
        ),
        f"last_event：{last_event.get('human_summary', last_event.get('summary', 'none'))}",
    ]
    if bool(report.get("survival_mode_active", False)):
        actions = report.get("survival_mode_actions", []) if isinstance(report.get("survival_mode_actions", []), list) else []
        disabled = report.get("survival_mode_disabled_features", []) if isinstance(report.get("survival_mode_disabled_features", []), list) else []
        blockers = _string_list(report.get("survival_mode_exit_blockers", []))
        stable_ready_runs = int(report.get("survival_mode_stable_ready_runs", 0) or 0)
        stable_required_runs = int(report.get("survival_mode_stable_required_runs", 0) or 0)
        lines.append(
            "survival_mode: active"
            f" | reason={report.get('survival_mode_reason', '') or 'unknown'}"
            f" | since={report.get('survival_mode_since', '') or 'unknown'}"
            f" | sticky={str(bool(report.get('survival_mode_sticky', False))).lower()}"
            f" | exit_ready={str(bool(report.get('survival_mode_exit_ready', False))).lower()}"
            f" | exit_policy={report.get('survival_mode_exit_policy', '') or 'none'}"
            f" | stable={stable_ready_runs}/{stable_required_runs}"
            f" | disabled={','.join(str(item) for item in disabled) if disabled else 'none'}"
        )
        lines.append(
            "survival_exit: "
            f"manual_clear_required={str(bool(report.get('survival_mode_manual_clear_required', False))).lower()}"
            f" | config_changed_away={str(bool(report.get('survival_mode_config_changed_away', False))).lower()}"
            f" | blockers={'; '.join(blockers) if blockers else (report.get('survival_mode_sticky_reason', '') or 'none')}"
        )
        if actions:
            lines.append("survival_actions: " + "; ".join(str(item) for item in actions))
    elif str(report.get("survival_mode_last_exit_kind", "") or ""):
        lines.append(
            "survival_last_exit: "
            f"kind={report.get('survival_mode_last_exit_kind', '') or 'unknown'}"
            f" | at={report.get('survival_mode_last_exit_at', '') or 'unknown'}"
            f" | reason={report.get('survival_mode_last_exit_reason', '') or 'unknown'}"
            f" | summary={report.get('survival_mode_last_exit_summary', '') or 'none'}"
        )
    if bool(report.get("config_drift_detected", False)):
        scope = report.get("drift_scope", []) if isinstance(report.get("drift_scope", []), list) else []
        lines.append(
            "drift_guard: detected"
            f" | scope={','.join(str(item) for item in scope) if scope else 'unknown'}"
            f" | baseline={report.get('drift_since_last_good', '') or 'unknown'}"
        )
    elif str(report.get("guard_last_operation", "") or ""):
        lines.append(
            "drift_guard: "
            f"{report.get('guard_last_operation', '') or 'unknown'}"
            f" | {report.get('guard_last_summary', '') or 'no-summary'}"
        )
    if isinstance(recent_incidents, list) and recent_incidents:
        lines.append("recent_incidents:")
        for incident in recent_incidents[-3:]:
            summary = _incident_summary(incident)
            latest_note_suffix = f" | note={summary.latest_note}" if summary.latest_note else ""
            attention_suffix = f" | attention={summary.attention_summary or 'none'}"
            lines.append(
                f"- {summary.incident_id or 'none'} | {summary.state or 'unknown'} | {summary.health_level or 'unknown'} | "
                f"owner={summary.owner or 'none'} | ack={str(bool(summary.acknowledged)).lower()} | notes={summary.notes_count} | "
                f"{summary.summary}{latest_note_suffix}{attention_suffix}"
            )
    else:
        lines.append("recent_incidents: none")
    if attention_items:
        lines.append("attention:")
        for item in attention_items:
            lines.append(f"- {item}")
    else:
        lines.append("attention: none")
    return "\n".join(lines)


def write_report_snapshot(engine, report: dict[str, object]) -> None:
    engine.config.watchdog_last_report_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    engine.config.watchdog_last_report_file.with_suffix(".txt").write_text(
        str(report.get("message_text", "")) + "\n",
        encoding="utf-8",
    )


def report_payload(engine, *, incident_limit: int = 5) -> dict[str, object]:
    payload = health_ops.status_payload(engine)
    probe = ProbeSnapshot.from_dict(payload)
    run_state = _run_state_snapshot(payload)
    snapshot_source = dict(payload)
    if isinstance(payload.get('run_state'), dict):
        snapshot_source.update(payload.get('run_state', {}))
    snapshot = operator_snapshot.build_operator_snapshot(
        snapshot_source,
        stable_required_runs=int(payload.get('survival_mode_stable_required_runs', 0) or 0) or 1,
        guard_manifest_file=str(payload.get('guard_manifest_file', '') or ''),
    )
    current_incident = incident_ops.current_incident_payload(engine) if str(payload.get("current_incident_id", "") or "") else {}
    recent_incidents = incident_ops.list_incident_snapshots(engine, limit=max(1, incident_limit))
    incident_context = incident_context_ops.build_report_incident_context(
        current_incident_id=payload.get('current_incident_id', ''),
        current_incident_state=payload.get('current_incident_state', ''),
        current_incident=current_incident,
        recent_incidents=recent_incidents,
        incident_limit=max(1, incident_limit),
    )
    status = str(payload.get("last_status", "unknown"))
    effective_health_level = str(payload.get("health_level", "unknown") or "unknown")
    report = {
        "generated_at": engine.now_iso(),
        "status": status,
        "health_level": effective_health_level,
        "current_mode": payload.get("current_mode", "unknown"),
        "service_active": probe.service_active,
        "conversation_ready": probe.conversation_ready,
        "minimal_usable_ready": probe.minimal_usable_ready,
        "conversation_status": probe.conversation_status,
        "service_probe_summary": probe.service_probe_summary,
        "conversation_probe_summary": probe.conversation_probe_summary,
        "message_loop_probe_enabled": bool(payload.get("message_loop_probe_enabled", False)),
        "message_loop_probe_attempted": bool(payload.get("message_loop_probe_attempted", False)),
        "message_loop_probe_ready": bool(payload.get("message_loop_probe_ready", False)),
        "message_loop_probe_sent": bool(payload.get("message_loop_probe_sent", False)),
        "message_loop_probe_echo_received": bool(payload.get("message_loop_probe_echo_received", False)),
        "message_loop_probe_cached": bool(payload.get("message_loop_probe_cached", False)),
        "message_loop_probe_summary": str(payload.get("message_loop_probe_summary", "") or ""),
        "last_event": payload.get("last_event", {}),
        "recent_event_stats": payload.get("recent_event_stats", {}),
        "incident_queue_summary": payload.get("incident_queue_summary", {}),
        "recent_incidents": incident_context['recent_incidents'],
        "current_incident_id": incident_context['current_incident_id'],
        "current_incident_state": incident_context['current_incident_state'],
        "current_incident_owner": incident_context['current_incident_owner'],
        "current_incident_acknowledged": incident_context['current_incident_acknowledged'],
        "current_incident_notes_count": incident_context['current_incident_notes_count'],
        "survival_mode_active": bool(payload.get("survival_mode_active", False)),
        "survival_mode_reason": str(payload.get("survival_mode_reason", "") or ""),
        "survival_mode_since": str(payload.get("survival_mode_since", "") or ""),
        "survival_mode_summary": str(payload.get("survival_mode_summary", "") or ""),
        "survival_mode_actions": list(payload.get("survival_mode_actions", [])) if isinstance(payload.get("survival_mode_actions", []), list) else [],
        "survival_mode_disabled_features": list(payload.get("survival_mode_disabled_features", [])) if isinstance(payload.get("survival_mode_disabled_features", []), list) else [],
        "survival_mode_config_file": str(payload.get("survival_mode_config_file", "") or ""),
        "survival_mode_sticky": bool(payload.get("survival_mode_sticky", False)),
        "survival_mode_sticky_reason": str(payload.get("survival_mode_sticky_reason", "") or ""),
        "survival_mode_exit_ready": bool(payload.get("survival_mode_exit_ready", False)),
        "survival_mode_exit_policy": str(payload.get("survival_mode_exit_policy", "") or "none"),
        "survival_mode_exit_blockers": list(payload.get("survival_mode_exit_blockers", [])) if isinstance(payload.get("survival_mode_exit_blockers", []), list) else [],
        "survival_mode_stable_ready_runs": int(payload.get("survival_mode_stable_ready_runs", 0) or 0),
        "survival_mode_stable_required_runs": int(payload.get("survival_mode_stable_required_runs", 0) or 0),
        "survival_mode_manual_clear_required": bool(payload.get("survival_mode_manual_clear_required", False)),
        "survival_mode_config_changed_away": bool(payload.get("survival_mode_config_changed_away", False)),
        "survival_mode_last_exit_at": str(payload.get("survival_mode_last_exit_at", "") or ""),
        "survival_mode_last_exit_reason": str(payload.get("survival_mode_last_exit_reason", "") or ""),
        "survival_mode_last_exit_kind": str(payload.get("survival_mode_last_exit_kind", "") or ""),
        "survival_mode_last_exit_summary": str(payload.get("survival_mode_last_exit_summary", "") or ""),
        **_model_failover_fields(run_state),
        "last_recovery_strategy": run_state.last_recovery_strategy,
        "last_recovery_path": run_state.last_recovery_path,
        "last_recovery_action_count": run_state.last_recovery_action_count,
        "last_recovery_restored_conversation": run_state.last_recovery_restored_conversation,
        **_rescue_fields(run_state),
        "last_good_validated_at": run_state.last_good_validated_at,
        "last_good_generation_id": run_state.last_good_generation_id,
        "last_good_generation_count": run_state.last_good_generation_count,
        "rollback_candidate_used": run_state.rollback_candidate_used,
        "rollback_reason": run_state.rollback_reason,
        "config_drift_detected": run_state.config_drift_detected,
        "drift_scope": list(run_state.drift_scope),
        "drift_since_last_good": run_state.drift_since_last_good,
        "drift_summary": run_state.drift_summary,
        "guard_manifest_file": str(payload.get("guard_manifest_file", "") or ""),
        "guard_last_operation": str(payload.get("guard_last_operation", "") or ""),
        "guard_last_phase": str(payload.get("guard_last_phase", "") or ""),
        "guard_last_time": str(payload.get("guard_last_time", "") or ""),
        "guard_last_summary": str(payload.get("guard_last_summary", "") or ""),
        "maintenance": payload.get("maintenance", {}),
        "env_file": payload.get("env_file", ""),
    }
    report.update(operator_snapshot.to_payload(snapshot))
    report['operator_attention_items'] = incident_context['operator_attention_items']
    report['operator_attention_needed'] = incident_context['operator_attention_needed']
    report['operator_attention_count'] = incident_context['operator_attention_count']
    report["message_text"] = message_report_text(report)
    write_report_snapshot(engine, report)
    return report
