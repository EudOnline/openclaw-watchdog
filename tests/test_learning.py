from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class LearningStoreTests(unittest.TestCase):
    def test_record_case_writes_json_case_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from openclaw_watchdog.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            written = store.record_case({'case_id': 'case-1', 'failure_signature': 'config-invalid', 'status': 'recovered'})

            self.assertTrue(written.exists())
            self.assertEqual(written.parent.name, 'cases')

    def test_recorded_case_persists_normalized_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from openclaw_watchdog.learning import LearningStore

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
            from openclaw_watchdog.learning import LearningStore

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
            from openclaw_watchdog.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            store.record_case({'case_id': 'case-1', 'failure_signature': 'config-invalid', 'status': 'recovered'})
            store.record_case({'case_id': 'case-2', 'failure_signature': 'gateway-down', 'status': 'failed'})

            cases = store.similar_cases({'failure_signature': 'config-invalid'})

            self.assertEqual([case['case_id'] for case in cases], ['case-1'])

    def test_record_case_classifies_phase_aware_failure_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from openclaw_watchdog.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            deterministic = store.record_case(
                {
                    'case_id': 'case-deterministic-failed',
                    'failure_signature': 'process-down',
                    'status': 'failed',
                    'learning_phase': 'deterministic',
                }
            )
            rescue_failed = store.record_case(
                {
                    'case_id': 'case-rescue-failed',
                    'failure_signature': 'process-down',
                    'status': 'failed',
                    'learning_phase': 'rescue',
                }
            )
            rolled_back = store.record_case(
                {
                    'case_id': 'case-rescue-rollback',
                    'failure_signature': 'config-invalid',
                    'status': 'failed',
                    'learning_phase': 'rescue',
                    'rollback_performed': True,
                }
            )
            deterministic_payload = deterministic.read_text(encoding='utf-8')
            rescue_failed_payload = rescue_failed.read_text(encoding='utf-8')
            rolled_back_payload = rolled_back.read_text(encoding='utf-8')

        self.assertIn('"outcome_kind": "deterministic-failure"', deterministic_payload)
        self.assertIn('"outcome_kind": "rescue-failure"', rescue_failed_payload)
        self.assertIn('"outcome_kind": "rolled-back-rescue"', rolled_back_payload)
        self.assertIn('"evidence_quality": "negative"', rolled_back_payload)


