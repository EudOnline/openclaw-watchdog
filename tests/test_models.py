import unittest

from watchdog_v2.models import BootstrapSummary, IncidentSummary, ProbeSnapshot, RunStateSnapshot


class ModelsTest(unittest.TestCase):
    def test_probe_snapshot_defaults_and_round_trip(self) -> None:
        snapshot = ProbeSnapshot.from_dict({'service_active': True, 'conversation_status': 'ready'})

        self.assertTrue(snapshot.service_active)
        self.assertEqual(snapshot.conversation_status, 'ready')
        self.assertFalse(snapshot.conversation_ready)
        self.assertEqual(ProbeSnapshot.from_dict(snapshot.to_dict()), snapshot)

    def test_run_state_snapshot_defaults_and_round_trip(self) -> None:
        snapshot = RunStateSnapshot.from_dict(
            {
                'health_level': 'degraded',
                'conversation_ready': True,
                'rollback_candidate_used': 'gen-2',
                'drift_scope': ['config', 'extensions'],
            }
        )

        self.assertEqual(snapshot.health_level, 'degraded')
        self.assertTrue(snapshot.conversation_ready)
        self.assertEqual(snapshot.rollback_candidate_used, 'gen-2')
        self.assertEqual(snapshot.drift_scope, ['config', 'extensions'])
        self.assertEqual(RunStateSnapshot.from_dict(snapshot.to_dict()), snapshot)

    def test_incident_summary_defaults_and_round_trip(self) -> None:
        summary = IncidentSummary.from_dict(
            {
                'incident_id': 'incident-42',
                'state': 'open',
                'owner': 'alice',
                'acknowledged': True,
                'notes_count': 2,
                'summary': 'gateway degraded',
            }
        )

        self.assertEqual(summary.incident_id, 'incident-42')
        self.assertEqual(summary.owner, 'alice')
        self.assertTrue(summary.acknowledged)
        self.assertEqual(summary.notes_count, 2)
        self.assertEqual(IncidentSummary.from_dict(summary.to_dict()), summary)

    def test_bootstrap_summary_builds_serializable_default_payload(self) -> None:
        summary = BootstrapSummary.initial(config_path='state/openclaw.json', dry_run=True)
        payload = summary.to_dict()

        self.assertEqual(payload['state'], 'unknown')
        self.assertTrue(payload['dry_run'])
        self.assertEqual(payload['config']['path'], 'state/openclaw.json')
        self.assertIn('ensure-opencode', payload['flow'])
        self.assertEqual(BootstrapSummary.from_dict(payload).to_dict(), payload)


if __name__ == '__main__':
    unittest.main()
