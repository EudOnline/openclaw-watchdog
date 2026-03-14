from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openclaw_watchdog.cli import main


class _FakeEngine:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def report_payload(self, *, incident_limit: int = 5) -> dict[str, object]:
        return {
            'status': 'healthy',
            'health_level': 'healthy',
            'current_mode': 'normal',
            'conversation_status': 'ready',
            'conversation_ready': True,
            'minimal_usable_ready': True,
            'last_recovery_strategy': 'litellm',
            'last_recovery_path': 'restart -> rollback -> survival -> doctor',
            'last_recovery_action_count': 4,
            'last_recovery_restored_conversation': True,
            'rescue_attempt_count': 5,
            'rescue_executor_selected': 'litellm',
            'rescue_plan_generated': True,
            'rescue_plan_source': 'litellm',
            'rescue_plan_status': 'applied',
            'rescue_tier': 'litellm',
            'case_ingest_result': 'recorded:case-1.json',
            'candidate_rule_status': 'pending-review',
            'rescue_attempt_order': ['codex', 'claude-code', 'litellm'],
            'rescue_rejected_executors': ['codex:unavailable', 'claude-code:no-plan'],
            'rescue_learning_summary': 'recorded:case-1.json / pending-review',
            'rescue_mutation_scope': ['restart_service', 'update_openclaw_config'],
            'rollback_candidate_used': '',
            'config_drift_detected': False,
            'current_incident_id': '',
            'operator_attention_needed': False,
            'operator_attention_items': [],
            'recent_incidents': [],
            'message_text': 'ok',
        }

    def status_payload(self) -> dict[str, object]:
        return {
            'last_status': 'healthy',
            'health_level': 'healthy',
            'current_mode': 'normal',
            'service_active': True,
            'process_layer_healthy': True,
            'service_layer_healthy': True,
            'conversation_ready': True,
            'minimal_usable_ready': True,
            'conversation_status': 'ready',
            'last_recovery_strategy': 'litellm',
            'last_recovery_path': 'restart -> rollback -> survival -> doctor',
            'last_recovery_action_count': 4,
            'last_recovery_restored_conversation': True,
            'rescue_attempt_count': 5,
            'rescue_executor_selected': 'litellm',
            'rescue_plan_generated': True,
            'rescue_plan_source': 'litellm',
            'rescue_plan_status': 'applied',
            'rescue_tier': 'litellm',
            'case_ingest_result': 'recorded:case-1.json',
            'candidate_rule_status': 'pending-review',
            'rescue_attempt_order': ['codex', 'claude-code', 'litellm'],
            'rescue_rejected_executors': ['codex:unavailable', 'claude-code:no-plan'],
            'rescue_learning_summary': 'recorded:case-1.json / pending-review',
            'rescue_mutation_scope': ['restart_service', 'update_openclaw_config'],
            'config_drift_detected': False,
            'survival_mode_active': False,
            'survival_mode_exit_ready': True,
            'maintenance': {'enabled': False},
            'last_event': {'human_summary': 'ok'},
            'recent_event_stats': {'counts': {'healthy': 2, 'degraded': 0, 'recovered': 1, 'failed': 0}},
            'recent_incidents': [],
            'incident_queue_summary': {'open_total': 0, 'attention_total': 0, 'handled_total': 0},
            'healthy': True,
            'healthy_raw': True,
            'service_probe_summary': 'ok',
            'conversation_probe_summary': 'ready',
            'run_state': {},
            'recent_events': [],
        }

    def metrics_payload(self) -> dict[str, object]:
        return {
            'status': 'healthy',
            'health_level': 'healthy',
            'service_active': True,
            'conversation_ready': True,
            'minimal_usable_ready': True,
            'survival_mode_active': False,
            'survival_mode_exit_ready': True,
            'last_recovery_strategy': 'litellm',
            'last_recovery_path': 'restart -> rollback -> survival -> doctor',
            'last_recovery_action_count': 4,
            'last_recovery_restored_conversation': True,
            'rescue_attempt_count': 5,
            'rescue_executor_selected': 'litellm',
            'rescue_plan_generated': True,
            'rescue_plan_source': 'litellm',
            'rescue_plan_status': 'applied',
            'rescue_tier': 'litellm',
            'candidate_rule_status': 'pending-review',
            'rescue_attempt_order': ['codex', 'claude-code', 'litellm'],
            'rescue_rejected_executors': ['codex:unavailable', 'claude-code:no-plan'],
            'rescue_learning_summary': 'recorded:case-1.json / pending-review',
            'rescue_mutation_scope': ['restart_service', 'update_openclaw_config'],
            'config_drift_detected': False,
            'current_incident_open': False,
            'current_incident_acknowledged': False,
            'current_incident_notes_count': 0,
            'current_incident_owner_assigned': False,
            'recent_healthy_total': 2,
            'recent_degraded_total': 0,
            'recent_recovered_total': 1,
            'recent_failed_total': 0,
        }

    def prometheus_metrics_text(self, payload: dict[str, object]) -> str:
        return '\n'.join(
            [
                '# HELP openclaw_watchdog_info Current watchdog info.',
                '# TYPE openclaw_watchdog_info gauge',
                'openclaw_watchdog_info{status="healthy"} 1',
                'openclaw_watchdog_service_active 1',
                'openclaw_watchdog_conversation_ready 1',
            ]
        ) + '\n'


