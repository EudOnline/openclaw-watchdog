import unittest

from watchdog_v2.incident_context import build_incident_index_entry, build_report_incident_context
from watchdog_v2.models import IncidentSummary


class IncidentContextTest(unittest.TestCase):
    def test_build_incident_index_entry_merges_state_workflow_and_latest_note(self) -> None:
        entry = build_incident_index_entry(
            run_ts='2026-03-10 12:00:00 UTC',
            incident_id='incident-42',
            incident_dir='state/incidents/incident-42',
            summary='gateway degraded',
            state_payload={
                'state': 'open',
                'created_at': '2026-03-10T11:55:00+00:00',
                'resolved_at': '',
                'resolution_summary': '',
            },
            workflow_payload={
                'owner': 'alice',
                'acknowledged': True,
                'acknowledged_by': 'alice',
                'acknowledged_at': '2026-03-10T11:56:00+00:00',
                'notes': [
                    {'time': '2026-03-10T11:57:00+00:00', 'by': 'alice', 'message': 'investigating'},
                    {'time': '2026-03-10T11:58:00+00:00', 'by': 'bob', 'message': 'rolled back config'},
                ],
            },
            run_state={
                'health_level': 'degraded',
                'conversation_status': 'minimal',
                'rescue_executor_selected': 'litellm',
                'rescue_plan_generated': True,
                'rescue_plan_source': 'litellm',
                'rescue_plan_status': 'applied',
                'rescue_tier': 'litellm',
                'candidate_rule_status': 'pending-review',
            },
            active='true',
            main_pid='123',
            listeners='123 456',
            pre_repair_backup_result='created',
            rollback_occurred=True,
            rollback_summary_archive_file='state/archive/rollback-1.txt',
            rollback_candidate_used='gen-2',
            rollback_reason='config invalid',
            last_recovery_strategy='rollback',
            last_recovery_path='restart -> rollback',
        )

        self.assertEqual(entry['incident_id'], 'incident-42')
        self.assertEqual(entry['state'], 'open')
        self.assertEqual(entry['owner'], 'alice')
        self.assertTrue(entry['acknowledged'])
        self.assertEqual(entry['notes_count'], 2)
        self.assertEqual(entry['latest_note'], 'rolled back config')
        self.assertEqual(entry['conversation_status'], 'minimal')
        self.assertEqual(entry['last_recovery_strategy'], 'rollback')
        self.assertEqual(entry['rescue_executor_selected'], 'litellm')
        self.assertEqual(entry['candidate_rule_status'], 'pending-review')
        self.assertNotIn('codex_trigger_result', entry)
        self.assertNotIn('opencode_fallback_trigger_result', entry)

    def test_build_report_incident_context_shapes_attention_from_typed_incidents(self) -> None:
        context = build_report_incident_context(
            current_incident_id='incident-42',
            current_incident_state='open',
            current_incident=IncidentSummary(
                incident_id='incident-42',
                state='open',
                health_level='failed',
                owner='',
                acknowledged=False,
                notes_count=0,
                summary='current outage',
                attention_summary='unowned,unacknowledged,no-notes',
            ),
            recent_incidents=[
                IncidentSummary(
                    incident_id='incident-41',
                    state='resolved',
                    health_level='failed',
                    owner='alice',
                    acknowledged=True,
                    notes_count=2,
                    summary='previous outage',
                    latest_note='resolved',
                    attention_summary='none',
                ),
                IncidentSummary(
                    incident_id='incident-42',
                    state='open',
                    health_level='failed',
                    owner='',
                    acknowledged=False,
                    notes_count=0,
                    summary='current outage',
                    attention_summary='unowned,unacknowledged,no-notes',
                ),
            ],
            incident_limit=5,
        )

        self.assertEqual(context['current_incident_owner'], '')
        self.assertFalse(context['current_incident_acknowledged'])
        self.assertEqual(context['current_incident_notes_count'], 0)
        self.assertEqual(
            context['operator_attention_items'],
            ['current incident is unowned', 'current incident is unacknowledged', 'current incident has no operator notes'],
        )
        self.assertTrue(context['operator_attention_needed'])
        self.assertEqual(len(context['recent_incidents']), 2)
        self.assertEqual(context['recent_incidents'][1]['incident_id'], 'incident-42')
        self.assertEqual(context['recent_incidents'][1]['attention_summary'], 'unowned,unacknowledged,no-notes')
        self.assertNotIn('recent_incident_summaries', context)


if __name__ == '__main__':
    unittest.main()
