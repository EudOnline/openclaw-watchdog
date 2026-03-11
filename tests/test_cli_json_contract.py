from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from watchdog_v2.cli import main


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

    def metrics_payload(self) -> dict[str, object]:
        return {
            'status': 'healthy',
            'health_level': 'healthy',
            'service_active': True,
            'conversation_ready': True,
            'minimal_usable_ready': True,
            'survival_mode_active': False,
            'survival_mode_exit_ready': True,
            'last_recovery_action_count': 4,
            'rescue_attempt_count': 5,
            'rescue_executor_selected': 'litellm',
            'rescue_plan_generated': True,
            'rescue_plan_status': 'applied',
            'rescue_tier': 'litellm',
            'candidate_rule_status': 'pending-review',
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
        with patch('watchdog_v2.cli.Config.load', return_value=object()):
            with patch('watchdog_v2.cli.WatchdogEngine', return_value=fake_engine):
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

    def test_metrics_prometheus_keeps_stable_metric_names(self) -> None:
        exit_code, output = self._run_cli(['metrics', '--prometheus'])

        self.assertEqual(exit_code, 0)
        self.assertIn('openclaw_watchdog_info', output)
        self.assertIn('openclaw_watchdog_service_active', output)
        self.assertIn('openclaw_watchdog_conversation_ready', output)


if __name__ == '__main__':
    unittest.main()