class CliJsonContractTest(unittest.TestCase):
    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        stdout = io.StringIO()
        fake_engine = _FakeEngine()
        with patch('openclaw_watchdog.cli.Config.load', return_value=object()):
            with patch('openclaw_watchdog.cli.WatchdogEngine', return_value=fake_engine):
                with patch('openclaw_watchdog.cli.health_ops.status_payload', side_effect=lambda engine: engine.status_payload()):
                    with patch('openclaw_watchdog.cli.reporting_ops.report_payload', side_effect=lambda engine, incident_limit=5: engine.report_payload(incident_limit=incident_limit)):
                        with patch('openclaw_watchdog.cli.reporting_ops.metrics_payload', side_effect=lambda engine: engine.metrics_payload()):
                            with redirect_stdout(stdout):
                                exit_code = main(argv)
        return exit_code, stdout.getvalue()

    def test_report_json_keeps_stable_top_level_keys(self) -> None:
        exit_code, output = self._run_cli(['report', '--json'])
        payload = json.loads(output)

        self.assertEqual(exit_code, 0)
        self.assertTrue(
            {
                'status',
                'health_level',
                'current_mode',
                'conversation_status',
                'conversation_ready',
                'minimal_usable_ready',
                'last_recovery_strategy',
                'rescue_executor_selected',
                'rescue_plan_generated',
                'candidate_rule_status',
                'rescue_attempt_order',
                'rescue_rejected_executors',
                'rescue_learning_summary',
                'rescue_mutation_scope',
                'current_incident_id',
                'operator_attention_needed',
                'operator_attention_items',
                'recent_incidents',
                'message_text',
            }.issubset(payload)
        )
        self.assertNotIn('recent_incident_summaries', payload)

    def test_metrics_json_keeps_stable_top_level_keys(self) -> None:
        exit_code, output = self._run_cli(['metrics', '--json'])
        payload = json.loads(output)

        self.assertEqual(exit_code, 0)
        self.assertTrue(
            {
                'status',
                'health_level',
                'service_active',
                'conversation_ready',
                'minimal_usable_ready',
                'survival_mode_active',
                'last_recovery_action_count',
                'rescue_attempt_count',
                'rescue_executor_selected',
                'candidate_rule_status',
                'config_drift_detected',
                'current_incident_open',
                'current_incident_acknowledged',
                'current_incident_notes_count',
                'current_incident_owner_assigned',
                'recent_healthy_total',
                'recent_degraded_total',
                'recent_recovered_total',
                'recent_failed_total',
            }.issubset(payload)
        )
        self.assertNotIn('current_incident_events_count', payload)
        self.assertNotIn('current_incident_latest_event_type', payload)

    def test_status_report_metrics_share_operator_snapshot_keys(self) -> None:
        from openclaw_watchdog.operator_snapshot import OPERATOR_SNAPSHOT_KEYS

        status_exit_code, status_output = self._run_cli(['status', '--json'])
        report_exit_code, report_output = self._run_cli(['report', '--json'])
        metrics_exit_code, metrics_output = self._run_cli(['metrics', '--json'])

        status_payload = json.loads(status_output)
        report_payload = json.loads(report_output)
        metrics_payload = json.loads(metrics_output)

        self.assertEqual(status_exit_code, 0)
        self.assertEqual(report_exit_code, 0)
        self.assertEqual(metrics_exit_code, 0)
        shared_keys = {
            'last_recovery_strategy',
            'last_recovery_path',
            'rescue_attempt_order',
            'rescue_rejected_executors',
            'rescue_learning_summary',
            'rescue_mutation_scope',
        }
        self.assertTrue(shared_keys.issubset(OPERATOR_SNAPSHOT_KEYS))
        self.assertTrue(shared_keys.issubset(status_payload))
        self.assertTrue(shared_keys.issubset(report_payload))
        self.assertTrue(shared_keys.issubset(metrics_payload))

    def test_metrics_prometheus_keeps_stable_metric_names(self) -> None:
        exit_code, output = self._run_cli(['metrics', '--prometheus'])

        self.assertEqual(exit_code, 0)
        self.assertIn('openclaw_watchdog_info', output)
        self.assertIn('openclaw_watchdog_service_active', output)
        self.assertIn('openclaw_watchdog_conversation_ready', output)

    def test_reporting_facade_delegates_to_runtime_modules(self) -> None:
        from openclaw_watchdog import reporting

        engine = object()
        report_mock = Mock(return_value={'status': 'healthy'})
        metrics_mock = Mock(return_value={'status': 'healthy'})
        prometheus_mock = Mock(return_value='metric 1\n')

        with patch.object(reporting, 'report_payload_runtime', SimpleNamespace(report_payload=report_mock), create=True):
            report = reporting.report_payload(engine, incident_limit=4)
        with patch.object(reporting, 'metrics_runtime', SimpleNamespace(metrics_payload=metrics_mock, prometheus_metrics_text=prometheus_mock), create=True):
            metrics = reporting.metrics_payload(engine)
            text = reporting.prometheus_metrics_text({'status': 'healthy'})

        self.assertEqual(report, {'status': 'healthy'})
        self.assertEqual(metrics, {'status': 'healthy'})
        self.assertEqual(text, 'metric 1\n')
        report_mock.assert_called_once_with(engine, incident_limit=4)
        metrics_mock.assert_called_once_with(engine)
        prometheus_mock.assert_called_once_with({'status': 'healthy'})

    def test_incidents_current_json_keeps_workflow_fields(self) -> None:
        stdout = io.StringIO()
        fake_engine = _FakeEngine()

        with patch('openclaw_watchdog.cli.Config.load', return_value=object()):
            with patch('openclaw_watchdog.cli.WatchdogEngine', return_value=fake_engine):
                with patch(
                    'openclaw_watchdog.cli.incident_ops.current_incident_payload',
                    return_value={
                        'incident_id': 'incident-5',
                        'state': 'open',
                        'owner': 'alice',
                        'acknowledged': True,
                        'notes_count': 2,
                        'attention_needed': False,
                    },
                ):
                    with redirect_stdout(stdout):
                        exit_code = main(['incidents', 'current', '--json'])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload['incident_id'], 'incident-5')
        self.assertEqual(payload['owner'], 'alice')
        self.assertTrue(payload['acknowledged'])
        self.assertEqual(payload['notes_count'], 2)


if __name__ == '__main__':
    unittest.main()
