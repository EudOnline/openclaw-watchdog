import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openclaw_watchdog.reporting import message_report_text, metrics_payload, prometheus_metrics_text, report_payload


STABLE_REPORT_KEYS = {
    'status',
    'health_level',
    'current_mode',
    'conversation_status',
    'conversation_ready',
    'minimal_usable_ready',
    'last_recovery_strategy',
    'last_recovery_path',
    'last_recovery_action_count',
    'last_recovery_restored_conversation',
    'rescue_attempt_count',
    'rescue_executor_selected',
    'rescue_plan_generated',
    'rescue_plan_source',
    'rescue_plan_status',
    'rescue_tier',
    'case_ingest_result',
    'candidate_rule_status',
    'rescue_attempt_order',
    'rescue_rejected_executors',
    'rescue_learning_summary',
    'rescue_mutation_scope',
    'rollback_candidate_used',
    'config_drift_detected',
    'current_incident_id',
    'operator_attention_needed',
    'operator_attention_items',
    'recent_incidents',
    'message_text',
}

STABLE_METRICS_KEYS = {
    'status',
    'health_level',
    'service_active',
    'conversation_ready',
    'minimal_usable_ready',
    'survival_mode_active',
    'survival_mode_exit_ready',
    'last_recovery_action_count',
    'rescue_attempt_count',
    'rescue_executor_selected',
    'rescue_plan_generated',
    'rescue_plan_status',
    'rescue_tier',
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
}


class FakeEngine:
    def __init__(self, temp_dir: str):
        self.config = SimpleNamespace(
            watchdog_last_report_file=Path(temp_dir) / 'last-report.json',
            watchdog_last_metrics_file=Path(temp_dir) / 'last-metrics.json',
            watchdog_incidents_dir=Path(temp_dir) / 'incidents',
        )

    def now_iso(self) -> str:
        return '2026-03-10T16:00:00+00:00'

    def status_payload(self) -> dict[str, object]:
        return {
            'env_file': 'config/openclaw-watchdog.env',
            'last_status': 'healthy',
            'health_level': 'healthy',
            'current_mode': 'normal',
            'service_active': True,
            'process_layer_healthy': True,
            'service_layer_healthy': True,
            'conversation_ready': True,
            'minimal_usable_ready': True,
            'conversation_status': 'ready',
            'service_probe_summary': 'ok',
            'conversation_probe_summary': 'ready',
            'maintenance': {'enabled': False},
            'survival_mode_active': False,
            'survival_mode_exit_ready': True,
            'survival_mode_actions': [],
            'survival_mode_disabled_features': [],
            'survival_mode_exit_blockers': [],
            'survival_mode_stable_ready_runs': 0,
            'survival_mode_stable_required_runs': 2,
            'consecutive_failures': 0,
            'current_incident_id': '',
            'current_incident_state': '',
            'recent_event_stats': {'counts': {'healthy': 3, 'degraded': 0, 'recovered': 1, 'failed': 0}},
            'last_event': {'summary': 'healthy', 'human_summary': 'healthy'},
            'incident_queue_summary': {'open_total': 0, 'attention_total': 0, 'handled_total': 0},
            'recent_incidents': [],
            'last_recovery_strategy': 'litellm',
            'last_recovery_path': 'restart -> rollback -> survival -> doctor',
            'last_recovery_action_count': 4,
            'last_recovery_restored_conversation': True,
            'rescue_attempt_count': 5,
            'rescue_executor_selected': 'litellm',
            'rescue_plan_generated': True,
            'rescue_plan_source': 'litellm',
            'rescue_plan_id': 'plan-litellm',
            'rescue_plan_status': 'applied',
            'rescue_tier': 'litellm',
            'case_ingest_result': 'recorded:case-1.json',
            'candidate_rule_status': 'pending-review',
            'rescue_attempt_order': ['codex', 'claude-code', 'litellm'],
            'rescue_rejected_executors': ['codex:unavailable', 'claude-code:no-plan'],
            'rescue_learning_summary': 'recorded:case-1.json / pending-review',
            'rescue_mutation_scope': ['restart_service', 'update_openclaw_config'],
            'last_good_validated_at': '2026-03-10T15:00:00+00:00',
            'last_good_generation_id': 'gen-1',
            'last_good_generation_count': 1,
            'rollback_candidate_used': 'none',
            'rollback_reason': '',
            'config_drift_detected': False,
            'drift_scope': [],
            'drift_since_last_good': '',
            'drift_summary': '',
            'guard_manifest_file': 'guard.json',
            'guard_last_operation': 'validate',
            'guard_last_phase': 'after',
            'guard_last_time': '2026-03-10T15:00:00+00:00',
            'guard_last_summary': 'ok',
            'run_state': {
                'service_probe_failures': 0,
                'last_recovery_strategy': 'litellm',
                'last_recovery_path': 'restart -> rollback -> survival -> doctor',
                'last_recovery_action_count': 4,
                'last_recovery_restored_conversation': True,
                'rescue_attempt_count': 5,
                'rescue_executor_selected': 'litellm',
                'rescue_plan_generated': True,
                'rescue_plan_source': 'litellm',
                'rescue_plan_id': 'plan-litellm',
                'rescue_plan_status': 'applied',
                'rescue_tier': 'litellm',
                'case_ingest_result': 'recorded:case-1.json',
                'candidate_rule_status': 'pending-review',
                'rescue_attempt_order': ['codex', 'claude-code', 'litellm'],
                'rescue_rejected_executors': ['codex:unavailable', 'claude-code:no-plan'],
                'rescue_learning_summary': 'recorded:case-1.json / pending-review',
                'rescue_mutation_scope': ['restart_service', 'update_openclaw_config'],
                'last_good_validated_at': '2026-03-10T15:00:00+00:00',
                'last_good_generation_id': 'gen-1',
                'last_good_generation_count': 1,
                'rollback_candidate_used': 'none',
                'rollback_reason': '',
                'config_drift_detected': False,
                'drift_scope': [],
                'drift_since_last_good': '',
                'drift_summary': '',
            },
        }

    def current_incident_payload(self) -> dict[str, object]:
        return {}

    def list_incident_snapshots(self, limit: int = 5, state: str = 'all', owner: str = '', acknowledged=None, has_notes=None, attention_needed=None):
        return []


