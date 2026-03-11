import unittest

from watchdog_v2.presenters.bootstrap import render_bootstrap
from watchdog_v2.presenters.incidents import render_incident_queue
from watchdog_v2.presenters.report import render_report
from watchdog_v2.presenters.status import render_status_summary


class CliPresentersTest(unittest.TestCase):
    def test_render_status_summary_surfaces_survival_and_last_event(self) -> None:
        text = render_status_summary(
            {
                'last_status': 'healthy',
                'conversation_status': 'ready',
                'health_level': 'healthy',
                'current_mode': 'normal',
                'last_recovery_strategy': 'litellm',
                'rescue_executor_selected': 'litellm',
                'candidate_rule_status': 'pending-review',
                'rescue_attempt_order': ['codex', 'claude-code', 'litellm'],
                'rescue_rejected_executors': ['codex:unavailable', 'claude-code:no-plan'],
                'survival_mode_active': False,
                'service_active': True,
                'service_probe_summary': 'ok',
                'recent_event_stats': {'counts': {'healthy': 2, 'degraded': 0, 'recovered': 1, 'failed': 0}},
                'recent_incidents': [],
                'last_event': {'human_summary': 'all good'},
            }
        )

        self.assertIn('status=healthy', text)
        self.assertIn('conv=ready', text)
        self.assertIn('litellm', text)
        self.assertIn('order=codex>claude-code>litellm', text)
        self.assertIn('reject=codex:unavailable,claude-code:no-plan', text)
        self.assertIn('last=all good', text)

    def test_render_report_surfaces_attention_and_recent_incident(self) -> None:
        text = render_report(
            {
                'status': 'degraded',
                'conversation_status': 'minimal',
                'conversation_ready': False,
                'minimal_usable_ready': True,
                'health_level': 'degraded',
                'current_mode': 'degraded',
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
                'rollback_candidate_used': '',
                'rollback_reason': '',
                'config_drift_detected': False,
                'current_incident_id': 'incident-7',
                'current_incident_state': 'open',
                'current_incident_owner': '',
                'current_incident_acknowledged': False,
                'current_incident_notes_count': 0,
                'incident_queue_summary': {'open_total': 1, 'attention_total': 1, 'handled_total': 0},
                'recent_event_stats': {'counts': {'healthy': 0, 'degraded': 1, 'recovered': 0, 'failed': 1}},
                'last_event': {'human_summary': 'gateway degraded'},
                'recent_incidents': [{'incident_id': 'incident-7', 'state': 'open', 'health_level': 'failed', 'owner': '', 'acknowledged': False, 'notes_count': 0, 'summary': 'gateway degraded', 'latest_note': '', 'attention_summary': 'unowned'}],
                'operator_attention_items': ['current incident is unowned'],
                'operator_attention_needed': True,
                'operator_attention_count': 1,
                'message_text': 'message',
            }
        )

        self.assertIn('current_incident_id=incident-7', text)
        self.assertIn('rescue_executor_selected=litellm', text)
        self.assertIn('candidate_rule_status=pending-review', text)
        self.assertIn('rescue_attempt_order=codex -> claude-code -> litellm', text)
        self.assertIn('rescue_rejected_executors=codex:unavailable, claude-code:no-plan', text)
        self.assertIn('rescue_learning_summary=recorded:case-1.json / pending-review', text)
        self.assertIn('rescue_mutation_scope=restart_service, update_openclaw_config', text)
        self.assertIn('operator_attention_needed=true', text)
        self.assertIn('recent_incident_1=incident-7', text)

    def test_render_incident_queue_surfaces_attention_summary(self) -> None:
        text = render_incident_queue(
            {
                'summary': {'open_total': 1, 'attention_total': 1, 'handled_total': 0, 'owned_total': 0, 'acknowledged_total': 0, 'with_notes_total': 0},
                'incidents': [
                    {
                        'incident_id': 'incident-9',
                        'state': 'open',
                        'health_level': 'failed',
                        'owner': '',
                        'acknowledged': False,
                        'notes_count': 0,
                        'attention_summary': 'unowned',
                        'summary': 'config broken',
                        'latest_note': '',
                    }
                ],
            }
        )

        self.assertIn('open_total=1', text)
        self.assertIn('queue_1=incident-9', text)
        self.assertIn('attention=unowned', text)

    def test_render_bootstrap_surfaces_detect_only_inventory(self) -> None:
        outcome = type('BootstrapOutcomeStub', (), {
            'state': 'ready',
            'summary': 'Bootstrap detection completed',
            'payload': {
                'opencode': {'available': True, 'detected_binary': 'opencode', 'config_ready': True, 'config': {'path': 'state/opencode.json', 'configured_model': 'opencode/minimax-m2.5-free', 'changed': False, 'backup_path': ''}, 'watchdog_bin_available': True, 'desired_model': 'opencode/minimax-m2.5-free'},
                'codex': {'available': False, 'detected_binary': ''},
                'openclaw': {'available': False, 'binary': '', 'detect_returncode': 1},
                'qq_plugin': {'installed': False},
                'config': {'path': 'state/openclaw.json', 'changed': False, 'backup_path': '', 'placeholders_remaining': []},
                'feishu_runtime': {'found': False},
                'files_changed': [],
                'flow': ['detect-opencode', 'detect-openclaw'],
            },
        })()

        text = render_bootstrap(outcome)

        self.assertIn('state=ready', text)
        self.assertIn('opencode_available=true', text)
        self.assertIn('openclaw_available=false', text)
        self.assertIn('bootstrap_flow=detect-opencode -> detect-openclaw', text)
        self.assertNotIn('confirmation_required=', text)
        self.assertNotIn('opencode_install_planned=', text)


if __name__ == '__main__':
    unittest.main()
