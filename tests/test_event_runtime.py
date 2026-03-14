from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog.engine import WatchdogEngine
from openclaw_watchdog.run_context import RunContext


class EventRuntimeEngineDouble:
    def __init__(self, temp_dir: str) -> None:
        root = Path(temp_dir)
        self.config = SimpleNamespace(
            watchdog_event_file=root / 'event.txt',
            watchdog_event_history_file=root / 'event-history.jsonl',
            watchdog_event_history_limit=10,
            watchdog_last_rollback_summary_file=root / 'rollback-summary.txt',
        )
        self.ctx = RunContext.initial(stable_required_runs=2)
        self.ctx.run_ts = '2026-03-12 19:00:00 CST'
        self.ctx.rollback_occurred = True
        self.ctx.rollback_summary_archive_file = 'archive/rollback-1.txt'
        self.ctx.rollback_broken_config_file = 'archive/broken.json'
        self.ctx.pre_repair_backup_result = 'created'
        self.ctx.consecutive_failures = 3
        self.ctx.incident_id = 'incident-9'
        self.ctx.incident_dir = root / 'incidents' / 'incident-9'
        self._run_state = {
            'health_level': 'failed',
            'current_mode': 'normal',
            'conversation_ready': False,
            'minimal_usable_ready': False,
            'conversation_status': 'down',
            'conversation_probe_summary': 'gateway down',
            'last_recovery_strategy': 'doctor',
            'last_recovery_path': 'restart -> doctor',
            'last_recovery_action_count': 2,
            'last_recovery_restored_conversation': False,
            'config_drift_detected': True,
            'rollback_candidate_used': 'gen-2',
            'rollback_reason': 'config invalid',
        }

    def read_run_state(self) -> dict[str, object]:
        return dict(self._run_state)

    def sibling_json_path(self, path: Path) -> Path:
        if path.suffix:
            return path.with_suffix('.json')
        return path.with_name(f'{path.name}.json')

class EventRuntimeTests(unittest.TestCase):
    def test_watchdog_engine_no_longer_exposes_write_event_wrapper(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'write_event'))

    def test_write_event_persists_text_json_and_history(self) -> None:
        from openclaw_watchdog import event_runtime

        with TemporaryDirectory() as temp_dir:
            engine = EventRuntimeEngineDouble(temp_dir)

            event_runtime.write_event(engine, 'failed', 'deterministic remediation failed')

            text_payload = engine.config.watchdog_event_file.read_text(encoding='utf-8')
            json_payload = json.loads(engine.sibling_json_path(engine.config.watchdog_event_file).read_text(encoding='utf-8'))
            history_lines = [
                json.loads(line)
                for line in engine.config.watchdog_event_history_file.read_text(encoding='utf-8').splitlines()
                if line.strip()
            ]

        self.assertIn('status=failed', text_payload)
        self.assertIn('incident_id=incident-9', text_payload)
        self.assertEqual(json_payload['status'], 'failed')
        self.assertEqual(json_payload['incident_id'], 'incident-9')
        self.assertEqual(json_payload['rollback_candidate_used'], 'gen-2')
        self.assertEqual(json_payload['rollback_reason'], 'config invalid')
        self.assertEqual(history_lines, [json_payload])


if __name__ == '__main__':
    unittest.main()