class ReportingTest(unittest.TestCase):
    def _report_payload(self, engine, *, incident_limit: int = 5) -> dict[str, object]:
        from openclaw_watchdog import report_payload_runtime

        with patch('openclaw_watchdog.report_payload_runtime.health_ops.status_payload', side_effect=lambda runtime_engine: runtime_engine.status_payload()):
            return report_payload_runtime.report_payload(engine, incident_limit=incident_limit)

    def _metrics_payload(self, engine) -> dict[str, object]:
        from openclaw_watchdog import metrics_runtime

        with patch('openclaw_watchdog.metrics_runtime.health_ops.status_payload', side_effect=lambda runtime_engine: runtime_engine.status_payload()):
            return metrics_runtime.metrics_payload(engine)

    def test_report_and_metrics_payload_use_health_module_directly(self) -> None:
        from openclaw_watchdog import metrics_runtime
        from openclaw_watchdog import report_payload_runtime

        with tempfile.TemporaryDirectory() as temp_dir:
            template_engine = FakeEngine(temp_dir)
            status_payload = template_engine.status_payload()

            class WrapperlessEngine:
                def __init__(self) -> None:
                    self.config = template_engine.config

                def now_iso(self) -> str:
                    return template_engine.now_iso()

            engine = WrapperlessEngine()

            incident_context = {
                'recent_incidents': [],
                'current_incident_id': '',
                'current_incident_state': '',
                'current_incident_owner': '',
                'current_incident_acknowledged': False,
                'current_incident_notes_count': 0,
                'operator_attention_items': [],
                'operator_attention_needed': False,
                'operator_attention_count': 0,
            }

            with patch('openclaw_watchdog.report_payload_runtime.health_ops.status_payload', return_value=status_payload) as status_mock:
                with patch('openclaw_watchdog.report_payload_runtime.incident_ops.list_incident_snapshots', return_value=[]):
                    with patch('openclaw_watchdog.report_payload_runtime.incident_context_ops.build_report_incident_context', return_value=incident_context):
                        with patch('openclaw_watchdog.report_payload_runtime.incident_ops.current_incident_payload', return_value={}):
                            report = report_payload_runtime.report_payload(engine)
                            metrics = metrics_runtime.metrics_payload(engine)

        self.assertEqual(report['status'], 'healthy')
        self.assertEqual(metrics['status'], 'healthy')
        self.assertEqual(status_mock.call_count, 2)

    def test_reporting_facade_delegates_to_runtime_modules(self) -> None:
        from openclaw_watchdog import reporting

        engine = object()
        report_mock = Mock(return_value={'status': 'healthy'})
        message_mock = Mock(return_value='ok')
        metrics_mock = Mock(return_value={'status': 'healthy'})
        prometheus_mock = Mock(return_value='metric 1\n')

        with patch.object(reporting, 'report_payload_runtime', SimpleNamespace(report_payload=report_mock, message_report_text=message_mock), create=True):
            report = reporting.report_payload(engine, incident_limit=7)
            text = reporting.message_report_text({'status': 'healthy'})
        with patch.object(reporting, 'metrics_runtime', SimpleNamespace(metrics_payload=metrics_mock, prometheus_metrics_text=prometheus_mock), create=True):
            metrics = reporting.metrics_payload(engine)
            prom = reporting.prometheus_metrics_text({'status': 'healthy'})

        self.assertEqual(report, {'status': 'healthy'})
        self.assertEqual(text, 'ok')
        self.assertEqual(metrics, {'status': 'healthy'})
        self.assertEqual(prom, 'metric 1\n')
        report_mock.assert_called_once_with(engine, incident_limit=7)
        message_mock.assert_called_once_with({'status': 'healthy'})
        metrics_mock.assert_called_once_with(engine)
        prometheus_mock.assert_called_once_with({'status': 'healthy'})

    def test_reporting_contract_document_lists_stable_keys(self) -> None:
        contract_doc = (Path(__file__).resolve().parents[1] / 'docs' / 'reporting-contract.md').read_text(encoding='utf-8')

        for key in sorted(STABLE_REPORT_KEYS):
            self.assertIn(f'- `{key}`', contract_doc)
        for key in sorted(STABLE_METRICS_KEYS):
            self.assertIn(f'- `{key}`', contract_doc)

    def test_report_contract_keys_are_present(self) -> None:
        report = {
            'status': 'degraded',
            'health_level': 'warning',
            'current_mode': 'degraded',
            'conversation_status': 'minimal',
            'conversation_ready': False,
            'minimal_usable_ready': True,
            'last_recovery_strategy': 'litellm',
            'last_recovery_path': 'restart -> rollback -> survival -> doctor',
            'last_recovery_action_count': 4,
            'last_recovery_restored_conversation': False,
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
            'rollback_candidate_used': 'none',
            'config_drift_detected': False,
            'current_incident_id': 'incident-123',
            'operator_attention_needed': True,
            'operator_attention_items': ['assign owner'],
            'recent_incidents': [],
        }
        report['message_text'] = message_report_text(report)

        self.assertTrue(STABLE_REPORT_KEYS.issubset(report.keys()))
        self.assertNotIn('recent_incident_summaries', report)

    def test_metrics_contract_keys_are_present(self) -> None:
        metrics = {
            'status': 'healthy',
            'health_level': 'healthy',
            'service_active': True,
            'conversation_ready': True,
            'minimal_usable_ready': True,
            'survival_mode_active': False,
            'survival_mode_exit_ready': True,
            'last_recovery_action_count': 2,
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
            'recent_healthy_total': 3,
            'recent_degraded_total': 0,
            'recent_recovered_total': 1,
            'recent_failed_total': 0,
        }

        self.assertTrue(STABLE_METRICS_KEYS.issubset(metrics.keys()))
        self.assertNotIn('current_incident_events_count', metrics)
        self.assertNotIn('current_incident_latest_event_type', metrics)


    def test_report_payload_reads_extracted_run_state_fields(self) -> None:
        from openclaw_watchdog import run_state_service

        with tempfile.TemporaryDirectory() as temp_dir:
            run_state_file = Path(temp_dir) / 'run-state.json'
            guard_manifest_file = Path(temp_dir) / 'guard.json'
            run_state_service.write_run_state(
                run_state_file,
                {
                    'rescue_attempt_order': ['codex', 'claude-code', 'litellm'],
                    'rescue_rejected_executors': ['codex:unavailable', 'claude-code:no-plan'],
                    'rescue_learning_summary': 'recorded:case-1.json / pending-review',
                    'rescue_mutation_scope': ['restart_service'],
                },
                stable_required_runs=2,
                guard_manifest_file=guard_manifest_file,
            )

            class ServiceBackedEngine(FakeEngine):
                def status_payload(self_nonlocal) -> dict[str, object]:
                    payload = super().status_payload()
                    payload['run_state'] = run_state_service.read_run_state(
                        run_state_file,
                        stable_required_runs=2,
                        guard_manifest_file=guard_manifest_file,
                    )
                    return payload

            report = self._report_payload(ServiceBackedEngine(temp_dir))

        self.assertEqual(report['rescue_attempt_order'], ['codex', 'claude-code', 'litellm'])
        self.assertEqual(report['rescue_rejected_executors'], ['codex:unavailable', 'claude-code:no-plan'])
        self.assertEqual(report['rescue_learning_summary'], 'recorded:case-1.json / pending-review')
        self.assertEqual(report['rescue_mutation_scope'], ['restart_service'])

    def test_metrics_and_report_share_same_rescue_chain_fields(self) -> None:
        from openclaw_watchdog.operator_snapshot import OPERATOR_SNAPSHOT_KEYS

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = FakeEngine(temp_dir)
            report = self._report_payload(engine)
            metrics = self._metrics_payload(engine)

        shared_keys = {
            'last_recovery_strategy',
            'last_recovery_path',
            'rescue_attempt_order',
            'rescue_rejected_executors',
            'rescue_learning_summary',
            'rescue_mutation_scope',
        }
        self.assertTrue(shared_keys.issubset(OPERATOR_SNAPSHOT_KEYS))
        for key in shared_keys:
            self.assertEqual(report[key], metrics[key])

    def test_docs_index_references_rescue_lifecycle_guide(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        guide = repo_root / 'docs' / 'rescue-lifecycle.md'

        self.assertTrue(guide.exists())
        self.assertIn('rescue-lifecycle', (repo_root / 'README.md').read_text(encoding='utf-8'))
        self.assertIn('rescue-lifecycle.md', (repo_root / 'docs' / 'README.md').read_text(encoding='utf-8'))
        self.assertIn('rescue-lifecycle', (repo_root / 'docs' / 'internal-architecture.md').read_text(encoding='utf-8'))
        self.assertIn('rescue-lifecycle', (repo_root / 'docs' / 'first-deployment.md').read_text(encoding='utf-8'))
        self.assertIn('rescue-lifecycle', (repo_root / 'docs' / 'live-acceptance-checklist.md').read_text(encoding='utf-8'))

    def test_report_payload_enforces_contract_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self._report_payload(FakeEngine(temp_dir))

        self.assertTrue(STABLE_REPORT_KEYS.issubset(report.keys()))
        self.assertNotIn('recent_incident_summaries', report)

    def test_metrics_payload_enforces_contract_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics = self._metrics_payload(FakeEngine(temp_dir))

        self.assertTrue(STABLE_METRICS_KEYS.issubset(metrics.keys()))
        self.assertNotIn('current_incident_events_count', metrics)
        self.assertNotIn('current_incident_latest_event_type', metrics)

    def test_message_report_text_surfaces_recovery_and_attention(self) -> None:
        report = {
            'status': 'degraded',
            'health_level': 'warning',
            'conversation_status': 'minimal',
            'conversation_ready': False,
            'minimal_usable_ready': True,
            'last_recovery_strategy': 'litellm',
            'last_recovery_path': 'restart -> rollback -> survival -> doctor',
            'survival_mode_active': False,
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
            'rollback_candidate_used': 'none',
            'operator_attention_needed': True,
            'operator_attention_items': ['assign owner', 'acknowledge incident'],
            'current_incident_id': 'incident-123',
            'recent_incidents': [{'incident_id': 'incident-123', 'state': 'open', 'summary': 'needs triage'}],
        }

        text = message_report_text(report)

        self.assertIn('degraded', text)
        self.assertIn('litellm', text)
        self.assertIn('pending-review', text)
        self.assertIn('chain=codex -> claude-code -> litellm', text)
        self.assertIn('rejected=codex:unavailable,claude-code:no-plan', text)
        self.assertIn('mutate=restart_service,update_openclaw_config', text)
        self.assertIn('learning=recorded:case-1.json / pending-review', text)
        self.assertIn('assign owner', text)
        self.assertIn('incident-123', text)

    def test_prometheus_metrics_text_exports_key_gauges(self) -> None:
        metrics = {
            'status': 'healthy',
            'health_level': 'healthy',
            'service_active': True,
            'conversation_ready': True,
            'minimal_usable_ready': True,
            'survival_mode_active': False,
            'survival_mode_exit_ready': True,
            'last_recovery_action_count': 2,
            'config_drift_detected': False,
            'current_incident_open': False,
            'operator_attention_needed': False,
            'operator_attention_count': 0,
            'current_incident_acknowledged': False,
            'current_incident_has_notes': False,
            'current_incident_has_owner': False,
            'last_success_timestamp': 1700000000,
            'last_failure_timestamp': 0,
            'last_recovery_timestamp': 1700000001,
            'recent_healthy_count': 3,
            'recent_degraded_count': 0,
            'recent_recovered_count': 1,
            'recent_failed_count': 0,
            'current_incident_age_seconds': 0,
        }

        text = prometheus_metrics_text(metrics)

        self.assertIn('openclaw_watchdog_info', text)
        self.assertIn('openclaw_watchdog_service_active 1', text)
        self.assertIn('openclaw_watchdog_conversation_ready 1', text)
        self.assertIn('openclaw_watchdog_current_incident_acknowledged 0', text)
        self.assertNotIn('openclaw_watchdog_current_incident_events_count', text)


if __name__ == '__main__':
    unittest.main()
