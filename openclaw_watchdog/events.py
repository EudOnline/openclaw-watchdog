from __future__ import annotations

import textwrap


def event_severity(status: str, health_level: str, summary: str) -> str:
    text = (summary or '').lower()
    if status == 'failed' or health_level == 'failed':
        return 'critical'
    if status == 'degraded' or health_level == 'degraded':
        return 'warning'
    if status == 'recovered':
        return 'success'
    if status == 'healthy':
        if 'maintenance' in text:
            return 'info'
        return 'ok'
    return 'info'


def event_human_summary(status: str, health_level: str, summary: str) -> str:
    if status == 'failed' or health_level == 'failed':
        return f'watchdog 判定修复失败：{summary}'
    if status == 'degraded' or health_level == 'degraded':
        return f'watchdog 判定服务降级：{summary}'
    if status == 'recovered':
        return f'watchdog 已完成恢复：{summary}'
    if status == 'healthy':
        return f'watchdog 健康检查正常：{summary}'
    return summary


def build_event_payload(
    *,
    run_ts: str,
    status: str,
    summary: str,
    run_state: dict[str, object],
    rollback_occurred: bool,
    rollback_summary_file: str,
    rollback_summary_archive_file: str,
    rollback_broken_config_file: str,
    pre_repair_backup_result: str,
    consecutive_failures: int,
    incident_id: str,
    incident_dir: str,
) -> dict[str, object]:
    health_level = str(run_state.get('health_level', 'unknown') or 'unknown')
    return {
        'status': status,
        'time': run_ts,
        'summary': summary,
        'human_summary': event_human_summary(status, health_level, summary),
        'severity': event_severity(status, health_level, summary),
        'rollback_occurred': rollback_occurred,
        'rollback_summary_file': rollback_summary_file,
        'rollback_summary_archive_file': rollback_summary_archive_file,
        'rollback_broken_config_file': rollback_broken_config_file,
        'rollback_candidate_used': str(run_state.get('rollback_candidate_used', '') or ''),
        'rollback_reason': str(run_state.get('rollback_reason', '') or ''),
        'pre_repair_backup_result': pre_repair_backup_result,
        'consecutive_failures': consecutive_failures,
        'health_level': health_level,
        'current_mode': run_state.get('current_mode', 'normal'),
        'conversation_ready': bool(run_state.get('conversation_ready', False)),
        'minimal_usable_ready': bool(run_state.get('minimal_usable_ready', False)),
        'conversation_status': str(run_state.get('conversation_status', 'down') or 'down'),
        'conversation_probe_summary': str(run_state.get('conversation_probe_summary', '') or ''),
        'last_recovery_strategy': str(run_state.get('last_recovery_strategy', 'none') or 'none'),
        'last_recovery_path': str(run_state.get('last_recovery_path', 'none') or 'none'),
        'last_recovery_action_count': int(run_state.get('last_recovery_action_count', 0) or 0),
        'last_recovery_restored_conversation': bool(run_state.get('last_recovery_restored_conversation', False)),
        'config_drift_detected': bool(run_state.get('config_drift_detected', False)),
        'incident_id': incident_id,
        'incident_dir': incident_dir,
    }


def render_event_text(event_payload: dict[str, object]) -> str:
    return textwrap.dedent(
        f"""\
        status={event_payload.get('status', '')}
        time={event_payload.get('time', '')}
        summary={event_payload.get('summary', '')}
        rollback_occurred={'true' if bool(event_payload.get('rollback_occurred', False)) else 'false'}
        rollback_summary_file={event_payload.get('rollback_summary_file', '')}
        rollback_summary_archive_file={event_payload.get('rollback_summary_archive_file', '')}
        rollback_broken_config_file={event_payload.get('rollback_broken_config_file', '')}
        pre_repair_backup_result={event_payload.get('pre_repair_backup_result', '')}
        consecutive_failures={int(event_payload.get('consecutive_failures', 0) or 0)}
        incident_id={event_payload.get('incident_id', '')}
        incident_dir={event_payload.get('incident_dir', '')}
        """
    )
