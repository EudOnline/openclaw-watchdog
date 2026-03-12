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

    def test_recorded_case_persists_normalized_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            case_path = store.record_case(
                {
                    'case_id': 'case-normalized',
                    'failure_signature': 'provider-auth-exploded',
                    'config_invalid': True,
                    'status': 'failed',
                }
            )

            payload = case_path.read_text(encoding='utf-8')
            self.assertIn('"normalized_failure_signature": "config-invalid"', payload)

    def test_similar_cases_match_normalized_signature_not_raw_summary_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            store.record_case(
                {
                    'case_id': 'case-1',
                    'failure_signature': 'provider-auth-exploded',
                    'config_invalid': True,
                    'status': 'recovered',
                }
            )
            store.record_case(
                {
                    'case_id': 'case-2',
                    'failure_signature': 'gateway-tls-broken',
                    'config_invalid': True,
                    'status': 'recovered',
                }
            )
            store.record_case(
                {
                    'case_id': 'case-3',
                    'failure_signature': 'process-down',
                    'process_layer_healthy': False,
                    'status': 'failed',
                }
            )

            cases = store.similar_cases({'failure_signature': 'yaml-parse-error', 'config_invalid': True})

            self.assertEqual([case['case_id'] for case in cases], ['case-1', 'case-2'])

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


    def test_rule_is_marked_pending_review_again_after_high_risk_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            promoted_rule = {
                'rule_id': 'config-invalid-auto',
                'match': {'normalized_failure_signature': 'config-invalid'},
                'diagnosis': 'config invalid',
                'actions': [{'kind': 'restore_last_good', 'params': {}}],
                'validations': ['minimal_usable_ready'],
                'negative_evidence_count': 0,
                'suppressed': False,
            }
            (store.rules_dir / 'config-invalid-auto.json').write_text(
                __import__('json').dumps(promoted_rule, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                encoding='utf-8',
            )
            store.record_case(
                {
                    'case_id': 'case-high-regression',
                    'failure_signature': 'yaml-parse-error',
                    'normalized_failure_signature': 'config-invalid',
                    'status': 'failed',
                    'risk_level': 'high',
                    'candidate_rule': {'rule_id': 'config-invalid-auto'},
                }
            )

            result = store.promote_candidates()

            self.assertEqual(result.pending_review, 1)
            review_payload = (store.reviews_dir / 'config-invalid-auto.json').read_text(encoding='utf-8')
            self.assertIn('"status": "pending-review"', review_payload)
            updated_rule = (store.rules_dir / 'config-invalid-auto.json').read_text(encoding='utf-8')
            self.assertIn('"negative_evidence_count": 1', updated_rule)

    def test_rule_with_repeated_failed_outcomes_is_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            promoted_rule = {
                'rule_id': 'process-down-auto',
                'match': {'normalized_failure_signature': 'process-down'},
                'diagnosis': 'restart service',
                'actions': [{'kind': 'restart_service', 'params': {}}],
                'validations': ['minimal_usable_ready'],
                'negative_evidence_count': 0,
                'suppressed': False,
            }
            (store.rules_dir / 'process-down-auto.json').write_text(
                __import__('json').dumps(promoted_rule, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                encoding='utf-8',
            )
            for idx in range(2):
                store.record_case(
                    {
                        'case_id': f'case-failed-{idx}',
                        'failure_signature': 'agent-timeout',
                        'normalized_failure_signature': 'process-down',
                        'status': 'failed',
                        'risk_level': 'low',
                        'candidate_rule': {'rule_id': 'process-down-auto'},
                    }
                )

            store.promote_candidates()

            updated_rule = (store.rules_dir / 'process-down-auto.json').read_text(encoding='utf-8')
            self.assertIn('"negative_evidence_count": 2', updated_rule)
            self.assertIn('"suppressed": true', updated_rule)

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



class EngineRecoveryLearningSeamsTest(unittest.TestCase):
    def _build_engine(self, temp_dir: str):
        from watchdog_v2.engine import WatchdogEngine
        from watchdog_v2.run_context import RunContext
        from types import SimpleNamespace

        engine = WatchdogEngine.__new__(WatchdogEngine)
        object.__setattr__(
            engine,
            'config',
            SimpleNamespace(
                watchdog_rescue_knowledge_root=Path(temp_dir) / 'knowledge',
            ),
        )
        object.__setattr__(engine, 'ctx', RunContext.initial(stable_required_runs=2))
        engine.ctx.incident_id = 'incident-42'
        return engine

    def test_record_learning_from_recovery_persists_normalized_signature_and_candidate_rule(self) -> None:
        from watchdog_v2.learning import LearningStore
        from watchdog_v2.rescue_dispatch import DispatchResult
        from watchdog_v2.rescue_models import RescueAction, RescueContext, RescuePlan

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self._build_engine(temp_dir)
            context = RescueContext(
                incident_id='incident-42',
                health_level='failed',
                conversation_status='down',
                available_executors=('rule-agent',),
                editable_paths=(),
                editable_keys=(),
                probe={'config_invalid': True},
                metadata={
                    'failure_signature': 'config-invalid',
                    'normalized_failure_signature': 'config-invalid',
                    'config_invalid': True,
                },
            )
            dispatch_result = DispatchResult(
                executor_order=['rule-agent'],
                final_executor='rule-agent',
                plan=RescuePlan(
                    plan_id='plan-rule-agent',
                    diagnosis='restore last good config',
                    actions=[RescueAction(kind='restore_last_good', params={})],
                    validations=['minimal_usable_ready'],
                ),
            )

            result = engine.record_learning_from_recovery(
                strategy='rule-agent',
                recovery_kind='rescue',
                probe={'config_invalid': True},
                context=context,
                dispatch_result=dispatch_result,
                plan_result=None,
            )
            store = LearningStore(root=engine.config.watchdog_rescue_knowledge_root)
            cases = store.load_cases()

        self.assertEqual(result['candidate_rule_status'], 'candidate-recorded')
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['normalized_failure_signature'], 'config-invalid')
        self.assertEqual(cases[0]['candidate_rule']['match']['normalized_failure_signature'], 'config-invalid')
        self.assertTrue(cases[0]['candidate_rule']['match']['config_invalid'])


if __name__ == '__main__':
    unittest.main()
