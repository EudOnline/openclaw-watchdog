from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openclaw_watchdog.rescue_models import RescueContext


class RuleAgentTests(unittest.TestCase):
    def test_matches_invalid_config_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules_dir = root / 'rules'
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / 'invalid-config.json').write_text(
                json.dumps(
                    {
                        'rule_id': 'invalid-config',
                        'match': {'config_invalid': True},
                        'diagnosis': 'config invalid',
                        'actions': [{'kind': 'restore_last_good', 'params': {}}],
                        'validations': ['minimal_usable_ready'],
                    }
                ),
                encoding='utf-8',
            )

            from openclaw_watchdog.rescue_agents.rule_agent import RuleBasedRescueAgent
            from openclaw_watchdog.learning import LearningStore

            agent = RuleBasedRescueAgent(rule_store=LearningStore(root=root))
            plan = agent.propose_plan(
                RescueContext(incident_id='incident-1', health_level='failed', metadata={'config_invalid': True})
            )

            self.assertEqual(plan.actions[0].kind, 'restore_last_good')
            self.assertEqual(plan.plan_id, 'invalid-config')

    def test_rule_agent_prefers_cases_with_same_normalized_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules_dir = root / 'rules'
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / 'invalid-config-normalized.json').write_text(
                json.dumps(
                    {
                        'rule_id': 'invalid-config-normalized',
                        'match': {'normalized_failure_signature': 'config-invalid'},
                        'diagnosis': 'config invalid',
                        'actions': [{'kind': 'restore_last_good', 'params': {}}],
                        'validations': ['minimal_usable_ready'],
                    }
                ),
                encoding='utf-8',
            )

            from openclaw_watchdog.rescue_agents.rule_agent import RuleBasedRescueAgent
            from openclaw_watchdog.learning import LearningStore

            store = LearningStore(root=root)
            store.record_case(
                {
                    'case_id': 'case-normalized',
                    'failure_signature': 'provider-auth-exploded',
                    'config_invalid': True,
                    'status': 'recovered',
                }
            )
            store.record_case(
                {
                    'case_id': 'case-other',
                    'failure_signature': 'process-down',
                    'process_layer_healthy': False,
                    'status': 'recovered',
                }
            )
            agent = RuleBasedRescueAgent(rule_store=store)
            plan = agent.propose_plan(
                RescueContext(incident_id='incident-normalized', health_level='failed', metadata={'failure_signature': 'yaml-parse-error', 'config_invalid': True})
            )

            self.assertEqual(plan.plan_id, 'invalid-config-normalized')
            self.assertIn('case:case-normalized', plan.rationale)
            self.assertNotIn('case:case-other', plan.rationale)

    def test_uses_process_down_heuristic_when_no_promoted_rule_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from openclaw_watchdog.rescue_agents.rule_agent import RuleBasedRescueAgent
            from openclaw_watchdog.learning import LearningStore

            agent = RuleBasedRescueAgent(rule_store=LearningStore(root=Path(temp_dir)))
            plan = agent.propose_plan(
                RescueContext(
                    incident_id='incident-heuristic',
                    health_level='failed',
                    metadata={
                        'failure_signature': 'process-down',
                        'service_active': False,
                        'process_layer_healthy': False,
                    },
                )
            )

            self.assertEqual(plan.actions[0].kind, 'restart_service')
            self.assertIn('heuristic', plan.rationale)

    def test_rule_agent_skips_suppressed_rule_and_falls_back_to_static_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules_dir = root / 'rules'
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / 'suppressed-process.json').write_text(
                json.dumps(
                    {
                        'rule_id': 'suppressed-process',
                        'match': {'normalized_failure_signature': 'process-down'},
                        'diagnosis': 'restart service',
                        'actions': [{'kind': 'restart_service', 'params': {}}],
                        'validations': ['minimal_usable_ready'],
                        'suppressed': True,
                        'negative_evidence_count': 2,
                    }
                ),
                encoding='utf-8',
            )

            from openclaw_watchdog.rescue_agents.rule_agent import RuleBasedRescueAgent
            from openclaw_watchdog.learning import LearningStore

            agent = RuleBasedRescueAgent(rule_store=LearningStore(root=root))
            plan = agent.propose_plan(
                RescueContext(
                    incident_id='incident-suppressed',
                    health_level='failed',
                    metadata={
                        'failure_signature': 'watchdog-reported-timeout',
                        'process_layer_healthy': False,
                        'service_active': False,
                    },
                )
            )

            self.assertEqual(plan.actions[0].kind, 'restart_service')
            self.assertIn('heuristic', plan.rationale)
            self.assertNotEqual(plan.plan_id, 'suppressed-process')

    def test_rule_agent_skips_low_confidence_rule_and_falls_back_to_static_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules_dir = root / 'rules'
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / 'low-confidence-process.json').write_text(
                json.dumps(
                    {
                        'rule_id': 'low-confidence-process',
                        'match': {'normalized_failure_signature': 'process-down'},
                        'diagnosis': 'restart service',
                        'actions': [{'kind': 'restart_service', 'params': {}}],
                        'validations': ['minimal_usable_ready'],
                        'confidence': 'low',
                        'evidence_count': 1,
                    }
                ),
                encoding='utf-8',
            )

            from openclaw_watchdog.rescue_agents.rule_agent import RuleBasedRescueAgent
            from openclaw_watchdog.learning import LearningStore

            agent = RuleBasedRescueAgent(rule_store=LearningStore(root=root))
            plan = agent.propose_plan(
                RescueContext(
                    incident_id='incident-low-confidence',
                    health_level='failed',
                    metadata={
                        'failure_signature': 'watchdog-reported-timeout',
                        'process_layer_healthy': False,
                        'service_active': False,
                    },
                )
            )

            self.assertEqual(plan.actions[0].kind, 'restart_service')
            self.assertIn('heuristic', plan.rationale)
            self.assertNotEqual(plan.plan_id, 'low-confidence-process')

    def test_uses_recent_case_evidence_in_rationale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules_dir = root / 'rules'
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / 'invalid-config.json').write_text(
                json.dumps(
                    {
                        'rule_id': 'invalid-config',
                        'match': {'failure_signature': 'config-invalid'},
                        'diagnosis': 'config invalid',
                        'actions': [{'kind': 'restore_last_good', 'params': {}}],
                        'validations': ['minimal_usable_ready'],
                    }
                ),
                encoding='utf-8',
            )

            from openclaw_watchdog.rescue_agents.rule_agent import RuleBasedRescueAgent
            from openclaw_watchdog.learning import LearningStore

            store = LearningStore(root=root)
            store.record_case(
                {
                    'case_id': 'case-1',
                    'failure_signature': 'config-invalid',
                    'status': 'recovered',
                }
            )
            agent = RuleBasedRescueAgent(rule_store=store)
            plan = agent.propose_plan(
                RescueContext(incident_id='incident-2', health_level='failed', metadata={'failure_signature': 'config-invalid'})
            )

            self.assertIn('case:case-1', plan.rationale)


if __name__ == '__main__':
    unittest.main()
