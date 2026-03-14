from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog.engine import WatchdogEngine


class MaintenanceRuntimeEngineDouble:
    def __init__(self, temp_dir: str) -> None:
        root = Path(temp_dir)
        self.config = SimpleNamespace(
            watchdog_maintenance_file=root / 'state' / 'maintenance.flag',
        )
        self.logged: list[tuple[str, str]] = []

    def log(self, level: str, message: str) -> None:
        self.logged.append((level, message))

    def maintenance_status_payload(self, runtime_engine=None) -> dict[str, object]:
        if runtime_engine is not None:
            assert runtime_engine is self
        enabled = self.config.watchdog_maintenance_file.exists()
        content = self.config.watchdog_maintenance_file.read_text(encoding='utf-8').strip() if enabled else ''
        return {
            'enabled': enabled,
            'content': content,
            'file': str(self.config.watchdog_maintenance_file),
        }


class MaintenanceRuntimeTests(unittest.TestCase):
    def test_watchdog_engine_no_longer_exposes_maintenance_helpers(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'maintenance_on'))
        self.assertFalse(hasattr(WatchdogEngine, 'maintenance_off'))

    def test_watchdog_engine_no_longer_exposes_survival_transition_helpers(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'sync_survival_mode'))
        self.assertFalse(hasattr(WatchdogEngine, 'enter_survival_mode'))

    def test_maintenance_on_writes_reason_and_returns_status_payload(self) -> None:
        from openclaw_watchdog import maintenance_runtime

        with TemporaryDirectory() as temp_dir:
            engine = MaintenanceRuntimeEngineDouble(temp_dir)

            with patch('openclaw_watchdog.maintenance_runtime.health_ops.maintenance_status_payload', wraps=engine.maintenance_status_payload) as status_mock:
                payload = maintenance_runtime.maintenance_on(engine, 'deploy window')

            written = engine.config.watchdog_maintenance_file.read_text(encoding='utf-8')

        self.assertTrue(payload['enabled'])
        self.assertIn('reason=deploy window', written)
        status_mock.assert_called_once_with(engine)
        self.assertEqual(engine.logged, [('INFO', f'maintenance mode enabled file={engine.config.watchdog_maintenance_file}')])

    def test_maintenance_off_removes_file_and_returns_status_payload(self) -> None:
        from openclaw_watchdog import maintenance_runtime

        with TemporaryDirectory() as temp_dir:
            engine = MaintenanceRuntimeEngineDouble(temp_dir)
            engine.config.watchdog_maintenance_file.parent.mkdir(parents=True, exist_ok=True)
            engine.config.watchdog_maintenance_file.write_text('enabled_at=2026-03-12 20:00:00 CST\n', encoding='utf-8')

            with patch('openclaw_watchdog.maintenance_runtime.health_ops.maintenance_status_payload', wraps=engine.maintenance_status_payload) as status_mock:
                payload = maintenance_runtime.maintenance_off(engine)

        self.assertFalse(payload['enabled'])
        self.assertFalse(engine.config.watchdog_maintenance_file.exists())
        status_mock.assert_called_once_with(engine)
        self.assertEqual(engine.logged, [('INFO', f'maintenance mode disabled file={engine.config.watchdog_maintenance_file}')])


if __name__ == '__main__':
    unittest.main()
