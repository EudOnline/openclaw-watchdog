from __future__ import annotations

import json

from openclaw_watchdog import event_history
from openclaw_watchdog import events as event_ops


def write_event(engine, status: str, summary: str) -> None:
    run_state = engine.read_run_state()
    event_payload = event_ops.build_event_payload(
        run_ts=engine.ctx.run_ts,
        status=status,
        summary=summary,
        run_state=run_state,
        rollback_occurred=engine.ctx.rollback_occurred,
        rollback_summary_file=str(engine.config.watchdog_last_rollback_summary_file),
        rollback_summary_archive_file=engine.ctx.rollback_summary_archive_file,
        rollback_broken_config_file=engine.ctx.rollback_broken_config_file,
        pre_repair_backup_result=engine.ctx.pre_repair_backup_result,
        consecutive_failures=engine.ctx.consecutive_failures,
        incident_id=engine.ctx.incident_id,
        incident_dir=str(engine.ctx.incident_dir) if engine.ctx.incident_dir else '',
    )
    engine.config.watchdog_event_file.write_text(event_ops.render_event_text(event_payload), encoding='utf-8')
    engine.sibling_json_path(engine.config.watchdog_event_file).write_text(
        json.dumps(event_payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    event_history.append_event_history(engine, event_payload)
