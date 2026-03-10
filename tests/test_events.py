import unittest

from watchdog_v2.events import build_event_payload, event_human_summary, event_severity


class EventsTest(unittest.TestCase):
    def test_event_severity_and_human_summary_follow_status(self) -> None:
        self.assertEqual(event_severity('failed', 'failed', 'doctor repair exhausted'), 'critical')
        self.assertEqual(event_severity('degraded', 'degraded', 'conversation minimal only'), 'warning')
        self.assertEqual(event_severity('recovered', 'healthy', 'restart restored service'), 'success')
        self.assertEqual(event_severity('healthy', 'healthy', 'maintenance window active'), 'info')
        self.assertEqual(event_human_summary('failed', 'failed', 'doctor repair exhausted'), 'watchdog 判定修复失败：doctor repair exhausted')
        self.assertEqual(event_human_summary('healthy', 'healthy', 'listener ready'), 'watchdog 健康检查正常：listener ready')

    def test_build_event_payload_includes_run_state_and_handoff_context(self) -> None:
        payload = build_event_payload(
            run_ts='2026-03-10 12:00:00 UTC',
            status='failed',
            summary='deterministic remediation failed',
            run_state={
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
            },
            rollback_occurred=True,
            rollback_summary_file='state/last-rollback-summary.txt',
            rollback_summary_archive_file='state/archive/rollback-1.txt',
            rollback_broken_config_file='state/archive/broken.env',
            pre_repair_backup_result='created',
            consecutive_failures=3,
            incident_id='incident-42',
            incident_dir='state/incidents/incident-42',
            codex_context={
                'prompt_file': 'state/incidents/incident-42/codex-prompt.md',
                'handoff_file': 'state/incidents/incident-42/run-codex.sh',
                'runner_file': 'state/incidents/incident-42/codex-runner.sh',
                'run_log_file': 'state/incidents/incident-42/codex-run.log',
                'run_pid': '111',
                'trigger_result': 'triggered',
                'autorun_ready': True,
            },
            opencode_fallback_context={
                'handoff_file': 'state/incidents/incident-42/run-opencode-fallback.sh',
                'runner_file': 'state/incidents/incident-42/opencode-fallback-runner.sh',
                'run_log_file': 'state/incidents/incident-42/opencode-fallback.log',
                'run_pid': '222',
                'trigger_result': 'not-run',
            },
        )

        self.assertEqual(payload['severity'], 'critical')
        self.assertEqual(payload['human_summary'], 'watchdog 判定修复失败：deterministic remediation failed')
        self.assertEqual(payload['rollback_candidate_used'], 'gen-2')
        self.assertTrue(payload['config_drift_detected'])
        self.assertEqual(payload['codex']['trigger_result'], 'triggered')
        self.assertEqual(payload['opencode_fallback']['run_pid'], '222')
        self.assertEqual(payload['incident_id'], 'incident-42')


if __name__ == '__main__':
    unittest.main()
