import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace

from watchdog_v2.reporting import message_report_text, metrics_payload, prometheus_metrics_text, report_payload


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
    'config_drift_detected',
    'current_incident_open',
    'current_incident_acknowledged',
    'current_incident_notes_count',
    'current_incident_owner_assigned',
    'cooldown_remaining_seconds',
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
            'cooldown_remaining_seconds': 0,
            'current_incident_id': '',
            'current_incident_state': '',
            'recent_event_stats': {'counts': {'healthy': 3, 'degraded': 0, 'recovered': 1, 'failed': 0}},
            'last_event': {'summary': 'healthy', 'human_summary': 'healthy'},
            'incident_queue_summary': {'open_total': 0, 'attention_total': 0, 'handled_total': 0},
            'recent_incidents': [],
            'last_recovery_strategy': 'restart',
            'last_recovery_path': 'restart -> probe',
            'last_recovery_action_count': 1,
            'last_recovery_restored_conversation': True,
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
                'last_recovery_strategy': 'restart',
                'last_recovery_path': 'restart -> probe',
                'last_recovery_action_count': 1,
                'last_recovery_restored_conversation': True,
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
            'last_recovery_strategy': 'restart',
            'last_recovery_path': 'restart -> probe',
            'last_recovery_action_count': 1,
            'last_recovery_restored_conversation': False,
            'rollback_candidate_used': 'none',
            'config_drift_detected': False,
            'current_incident_id': 'incident-123',
            'operator_attention_needed': True,
            'operator_attention_items': ['assign owner'],
            'recent_incidents': [],
        }
        report['message_text'] = message_report_text(report)

        self.assertTrue(STABLE_REPORT_KEYS.issubset(report.keys()))

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
            'config_drift_detected': False,
            'current_incident_open': False,
            'current_incident_acknowledged': False,
            'current_incident_notes_count': 0,
            'current_incident_owner_assigned': False,
            'cooldown_remaining_seconds': 0,
            'recent_healthy_total': 3,
            'recent_degraded_total': 0,
            'recent_recovered_total': 1,
            'recent_failed_total': 0,
        }

        self.assertTrue(STABLE_METRICS_KEYS.issubset(metrics.keys()))

    def test_report_payload_enforces_contract_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = report_payload(FakeEngine(temp_dir))

        self.assertTrue(STABLE_REPORT_KEYS.issubset(report.keys()))

    def test_metrics_payload_enforces_contract_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics = metrics_payload(FakeEngine(temp_dir))

        self.assertTrue(STABLE_METRICS_KEYS.issubset(metrics.keys()))

    def test_message_report_text_surfaces_recovery_and_attention(self) -> None:
        report = {
            'status': 'degraded',
            'health_level': 'warning',
            'conversation_status': 'minimal',
            'conversation_ready': False,
            'minimal_usable_ready': True,
            'last_recovery_strategy': 'restart',
            'last_recovery_path': 'restart -> probe',
            'survival_mode_active': False,
            'rollback_candidate_used': 'none',
            'operator_attention_needed': True,
            'operator_attention_items': ['assign owner', 'acknowledge incident'],
            'current_incident_id': 'incident-123',
            'recent_incidents': [{'incident_id': 'incident-123', 'state': 'open', 'summary': 'needs triage'}],
        }

        text = message_report_text(report)

        self.assertIn('degraded', text)
        self.assertIn('restart', text)
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
            'cooldown_remaining_seconds': 0,
        }

        text = prometheus_metrics_text(metrics)

        self.assertIn('openclaw_watchdog_info', text)
        self.assertIn('openclaw_watchdog_service_active 1', text)
        self.assertIn('openclaw_watchdog_conversation_ready 1', text)
        self.assertIn('openclaw_watchdog_current_incident_acknowledged 0', text)


if __name__ == '__main__':
    unittest.main()
