from __future__ import annotations

import os
import signal
import time

from openclaw_watchdog import service_runtime


def _platform_supervisor_mode(engine) -> str:
    capabilities = getattr(getattr(engine, 'platform', None), 'capabilities', None)
    value = getattr(capabilities, 'supervisor', '')
    return str(value) if value is not None else ''


def run_pre_repair_backup(engine) -> None:
    if not engine.config.watchdog_enable_pre_repair_backup:
        engine.ctx.pre_repair_backup_result = 'disabled'
        return
    if engine.incident_backup_marker.exists():
        engine.ctx.pre_repair_backup_result = 'skipped-existing-incident-backup'
        return
    if not engine.config.watchdog_backup_script.exists():
        engine.ctx.pre_repair_backup_result = 'backup-script-missing'
        engine.log('WARN', f'pre-repair backup skipped: missing script {engine.config.watchdog_backup_script}')
        engine.incident_backup_marker.write_text(f'{engine.ctx.run_ts} backup-script-missing\n', encoding='utf-8')
        return
    engine.log('INFO', f'running pre-repair backup via {engine.config.watchdog_backup_script}')
    result = engine.run_command(
        [
            'bash',
            '-lc',
            'source "$1" 2>/dev/null || true; node "$2"',
            '_',
            str(engine.config.watchdog_backup_env_file),
            str(engine.config.watchdog_backup_script),
        ],
        timeout=engine.config.watchdog_backup_timeout_seconds,
        merge_stderr=True,
    )
    with engine.config.watchdog_log_file.open('a', encoding='utf-8') as handle:
        if result.output:
            handle.write(result.output)
    if result.returncode == 0:
        engine.ctx.pre_repair_backup_result = 'success'
        engine.log('INFO', 'pre-repair backup completed')
    else:
        engine.ctx.pre_repair_backup_result = 'failed'
        engine.log('WARN', 'pre-repair backup failed; continuing remediation')
    engine.incident_backup_marker.write_text(f'{engine.ctx.run_ts} {engine.ctx.pre_repair_backup_result}\n', encoding='utf-8')


def kill_stray_listeners(engine, main_pid: str) -> None:
    killed = False
    for pid in service_runtime.listener_pids(engine):
        if pid == main_pid:
            continue
        result = engine.run_command(['ps', '-p', pid, '-o', 'args='], timeout=10)
        cmdline = result.output.strip()
        if 'openclaw' in cmdline.lower():
            engine.log('WARN', f'killing stray listener pid={pid} cmd={cmdline}')
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, ValueError):
                pass
            killed = True
    if killed:
        time.sleep(2)


def restart_service(engine) -> bool:
    supervisor = getattr(getattr(engine, 'platform', None), 'supervisor', None)
    if supervisor is not None and _platform_supervisor_mode(engine) != 'manual':
        return supervisor.restart_service(engine)
    engine.log('INFO', f'restarting {engine.config.openclaw_gateway_service}')
    engine.run_command(['systemctl', '--user', 'reset-failed', engine.config.openclaw_gateway_service], timeout=15)
    result = engine.run_command(['systemctl', '--user', 'restart', engine.config.openclaw_gateway_service], timeout=30)
    if result.returncode == 0:
        time.sleep(engine.config.watchdog_restart_wait_seconds)
        return True
    engine.log('WARN', f'failed to restart {engine.config.openclaw_gateway_service}: {result.output.strip()}')
    return False


def run_doctor_repair(engine) -> bool:
    if not engine.config.watchdog_enable_doctor_repair:
        return False
    engine.log('INFO', 'running openclaw doctor --repair --non-interactive --yes')
    result = engine.run_command(
        ['openclaw', 'doctor', '--repair', '--non-interactive', '--yes'],
        timeout=engine.config.watchdog_doctor_timeout_seconds,
        merge_stderr=True,
    )
    with engine.config.watchdog_log_file.open('a', encoding='utf-8') as handle:
        if result.output:
            handle.write(result.output)
    if result.returncode == 0:
        engine.log('INFO', 'doctor repair completed')
        return True
    else:
        engine.log('WARN', f'doctor repair exited rc={result.returncode}')
        return False
