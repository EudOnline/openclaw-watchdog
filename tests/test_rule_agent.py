from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from watchdog_v2.rescue_models import RescueContext


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

            from watchdog_v2.rescue_agents.rule_agent import RuleBasedRescueAgent
            from watchdog_v2.learning import LearningStore

            agent = RuleBasedRescueAgent(rule_store=LearningStore(root=root))
            plan = agent.propose_plan(
                RescueContext(incident_id='incident-1', health_level='failed', metadata={'config_invalid': True})
            )

            self.assertEqual(plan.actions[0].kind, 'restore_last_good')
            self.assertEqual(plan.plan_id, 'invalid-config')

    def test_uses_process_down_heuristic_when_no_promoted_rule_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            from watchdog_v2.rescue_agents.rule_agent import RuleBasedRescueAgent
            from watchdog_v2.learning import LearningStore

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

            from watchdog_v2.rescue_agents.rule_agent import RuleBasedRescueAgent
            from watchdog_v2.learning import LearningStore

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
