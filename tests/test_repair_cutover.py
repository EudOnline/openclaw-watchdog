from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog.engine import WatchdogEngine


class RepairCutoverTests(unittest.TestCase):
    def test_engine_support_helpers_delegate_to_engine_support_runtime(self) -> None:
        engine = object.__new__(WatchdogEngine)

        with patch('openclaw_watchdog.engine.engine_support_runtime.prepare_state_dirs') as prepare_mock:
            engine._prepare_state_dirs()

        with patch('openclaw_watchdog.engine.engine_support_runtime.acquire_lock', return_value=True) as acquire_mock:
            self.assertTrue(engine.acquire_lock())

        with patch('openclaw_watchdog.engine.engine_support_runtime.release_lock') as release_mock:
            engine.release_lock()

        with patch('openclaw_watchdog.engine.engine_support_runtime.log') as log_mock:
            engine.log('WARN', 'hello')

        with patch('openclaw_watchdog.engine.engine_support_runtime.notify') as notify_mock:
            engine.notify('hello')

        with patch('openclaw_watchdog.engine.engine_support_runtime.append_rollback_summary', return_value='merged') as summary_mock:
            self.assertEqual(engine.append_rollback_summary('base'), 'merged')

        with patch('openclaw_watchdog.engine.engine_support_runtime.read_failure_count', return_value=3) as read_mock:
            self.assertEqual(engine.read_failure_count(), 3)

        with patch('openclaw_watchdog.engine.engine_support_runtime.write_failure_count') as write_mock:
            engine.write_failure_count(4)

        with patch('openclaw_watchdog.engine.engine_support_runtime.reset_failure_count') as reset_mock:
            engine.reset_failure_count()

        with patch('openclaw_watchdog.engine.engine_support_runtime.increment_failure_count', return_value=5) as increment_mock:
            self.assertEqual(engine.increment_failure_count(), 5)

        with patch('openclaw_watchdog.engine.engine_support_runtime.now_iso', return_value='2026-03-12T22:00:00+08:00') as now_mock:
            self.assertEqual(engine.now_iso(), '2026-03-12T22:00:00+08:00')

        with patch('openclaw_watchdog.engine.engine_support_runtime.current_mode', return_value='survival') as mode_mock:
            self.assertEqual(engine.current_mode(maintenance=False, degraded=False, survival=True), 'survival')

        with patch('openclaw_watchdog.engine.engine_support_runtime.sibling_json_path', return_value=Path('/tmp/event.json')) as sibling_mock:
            self.assertEqual(engine.sibling_json_path(Path('/tmp/event')), Path('/tmp/event.json'))

        prepare_mock.assert_called_once_with(engine)
        acquire_mock.assert_called_once_with(engine)
        release_mock.assert_called_once_with(engine)
        log_mock.assert_called_once_with(engine, 'WARN', 'hello')
        notify_mock.assert_called_once_with(engine, 'hello')
        summary_mock.assert_called_once_with(engine, 'base')
        read_mock.assert_called_once_with(engine)
        write_mock.assert_called_once_with(engine, 4)
        reset_mock.assert_called_once_with(engine)
        increment_mock.assert_called_once_with(engine)
        now_mock.assert_called_once_with(engine)
        mode_mock.assert_called_once_with(maintenance=False, degraded=False, survival=True)
        sibling_mock.assert_called_once_with(Path('/tmp/event'))

    def test_watchdog_engine_no_longer_exposes_doctor_wrappers(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'run_doctor'))
        self.assertFalse(hasattr(WatchdogEngine, 'config_invalid'))

    def test_watchdog_engine_no_longer_exposes_deterministic_repair_wrappers(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'backup_last_good'))
        self.assertFalse(hasattr(WatchdogEngine, 'run_pre_repair_backup'))
        self.assertFalse(hasattr(WatchdogEngine, 'restore_last_good'))
        self.assertFalse(hasattr(WatchdogEngine, 'restart_service'))
        self.assertFalse(hasattr(WatchdogEngine, 'run_doctor_repair'))

    def test_watchdog_engine_no_longer_exposes_recovery_tracking_and_domain_wrappers(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'reset_recovery_tracking'))
        self.assertFalse(hasattr(WatchdogEngine, 'record_recovery_step'))
        self.assertFalse(hasattr(WatchdogEngine, 'recovery_path_text'))
        self.assertFalse(hasattr(WatchdogEngine, 'finalize_recovery_tracking'))
        self.assertFalse(hasattr(WatchdogEngine, 'capture_rollback_summary'))
        self.assertFalse(hasattr(WatchdogEngine, '_walk_json_diff'))
        self.assertFalse(hasattr(WatchdogEngine, 'prune_rollback_archives'))
        self.assertFalse(hasattr(WatchdogEngine, 'drift_context'))
        self.assertFalse(hasattr(WatchdogEngine, 'refresh_drift_context'))
        self.assertFalse(hasattr(WatchdogEngine, 'kill_stray_listeners'))

    def test_rescue_actions_guard_helpers_delegate_to_last_good_runtime(self) -> None:
        from openclaw_watchdog.rescue_actions import RescueActionExecutor

        config = SimpleNamespace(
            watchdog_guard_manifest_file=Path('/tmp/guard.json'),
            openclaw_config=Path('/tmp/openclaw.json'),
            env_file=None,
            watchdog_survival_config_file=Path('/tmp/survival.json'),
            watchdog_protected_paths=(),
            watchdog_rescue_editable_paths=(),
            watchdog_rescue_editable_keys=(),
        )
        executor = RescueActionExecutor(config=config, engine=SimpleNamespace())

        with patch('openclaw_watchdog.rescue_actions.last_good_runtime.protected_paths_snapshot', return_value=[{'label': 'openclaw_config'}]) as snapshot_mock:
            self.assertEqual(executor._protected_paths_snapshot(), [{'label': 'openclaw_config'}])

        with patch('openclaw_watchdog.rescue_actions.last_good_runtime.record_guard_event') as event_mock:
            executor._record_guard_event(
                phase='after',
                before=[{'label': 'openclaw_config'}],
                after=[{'label': 'openclaw_config'}],
                validation='applied',
                context={'plan_id': 'plan-1'},
            )

        snapshot_mock.assert_called_once_with(config)
        event_mock.assert_called_once_with(
            config,
            operation='rescue-update-openclaw-config',
            phase='after',
            before=[{'label': 'openclaw_config'}],
            after=[{'label': 'openclaw_config'}],
            validation='applied',
            context={'plan_id': 'plan-1'},
        )

    def test_survival_mode_uses_last_good_runtime_helpers(self) -> None:
        from openclaw_watchdog import survival

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            openclaw_config = root / 'openclaw.json'
            openclaw_config.write_text(
                json.dumps({'channels': {'qqbot': {'enabled': True}, 'feishu': {'enabled': True}}}),
                encoding='utf-8',
            )
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_enable_survival_mode=True,
                    watchdog_survival_required_channels=('qqbot',),
                    watchdog_survival_disable_optional_extensions=True,
                    watchdog_survival_state_file=root / 'survival-state.json',
                    watchdog_survival_config_file=root / 'survival.json',
                    watchdog_rollback_archive_dir=root / 'rollback',
                    openclaw_config=openclaw_config,
                    watchdog_survival_stable_ready_runs=2,
                ),
                ctx=SimpleNamespace(),
                now_iso=lambda: '2026-03-12T21:30:00+08:00',
                log=lambda level, message: None,
            )

            with patch('openclaw_watchdog.survival_transition_runtime.guard_runtime.protected_paths_snapshot', return_value=[{'label': 'openclaw_config'}]) as snapshot_mock:
                with patch('openclaw_watchdog.survival_transition_runtime.guard_runtime.record_guard_event') as event_mock:
                    with patch('openclaw_watchdog.survival_transition_runtime.guard_runtime.fingerprint_path', return_value='fp-1') as fingerprint_mock:
                        result = survival.enter_survival_mode(engine, reason='unit-test')

        self.assertTrue(result['applied'])
        fingerprint_mock.assert_any_call(openclaw_config)
        snapshot_mock.assert_any_call(engine.config)
        self.assertEqual(event_mock.call_count, 2)


if __name__ == '__main__':
    unittest.main()