class RulePromotionTests(unittest.TestCase):
    def test_deterministic_recovery_count_alone_does_not_auto_promote_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from openclaw_watchdog.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            candidate = {
                'rule_id': 'restart-service-auto',
                'match': {'normalized_failure_signature': 'process-down'},
                'diagnosis': 'restart service',
                'actions': [{'kind': 'restart_service', 'params': {}}],
                'validations': ['minimal_usable_ready'],
            }
            for idx in range(3):
                store.record_case(
                    {
                        'case_id': f'case-deterministic-{idx}',
                        'failure_signature': 'process-down',
                        'status': 'recovered',
                        'learning_phase': 'deterministic',
                        'candidate_rule': candidate,
                        'risk_level': 'low',
                    }
                )

            result = store.promote_candidates()

            self.assertEqual(result.auto_promoted, 0)
            self.assertFalse((store.rules_dir / 'restart-service-auto.json').exists())

    def test_low_risk_candidate_auto_promotes_after_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from openclaw_watchdog.learning import LearningStore

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
            self.assertIn('"evidence_score"', promoted)
            self.assertIn('"strong_evidence_count": 3', promoted)
            self.assertIn('"confidence"', promoted)

    def test_auto_promotion_counts_preloaded_simple_success_cases_after_load_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from openclaw_watchdog.learning import LearningStore

            store = LearningStore(root=Path(temp_dir))
            candidate_rule = {
                'rule_id': 'process-down-litellm',
                'match': {'failure_signature': 'process-down'},
                'diagnosis': 'litellm restart rescue',
                'actions': [{'kind': 'restart_service', 'params': {}}],
                'validations': ['minimal_usable_ready'],
            }
            for idx in range(2):
                payload = {
                    'case_id': f'case-auto-{idx + 1}',
                    'failure_signature': 'process-down',
                    'status': 'recovered',
                    'risk_level': 'low',
                    'candidate_rule': candidate_rule,
                }
                (store.cases_dir / f'case-auto-{idx + 1}.json').write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                    encoding='utf-8',
                )
            store.record_successful_case(
                {
                    'case_id': 'case-auto-3',
                    'failure_signature': 'process-down',
                    'status': 'recovered',
                    'risk_level': 'low',
                    'candidate_rule': candidate_rule,
                }
            )

            result = store.promote_candidates()

            self.assertEqual(result.auto_promoted, 1)
            self.assertTrue((store.rules_dir / 'process-down-litellm.json').exists())


    def test_rule_is_marked_pending_review_again_after_high_risk_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from openclaw_watchdog.learning import LearningStore

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
            from openclaw_watchdog.learning import LearningStore

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
            from openclaw_watchdog.learning import LearningStore

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
        from openclaw_watchdog.run_context import RunContext
        from types import SimpleNamespace

        engine = SimpleNamespace(
            config=SimpleNamespace(
                watchdog_rescue_knowledge_root=Path(temp_dir) / 'knowledge',
            ),
            ctx=RunContext.initial(stable_required_runs=2),
        )
        engine.ctx.incident_id = 'incident-42'
        return engine

    def test_record_learning_from_recovery_persists_normalized_signature_and_candidate_rule(self) -> None:
        from openclaw_watchdog.learning import LearningStore
        from openclaw_watchdog import rescue_learning_service
        from openclaw_watchdog.rescue_dispatch import DispatchResult
        from openclaw_watchdog.rescue_models import RescueAction, RescueContext, RescuePlan

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

            result = rescue_learning_service.record_learning_from_recovery(
                engine,
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
        self.assertEqual(cases[0]['learning_phase'], 'rescue')
        self.assertEqual(cases[0]['outcome_kind'], 'successful-rescue')
        self.assertEqual(cases[0]['evidence_quality'], 'strong')
        self.assertEqual(cases[0]['normalized_failure_signature'], 'config-invalid')
        self.assertEqual(cases[0]['candidate_rule']['match']['normalized_failure_signature'], 'config-invalid')
        self.assertTrue(cases[0]['candidate_rule']['match']['config_invalid'])

    def test_record_learning_from_failure_marks_rolled_back_rescue_negative_evidence(self) -> None:
        from openclaw_watchdog.learning import LearningStore
        from openclaw_watchdog import rescue_learning_service
        from openclaw_watchdog.rescue_dispatch import DispatchResult
        from openclaw_watchdog.rescue_models import RescueAction, RescueContext, RescuePlan, RescueResult

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self._build_engine(temp_dir)
            context = RescueContext(
                incident_id='incident-42',
                health_level='failed',
                conversation_status='down',
                available_executors=('rule-agent',),
                probe={'config_invalid': True},
                metadata={'config_invalid': True},
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
            plan_result = RescueResult(status='rolled-back', executor='rule-agent', plan_id='plan-rule-agent', rollback_performed=True)

            result = rescue_learning_service.record_learning_from_failure(
                engine,
                strategy='rule-agent',
                recovery_kind='rescue',
                probe={'config_invalid': True},
                context=context,
                dispatch_result=dispatch_result,
                plan_result=plan_result,
            )
            store = LearningStore(root=engine.config.watchdog_rescue_knowledge_root)
            cases = store.load_cases()

        self.assertEqual(result['candidate_rule_status'], 'negative-evidence-recorded')
        self.assertEqual(cases[0]['outcome_kind'], 'rolled-back-rescue')
        self.assertEqual(cases[0]['evidence_quality'], 'negative')


if __name__ == '__main__':
    unittest.main()
