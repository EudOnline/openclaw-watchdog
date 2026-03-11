from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class LearningStoreTests(unittest.TestCase):
    def test_record_case_writes_json_case_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            written = store.record_case({'case_id': 'case-1', 'failure_signature': 'config-invalid', 'status': 'recovered'})

            self.assertTrue(written.exists())
            self.assertEqual(written.parent.name, 'cases')

    def test_similar_cases_match_failure_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            store.record_case({'case_id': 'case-1', 'failure_signature': 'config-invalid', 'status': 'recovered'})
            store.record_case({'case_id': 'case-2', 'failure_signature': 'gateway-down', 'status': 'failed'})

            cases = store.similar_cases({'failure_signature': 'config-invalid'})

            self.assertEqual([case['case_id'] for case in cases], ['case-1'])


class RulePromotionTests(unittest.TestCase):
    def test_low_risk_candidate_auto_promotes_after_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            low_risk_case = {
                'case_id': 'case-low',
                'failure_signature': 'config-invalid',
                'status': 'recovered',
                'risk_level': 'low',
                'candidate_rule': {
                    'rule_id': 'config-invalid-auto',
                    'match': {'failure_signature': 'config-invalid'},
                    'diagnosis': 'config invalid',
                    'actions': [{'kind': 'restore_last_good', 'params': {}}],
                    'validations': ['minimal_usable_ready'],
                },
            }
            for idx in range(3):
                payload = dict(low_risk_case)
                payload['case_id'] = f'case-low-{idx}'
                store.record_successful_case(payload)

            result = store.promote_candidates()

            self.assertEqual(result.auto_promoted, 1)
            self.assertTrue((store.rules_dir / 'config-invalid-auto.json').exists())
            promoted = (store.rules_dir / 'config-invalid-auto.json').read_text(encoding='utf-8')
            self.assertIn('"evidence_count": 3', promoted)
            self.assertIn('"confidence"', promoted)


    def test_high_risk_candidate_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            store.record_successful_case(
                {
                    'case_id': 'case-high-1',
                    'failure_signature': 'provider-switch',
                    'status': 'recovered',
                    'risk_level': 'high',
                    'candidate_rule': {
                        'rule_id': 'provider-switch-review',
                        'match': {'failure_signature': 'provider-switch'},
                        'diagnosis': 'provider switch',
                        'actions': [{'kind': 'update_openclaw_config', 'params': {'file': 'config.json', 'path': 'provider', 'value': 'backup'}}],
                        'validations': ['minimal_usable_ready'],
                    },
                }
            )

            result = store.promote_candidates()

            self.assertEqual(result.pending_review, 1)
            self.assertTrue((store.reviews_dir / 'provider-switch-review.json').exists())
            review = (store.reviews_dir / 'provider-switch-review.json').read_text(encoding='utf-8')
            self.assertIn('"evidence_count": 1', review)
            self.assertIn('"mutation_scope"', review)



if __name__ == '__main__':
    unittest.main()
