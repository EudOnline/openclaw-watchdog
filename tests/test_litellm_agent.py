from __future__ import annotations

import unittest
from types import SimpleNamespace

from watchdog_v2.rescue_models import RescueContext


class FakeLiteLLMClient:
    def __init__(self, response):
        self.response = response
        self.payloads = []

    def generate_plan(self, payload):
        self.payloads.append(payload)
        return self.response


class LiteLLMAgentTests(unittest.TestCase):
    def test_agent_returns_structured_plan(self) -> None:
        from watchdog_v2.rescue_agents.litellm_agent import LiteLLMSpecialistAgent

        client = FakeLiteLLMClient(
            response={
                'plan_id': 'plan-1',
                'diagnosis': 'rollback to recover',
                'actions': [{'kind': 'restore_last_good', 'params': {}}],
                'validations': ['minimal_usable_ready'],
            }
        )
        config = SimpleNamespace(
            watchdog_litellm_enabled=True,
            watchdog_litellm_model='openai/gpt-5',
            watchdog_litellm_api_base='https://example.invalid/v1',
        )
        agent = LiteLLMSpecialistAgent(config=config, client=client)
        plan = agent.propose_plan(RescueContext(incident_id='incident-1'))

        self.assertEqual(plan.actions[0].kind, 'restore_last_good')
        self.assertEqual(plan.plan_id, 'plan-1')

    def test_agent_payload_includes_openclaw_policy_and_learning_context(self) -> None:
        from watchdog_v2.rescue_agents.litellm_agent import LiteLLMSpecialistAgent

        client = FakeLiteLLMClient(
            response={
                'plan_id': 'plan-2',
                'diagnosis': 'restart the gateway',
                'actions': [{'kind': 'restart_service', 'params': {}}],
                'validations': ['minimal_usable_ready'],
            }
        )
        config = SimpleNamespace(
            watchdog_litellm_enabled=True,
            watchdog_litellm_model='openai/gpt-5',
            watchdog_litellm_api_base='https://example.invalid/v1',
            openclaw_config='~/.openclaw/openclaw.json',
            watchdog_survival_required_channels=('qqbot',),
            watchdog_rescue_editable_keys=('channels', 'extensions'),
        )
        agent = LiteLLMSpecialistAgent(config=config, client=client)
        agent.propose_plan(
            RescueContext(
                incident_id='incident-ctx',
                health_level='failed',
                conversation_status='down',
                metadata={
                    'failure_signature': 'process-down',
                    'recent_cases': [{'case_id': 'case-1'}],
                    'known_rules': [{'rule_id': 'process-down-rule'}],
                },
            )
        )

        payload = client.payloads[-1]
        self.assertEqual(payload['failure_signature'], 'process-down')
        self.assertEqual(payload['recent_cases'][0]['case_id'], 'case-1')
        self.assertEqual(payload['known_rules'][0]['rule_id'], 'process-down-rule')
        self.assertIn('openclaw_policy', payload)
        self.assertIn('required_channels', payload['openclaw_policy'])

    def test_agent_refuses_freeform_shell_output(self) -> None:
        from watchdog_v2.rescue_agents.litellm_agent import LiteLLMSpecialistAgent

        client = FakeLiteLLMClient(response={'shell': 'rm -rf /'})
        config = SimpleNamespace(
            watchdog_litellm_enabled=True,
            watchdog_litellm_model='openai/gpt-5',
            watchdog_litellm_api_base='https://example.invalid/v1',
        )
        agent = LiteLLMSpecialistAgent(config=config, client=client)
        with self.assertRaises(ValueError):
            agent.propose_plan(RescueContext(incident_id='incident-2'))


if __name__ == '__main__':
    unittest.main()
