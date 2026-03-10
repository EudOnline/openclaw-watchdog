import unittest

from watchdog_v2.reporting import message_report_text, prometheus_metrics_text


class ReportingTest(unittest.TestCase):
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
