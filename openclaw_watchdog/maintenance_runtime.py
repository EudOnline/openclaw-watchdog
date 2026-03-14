from __future__ import annotations

from datetime import datetime

from openclaw_watchdog import health as health_ops


def maintenance_on(engine, reason: str = '') -> dict[str, object]:
    lines = [f"enabled_at={datetime.now().astimezone().strftime('%F %T %Z')}"]
    if reason:
        lines.append(f'reason={reason}')
    engine.config.watchdog_maintenance_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_maintenance_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    engine.log('INFO', f'maintenance mode enabled file={engine.config.watchdog_maintenance_file}')
    return health_ops.maintenance_status_payload(engine)


def maintenance_off(engine) -> dict[str, object]:
    engine.config.watchdog_maintenance_file.unlink(missing_ok=True)
    engine.log('INFO', f'maintenance mode disabled file={engine.config.watchdog_maintenance_file}')
    return health_ops.maintenance_status_payload(engine)
