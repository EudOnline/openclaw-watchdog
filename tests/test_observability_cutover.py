from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from openclaw_watchdog.engine import WatchdogEngine


class ObservabilityCutoverTests(unittest.TestCase):
    def test_watchdog_engine_no_longer_exposes_intermediate_health_proxies(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'service_level_probe'))
        self.assertFalse(hasattr(WatchdogEngine, 'raw_live_probe'))
        self.assertFalse(hasattr(WatchdogEngine, 'healthy_now'))
        self.assertFalse(hasattr(WatchdogEngine, 'live_probe'))
        self.assertFalse(hasattr(WatchdogEngine, 'status_payload'))
        self.assertFalse(hasattr(WatchdogEngine, 'metrics_payload'))
        self.assertFalse(hasattr(WatchdogEngine, 'maintenance_on'))
        self.assertFalse(hasattr(WatchdogEngine, 'maintenance_off'))
        self.assertFalse(hasattr(WatchdogEngine, 'write_event'))
        self.assertFalse(hasattr(WatchdogEngine, 'set_state'))
        self.assertFalse(hasattr(WatchdogEngine, 'report_payload'))

    def test_cli_check_uses_health_module_directly(self) -> None:
        from openclaw_watchdog.cli import main

        class FakeEngine:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        stdout = io.StringIO()
        fake_engine = FakeEngine()
        with patch('openclaw_watchdog.cli.Config.load', return_value=object()):
            with patch('openclaw_watchdog.cli.WatchdogEngine', return_value=fake_engine):
                with patch('openclaw_watchdog.cli.health_ops.live_probe', return_value={'healthy': True}) as probe_mock:
                    with redirect_stdout(stdout):
                        exit_code = main(['check', '--json'])

        self.assertEqual(exit_code, 0)
        self.assertIn('"healthy": true', stdout.getvalue())
        probe_mock.assert_called_once_with(fake_engine, include_doctor=True)

    def test_event_runtime_uses_event_history_module_directly(self) -> None:
        from openclaw_watchdog import event_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            event_file = root / 'event.txt'
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_event_file=event_file,
                    watchdog_last_rollback_summary_file=root / 'rollback-summary.txt',
                ),
                ctx=SimpleNamespace(
                    run_ts='2026-03-13 09:00:00 CST',
                    rollback_occurred=False,
                    rollback_summary_archive_file='',
                    rollback_broken_config_file='',
                    pre_repair_backup_result='not-run',
                    consecutive_failures=0,
                    incident_id='',
                    incident_dir=None,
                ),
                read_run_state=lambda: {'health_level': 'healthy'},
                sibling_json_path=lambda path: path.with_suffix('.json'),
            )

            with patch('openclaw_watchdog.event_runtime.event_history.append_event_history') as history_mock:
                event_runtime.write_event(engine, 'healthy', 'ok')

            json_payload = json.loads(event_file.with_suffix('.json').read_text(encoding='utf-8'))

        history_mock.assert_called_once_with(engine, json_payload)

    def test_health_status_payload_uses_event_history_and_last_good_modules_directly(self) -> None:
        from openclaw_watchdog import health_status_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            last_status_file = root / 'state' / 'last-status'
            current_marker = root / 'state' / 'current-incident-id'
            last_status_file.parent.mkdir(parents=True, exist_ok=True)
            current_marker.parent.mkdir(parents=True, exist_ok=True)
            last_status_file.write_text('healthy\n', encoding='utf-8')
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    env_file=None,
                    watchdog_state_dir=root / 'state',
                    watchdog_last_good_config=root / 'state' / 'last-good.json',
                    watchdog_incidents_dir=root / 'incidents',
                    watchdog_maintenance_file=root / 'state' / 'maintenance.flag',
                    watchdog_survival_stable_ready_runs=2,
                    watchdog_guard_manifest_file=root / 'state' / 'guard.json',
                ),
                last_status_file=last_status_file,
                current_incident_marker=current_marker,
                read_run_state=lambda: {'current_incident_state': '', 'current_incident_age_seconds': 0, 'health_level': 'healthy'},
                read_failure_count=lambda: 0,
                now_iso=lambda: '2026-03-13T09:10:00+08:00',
                current_mode=lambda **kwargs: 'normal',
            )

            with patch('openclaw_watchdog.health_status_runtime.read_last_event', return_value={'summary': 'ok'}):
                with patch('openclaw_watchdog.health_status_runtime.health_probe_runtime.live_probe', return_value={'health_level': 'healthy', 'conversation_ready': True, 'minimal_usable_ready': True, 'conversation_status': 'ready'}):
                    with patch('openclaw_watchdog.health_status_runtime.event_history.read_event_history', return_value=[{'status': 'healthy'}]) as read_mock:
                        with patch('openclaw_watchdog.health_status_runtime.event_history.recent_event_stats', return_value={'counts': {'healthy': 1}}) as stats_mock:
                            with patch('openclaw_watchdog.health_status_runtime.last_good_runtime.last_good_status', return_value={'last_good_generation_id': 'gen-1'}) as last_good_mock:
                                with patch('openclaw_watchdog.health_status_runtime.last_good_runtime.guard_status', return_value={'guard_last_operation': 'validate'}) as guard_mock:
                                    with patch('openclaw_watchdog.health_status_runtime.incident_ops.incident_queue_payload', return_value={'summary': {}, 'incidents': []}):
                                        with patch('openclaw_watchdog.health_status_runtime.incident_ops.list_incident_snapshots', return_value=[]):
                                            payload = health_status_runtime.status_payload(engine)

        self.assertEqual(payload['recent_events'], [{'status': 'healthy'}])
        self.assertEqual(payload['recent_event_stats'], {'counts': {'healthy': 1}})
        self.assertEqual(payload['last_good_generation_id'], 'gen-1')
        self.assertEqual(payload['guard_last_operation'], 'validate')
        read_mock.assert_called_once_with(engine, limit=5)
        stats_mock.assert_called_once_with(engine, hours=24)
        last_good_mock.assert_called_once_with(engine)
        guard_mock.assert_called_once_with(engine.config)

    def test_health_facade_delegates_status_and_live_probe_to_runtime_modules(self) -> None:
        from openclaw_watchdog import health

        engine = object()
        live_probe_mock = Mock(return_value={'healthy': True})
        status_payload_mock = Mock(return_value={'health_level': 'healthy'})

        with patch.object(health, 'health_probe_runtime', SimpleNamespace(live_probe=live_probe_mock), create=True):
            live_payload = health.live_probe(engine, include_doctor=True, apply_grace=False)
        with patch.object(health, 'health_status_runtime', SimpleNamespace(status_payload=status_payload_mock), create=True):
            status = health.status_payload(engine)

        self.assertEqual(live_payload, {'healthy': True})
        self.assertEqual(status, {'health_level': 'healthy'})
        live_probe_mock.assert_called_once_with(engine, include_doctor=True, apply_grace=False)
        status_payload_mock.assert_called_once_with(engine)

    def test_state_transition_uses_last_good_runtime_guard_status_directly(self) -> None:
        from openclaw_watchdog import state_transition
        from openclaw_watchdog.run_context import RunContext

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            last_status_file = root / 'state' / 'last-status'
            last_status_file.parent.mkdir(parents=True, exist_ok=True)
            last_status_file.write_text('healthy', encoding='utf-8')
            ctx = RunContext.initial(stable_required_runs=2)
            ctx.run_ts = '2026-03-13 09:20:00 CST'
            ctx.latest_probe = {
                'conversation_ready': True,
                'minimal_usable_ready': True,
                'conversation_status': 'ready',
                'conversation_probe_summary': 'ready',
            }
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_maintenance_file=root / 'state' / 'maintenance.flag',
                    watchdog_notify_on_degraded=False,
                    watchdog_notify_on_recovery=False,
                    watchdog_notify_on_failure=False,
                    watchdog_guard_manifest_file=root / 'state' / 'guard.json',
                ),
                last_status_file=last_status_file,
                incident_backup_marker=root / 'state' / 'incident-backup-done',
                ctx=ctx,
                current_mode=lambda **kwargs: 'normal',
                recovery_path_text=lambda: 'none',
                reset_failure_count=lambda: None,
                write_run_state=lambda updates: updates,
                append_rollback_summary=lambda text: text,
                notify=lambda message: None,
            )

            with patch('openclaw_watchdog.state_transition.last_good_runtime.guard_status', return_value={'guard_last_operation': 'validate'}) as guard_mock:
                write_event_mock = Mock()
                report_mock = Mock(return_value={'message_text': 'ok'})
                with patch.object(state_transition, 'event_runtime', SimpleNamespace(write_event=write_event_mock), create=True):
                    with patch.object(state_transition, 'reporting_ops', SimpleNamespace(report_payload=report_mock), create=True):
                        state_transition.set_state(engine, 'degraded', 'degraded', health_level_override='degraded')

        guard_mock.assert_called_once_with(engine.config)
        write_event_mock.assert_called_once_with(engine, 'degraded', 'degraded')
        report_mock.assert_called_once_with(engine, incident_limit=5)

    def test_health_live_probe_uses_doctor_runtime_directly(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        engine = SimpleNamespace(
            config=SimpleNamespace(
                watchdog_enable_survivability_flow=True,
                watchdog_survival_stable_ready_runs=2,
                watchdog_guard_manifest_file=Path('/tmp/guard.json'),
                watchdog_maintenance_file=Path('/tmp/maintenance.flag'),
                watchdog_service_level_retry_grace_seconds=0,
                watchdog_active_no_listener_grace_seconds=0,
            ),
            read_run_state=lambda: {},
            current_mode=lambda **kwargs: 'failed',
        )

        run_doctor_mock = Mock(return_value=(7, 'Config invalid: missing token'))
        config_invalid_mock = Mock(return_value=True)
        with patch('openclaw_watchdog.health_probe_runtime.raw_live_probe', return_value={'healthy': False, 'process_layer_healthy': False, 'service_active': False, 'service_main_pid': '0', 'listener_pids': []}):
            with patch('openclaw_watchdog.health_probe_runtime.service_level_probe', return_value={'service_layer_healthy': False, 'service_probe_summary': 'down', 'service_status_payload': {}, 'service_probe_checked_at': '2026-03-13T10:00:00+08:00'}):
                with patch('openclaw_watchdog.health_probe_runtime.conversation_level_probe', return_value={'conversation_ready': False, 'minimal_usable_ready': False, 'conversation_status': 'down', 'conversation_probe_summary': 'down', 'conversation_probe_checked_at': '2026-03-13T10:00:00+08:00', 'conversation_probe_targets': []}):
                    with patch('openclaw_watchdog.health_probe_runtime.operator_snapshot.build_operator_snapshot', return_value={}):
                        with patch('openclaw_watchdog.health_probe_runtime.operator_snapshot.to_payload', return_value={}):
                            with patch.object(health_probe_runtime, 'doctor_runtime', SimpleNamespace(run_doctor=run_doctor_mock, config_invalid=config_invalid_mock), create=True):
                                payload = health_probe_runtime.live_probe(engine, include_doctor=True, apply_grace=False)

        self.assertEqual(payload['doctor_rc'], 7)
        self.assertTrue(payload['config_invalid'])
        self.assertEqual(payload['doctor_output'], 'Config invalid: missing token')
        run_doctor_mock.assert_called_once_with(engine)
        config_invalid_mock.assert_called_once_with(engine, 'Config invalid: missing token')

    def test_cli_uses_reporting_and_health_modules_directly_for_observability_commands(self) -> None:
        from openclaw_watchdog.cli import main

        class FakeEngine:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def metrics_payload(self) -> dict[str, object]:
                return {'status': 'healthy'}

        stdout = io.StringIO()
        with patch('openclaw_watchdog.cli.Config.load', return_value=object()):
            with patch('openclaw_watchdog.cli.WatchdogEngine', return_value=FakeEngine()):
                with patch('openclaw_watchdog.cli.health_ops.status_payload', return_value={'healthy': True}) as status_mock:
                    with patch('openclaw_watchdog.cli.reporting_ops.report_payload', return_value={'status': 'healthy', 'message_text': 'ok'}) as report_mock:
                        with patch('openclaw_watchdog.cli.reporting_ops.metrics_payload', return_value={'status': 'healthy'}) as metrics_mock:
                            with patch('openclaw_watchdog.cli.reporting_ops.prometheus_metrics_text', return_value='metric 1\n') as prometheus_mock:
                                with patch('openclaw_watchdog.cli.maintenance_runtime.maintenance_on', return_value={'enabled': True}) as maintenance_on_mock:
                                    with patch('openclaw_watchdog.cli.maintenance_runtime.maintenance_off', return_value={'enabled': False}) as maintenance_off_mock:
                                        with patch('openclaw_watchdog.cli.health_ops.maintenance_status_payload', return_value={'enabled': False}) as maintenance_status_mock:
                                            with redirect_stdout(stdout):
                                                status_exit = main(['status', '--json'])
                                                report_exit = main(['report', '--json'])
                                                metrics_exit = main(['metrics', '--prometheus'])
                                                maintenance_status_exit = main(['maintenance', 'status', '--json'])
                                                maintenance_on_exit = main(['maintenance', 'on', '--json'])
                                                maintenance_off_exit = main(['maintenance', 'off', '--json'])

        self.assertEqual(status_exit, 0)
        self.assertEqual(report_exit, 0)
        self.assertEqual(metrics_exit, 0)
        self.assertEqual(maintenance_status_exit, 0)
        self.assertEqual(maintenance_on_exit, 0)
        self.assertEqual(maintenance_off_exit, 0)
        self.assertIn('metric 1', stdout.getvalue())
        status_mock.assert_called_once()
        report_mock.assert_called_once()
        metrics_mock.assert_called_once()
        prometheus_mock.assert_called_once_with({'status': 'healthy'})
        maintenance_status_mock.assert_called_once()
        maintenance_on_mock.assert_called_once()
        maintenance_off_mock.assert_called_once()

    def test_maintenance_runtime_uses_health_module_directly(self) -> None:
        from openclaw_watchdog import maintenance_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = SimpleNamespace(
                config=SimpleNamespace(watchdog_maintenance_file=root / 'state' / 'maintenance.flag'),
                log=lambda level, message: None,
            )

            with patch('openclaw_watchdog.maintenance_runtime.health_ops.maintenance_status_payload', return_value={'enabled': True}) as status_mock:
                self.assertEqual(maintenance_runtime.maintenance_on(engine, 'deploy'), {'enabled': True})

            with patch('openclaw_watchdog.maintenance_runtime.health_ops.maintenance_status_payload', return_value={'enabled': False}) as status_off_mock:
                self.assertEqual(maintenance_runtime.maintenance_off(engine), {'enabled': False})

        status_mock.assert_called_once_with(engine)
        status_off_mock.assert_called_once_with(engine)


if __name__ == '__main__':
    unittest.main()
