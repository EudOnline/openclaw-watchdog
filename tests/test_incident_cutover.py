from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class IncidentCutoverTests(unittest.TestCase):
    def test_incident_service_facade_delegates_read_and_write_helpers_to_owner_runtimes(self) -> None:
        from openclaw_watchdog import incident_service

        read_mock = Mock(return_value={'state': 'open'})
        write_mock = Mock()

        with TemporaryDirectory() as temp_dir:
            incident_dir = Path(temp_dir) / 'incident-1'
            engine = SimpleNamespace(
                ctx=SimpleNamespace(incident_id='incident-1', incident_dir=incident_dir),
                now_iso=lambda: '2026-03-12T22:10:00+08:00',
            )

            with patch.object(
                incident_service,
                'incident_read_runtime',
                SimpleNamespace(read_incident_state_payload=read_mock),
                create=True,
            ):
                payload = incident_service.read_incident_state_payload(engine, incident_dir)
            with patch.object(
                incident_service,
                'incident_write_runtime',
                SimpleNamespace(update_incident_state=write_mock),
                create=True,
            ):
                incident_service.update_incident_state(engine, 'open', 'gateway degraded')

        self.assertEqual(payload, {'state': 'open'})
        read_mock.assert_called_once_with(engine, incident_dir)
        write_mock.assert_called_once_with(engine, 'open', 'gateway degraded', resolved=False)

    def test_incidents_facade_delegates_read_and_workflow_owners(self) -> None:
        from openclaw_watchdog import incidents

        snapshot_mock = Mock(return_value={'incident_id': 'incident-9'})
        queue_mock = Mock(return_value={'summary': {'open_total': 1}, 'incidents': []})
        assign_mock = Mock(return_value={'incident_id': 'incident-9', 'owner': 'alice'})

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incident_dir = root / 'incident-9'
            incident_dir.mkdir()
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_incidents_dir=root,
                    watchdog_incident_index_file=root / 'incident-index.json',
                    watchdog_incident_index_limit=20,
                ),
                read_run_state=lambda: {},
                now_iso=lambda: '2026-03-12T22:11:00+08:00',
                ctx=SimpleNamespace(
                    run_ts='2026-03-12 22:11:00 CST',
                    pre_repair_backup_result='not-run',
                    rollback_occurred=False,
                    rollback_summary_archive_file='',
                    rollback_candidate_used='',
                    rollback_reason='',
                    last_recovery_strategy='none',
                ),
                recovery_path_text=lambda: 'none',
            )

            with patch.object(
                incidents,
                'incident_read_runtime',
                SimpleNamespace(incident_snapshot=snapshot_mock, incident_queue_payload=queue_mock),
                create=True,
            ):
                snapshot = incidents.incident_snapshot(engine, incident_dir)
                queue = incidents.incident_queue_payload(engine, limit=5)
            with patch.object(
                incidents,
                'incident_write_runtime',
                SimpleNamespace(set_incident_owner=assign_mock),
                create=True,
            ):
                assigned = incidents.set_incident_owner(engine, 'incident-9', 'alice')

        self.assertEqual(snapshot['incident_id'], 'incident-9')
        self.assertEqual(queue['summary']['open_total'], 1)
        self.assertEqual(assigned['owner'], 'alice')
        snapshot_mock.assert_called_once_with(engine, incident_dir)
        queue_mock.assert_called_once_with(engine, limit=5)
        assign_mock.assert_called_once_with(engine, 'incident-9', 'alice')

    def test_incidents_module_uses_incident_read_runtime_directly(self) -> None:
        from openclaw_watchdog import incidents

        with TemporaryDirectory() as temp_dir:
            incident_dir = Path(temp_dir) / 'incident-1'
            incident_dir.mkdir()
            (incident_dir / 'artifact.txt').write_text('artifact', encoding='utf-8')
            engine = SimpleNamespace(config=SimpleNamespace())

            with patch('openclaw_watchdog.incidents.incident_read_runtime.read_incident_state_payload', return_value={'state': 'open', 'created_at': '2026-03-12T22:10:00+08:00'}) as state_mock:
                with patch('openclaw_watchdog.incidents.incident_read_runtime.read_incident_operator_summary_payload', return_value={'summary': 'gateway degraded', 'health_level': 'failed', 'active': 'inactive', 'main_pid': '0', 'listeners': 'none'}) as summary_mock:
                    with patch('openclaw_watchdog.incidents.incident_read_runtime.read_incident_operator_workflow_payload', return_value={'owner': '', 'acknowledged': False, 'notes': [], 'events': []}) as workflow_mock:
                        with patch('openclaw_watchdog.incidents.incident_read_runtime.read_incident_index', return_value=[]) as index_mock:
                            with patch('openclaw_watchdog.incidents.incident_read_runtime.incident_bool', side_effect=lambda value: bool(value)) as bool_mock:
                                snapshot = incidents.incident_snapshot(engine, incident_dir)

        self.assertEqual(snapshot['incident_id'], 'incident-1')
        self.assertEqual(snapshot['summary'], 'gateway degraded')
        state_mock.assert_called_once_with(engine, incident_dir)
        summary_mock.assert_called_once_with(engine, incident_dir)
        workflow_mock.assert_called_once_with(engine, incident_dir)
        index_mock.assert_called_once_with(engine)
        self.assertEqual(bool_mock.call_count, 2)

    def test_reporting_uses_incident_ops_directly(self) -> None:
        from openclaw_watchdog import metrics_runtime
        from openclaw_watchdog import report_payload_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_last_report_file=root / 'last-report.json',
                    watchdog_last_metrics_file=root / 'last-metrics.json',
                ),
                now_iso=lambda: '2026-03-12T22:20:00+08:00',
                status_payload=lambda: {
                    'env_file': 'config.env',
                    'last_status': 'failed',
                    'health_level': 'failed',
                    'current_mode': 'failed',
                    'service_active': False,
                    'process_layer_healthy': False,
                    'service_layer_healthy': False,
                    'conversation_ready': False,
                    'minimal_usable_ready': False,
                    'conversation_status': 'down',
                    'service_probe_summary': 'down',
                    'conversation_probe_summary': 'down',
                    'maintenance': {'enabled': False},
                    'survival_mode_active': False,
                    'survival_mode_exit_ready': False,
                    'survival_mode_actions': [],
                    'survival_mode_disabled_features': [],
                    'survival_mode_exit_blockers': [],
                    'survival_mode_stable_ready_runs': 0,
                    'survival_mode_stable_required_runs': 2,
                    'consecutive_failures': 2,
                    'current_incident_id': 'incident-1',
                    'current_incident_state': 'open',
                    'recent_event_stats': {'counts': {'healthy': 0, 'degraded': 0, 'recovered': 0, 'failed': 1}},
                    'last_event': {'summary': 'failed', 'human_summary': 'failed'},
                    'incident_queue_summary': {'open_total': 1, 'attention_total': 1, 'handled_total': 0},
                    'recent_incidents': [],
                    'run_state': {},
                },
            )

            with patch('openclaw_watchdog.report_payload_runtime.health_ops.status_payload', side_effect=lambda runtime_engine: runtime_engine.status_payload()):
                with patch('openclaw_watchdog.report_payload_runtime.incident_ops.current_incident_payload', return_value={'incident_id': 'incident-1', 'owner': '', 'acknowledged': False, 'notes_count': 0}) as current_mock:
                    with patch('openclaw_watchdog.report_payload_runtime.incident_ops.list_incident_snapshots', return_value=[{'incident_id': 'incident-1', 'state': 'open'}]) as list_mock:
                        report = report_payload_runtime.report_payload(engine, incident_limit=3)
                        metrics = metrics_runtime.metrics_payload(engine)

        self.assertEqual(report['current_incident_id'], 'incident-1')
        self.assertFalse(metrics['current_incident_acknowledged'])
        current_mock.assert_called()
        list_mock.assert_called()

    def test_health_status_payload_uses_incident_ops_directly(self) -> None:
        from openclaw_watchdog import health_status_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            last_status_file = root / 'state' / 'last-status'
            current_marker = root / 'state' / 'current-incident-id'
            last_status_file.parent.mkdir(parents=True, exist_ok=True)
            current_marker.parent.mkdir(parents=True, exist_ok=True)
            last_status_file.write_text('failed\n', encoding='utf-8')
            current_marker.write_text('incident-1\n', encoding='utf-8')
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    env_file=None,
                    watchdog_state_dir=root / 'state',
                    watchdog_event_history_file=root / 'state' / 'event-history.jsonl',
                    watchdog_last_good_config=root / 'state' / 'last-good.json',
                    watchdog_last_good_manifest_file=root / 'state' / 'last-good-manifest.json',
                    watchdog_incidents_dir=root / 'incidents',
                    watchdog_maintenance_file=root / 'state' / 'maintenance.flag',
                    watchdog_survival_stable_ready_runs=2,
                    watchdog_guard_manifest_file=root / 'state' / 'guard.json',
                ),
                last_status_file=last_status_file,
                current_incident_marker=current_marker,
                read_run_state=lambda: {'current_incident_state': 'open', 'current_incident_age_seconds': 0, 'health_level': 'failed'},
                read_failure_count=lambda: 2,
                read_event_history=lambda limit=5: [],
                recent_event_stats=lambda hours=24: {'counts': {'failed': 1}},
                last_good_status=lambda: {'last_good_generation_id': ''},
                guard_status=lambda: {'guard_last_operation': ''},
                now_iso=lambda: '2026-03-12T22:30:00+08:00',
                current_mode=lambda **kwargs: 'normal',
            )

            with patch('openclaw_watchdog.health_status_runtime.read_last_event', return_value={'summary': 'failed'}):
                with patch('openclaw_watchdog.health_status_runtime.health_probe_runtime.live_probe', return_value={'health_level': 'failed', 'conversation_ready': False, 'minimal_usable_ready': False, 'conversation_status': 'down'}):
                    with patch('openclaw_watchdog.health_status_runtime.incident_ops.incident_queue_payload', return_value={'summary': {'open_total': 1}, 'incidents': []}) as queue_mock:
                        with patch('openclaw_watchdog.health_status_runtime.incident_ops.list_incident_snapshots', return_value=[{'incident_id': 'incident-1'}]) as list_mock:
                            payload = health_status_runtime.status_payload(engine)

        self.assertEqual(payload['incident_queue_summary']['open_total'], 1)
        self.assertEqual(payload['recent_incidents'], [{'incident_id': 'incident-1'}])
        queue_mock.assert_called_once_with(engine, limit=5)
        list_mock.assert_called_once_with(engine, limit=5)

    def test_state_transition_uses_incident_service_directly(self) -> None:
        from openclaw_watchdog import state_transition
        from openclaw_watchdog.run_context import RunContext

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            last_status_file = root / 'state' / 'last-status'
            last_status_file.parent.mkdir(parents=True, exist_ok=True)
            last_status_file.write_text('failed', encoding='utf-8')
            incident_backup_marker = root / 'state' / 'incident-backup-done'
            incident_backup_marker.write_text('1', encoding='utf-8')
            ctx = RunContext.initial(stable_required_runs=2)
            ctx.incident_id = 'incident-1'
            ctx.incident_dir = root / 'incidents' / 'incident-1'
            ctx.run_ts = '2026-03-12 22:40:00 CST'
            ctx.pre_repair_backup_result = 'success'
            ctx.last_recovery_strategy = 'rollback'
            ctx.last_recovery_action_count = 2
            ctx.last_recovery_restored_conversation = True
            ctx.latest_probe = {
                'conversation_ready': True,
                'minimal_usable_ready': True,
                'conversation_status': 'ready',
                'conversation_probe_summary': 'ready',
            }
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_maintenance_file=root / 'state' / 'maintenance.flag',
                    watchdog_notify_on_degraded=True,
                    watchdog_notify_on_recovery=True,
                    watchdog_notify_on_failure=True,
                    watchdog_guard_manifest_file=root / 'state' / 'guard.json',
                ),
                last_status_file=last_status_file,
                incident_backup_marker=incident_backup_marker,
                ctx=ctx,
                current_mode=lambda **kwargs: 'normal',
                recovery_path_text=lambda: 'restart -> rollback',
                guard_status=lambda: {'guard_manifest_file': 'guard.json', 'guard_last_operation': '', 'guard_last_phase': '', 'guard_last_time': '', 'guard_last_summary': ''},
                reset_failure_count=lambda: None,
                write_run_state=lambda updates: updates,
                append_rollback_summary=lambda text: text,
                notify=lambda message: None,
            )
            write_event_mock = Mock()
            report_mock = Mock(return_value={'message_text': 'operator summary'})

            with patch('openclaw_watchdog.state_transition.incident_service_ops.attach_current_incident_if_any', return_value=True) as attach_mock:
                with patch('openclaw_watchdog.state_transition.incident_service_ops.update_incident_state') as update_mock:
                    with patch('openclaw_watchdog.state_transition.incident_service_ops.refresh_current_incident_index') as refresh_mock:
                        with patch('openclaw_watchdog.state_transition.incident_service_ops.reset_incident_state') as reset_mock:
                            with patch.object(state_transition, 'event_runtime', SimpleNamespace(write_event=write_event_mock), create=True):
                                with patch.object(state_transition, 'reporting_ops', SimpleNamespace(report_payload=report_mock), create=True):
                                    state_transition.set_state(engine, 'healthy', 'all good', health_level_override='healthy')

        attach_mock.assert_called_once_with(engine)
        update_mock.assert_called_once_with(engine, 'resolved', 'all good', resolved=True)
        refresh_mock.assert_called_once_with(engine, summary='all good', health_level='healthy')
        reset_mock.assert_called_once_with(engine)
        write_event_mock.assert_called_once_with(engine, 'healthy', 'all good')
        report_mock.assert_called_once_with(engine, incident_limit=5)

    def test_cli_incident_commands_use_incident_ops_directly(self) -> None:
        from openclaw_watchdog.cli import main

        class FakeEngine:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        emitted: list[dict[str, object]] = []
        with patch('openclaw_watchdog.cli.Config.load', return_value=object()):
            with patch('openclaw_watchdog.cli.WatchdogEngine', return_value=FakeEngine()):
                with patch('openclaw_watchdog.cli.incident_ops.current_incident_payload', return_value={'incident_id': 'incident-1'}) as current_mock:
                    with patch('openclaw_watchdog.cli.incident_ops.set_incident_owner', return_value={'incident_id': 'incident-1', 'owner': 'alice'}) as assign_mock:
                        with patch('openclaw_watchdog.cli._print_json', side_effect=lambda payload: emitted.append(payload)):
                            current_exit = main(['incidents', 'current', '--json'])
                            assign_exit = main(['incidents', 'assign', 'incident-1', '--owner', 'alice', '--json'])

        self.assertEqual(current_exit, 0)
        self.assertEqual(assign_exit, 0)
        self.assertEqual(emitted[0]['incident_id'], 'incident-1')
        self.assertEqual(emitted[1]['owner'], 'alice')
        current_mock.assert_called()
        assign_mock.assert_called()


if __name__ == '__main__':
    unittest.main()
