from __future__ import annotations

from typing import Any

from openclaw_watchdog import rescue_policy
from openclaw_watchdog.rescue_models import RescueContext, RescuePlan


class LiteLLMSpecialistAgent:
    name = 'litellm'

    def __init__(self, *, config, client=None) -> None:
        self.config = config
        self.client = client

    def is_available(self, context: RescueContext) -> bool:
        return bool(
            getattr(self.config, 'watchdog_litellm_enabled', False)
            and str(getattr(self.config, 'watchdog_litellm_model', '') or '')
            and self.client is not None
        )

    def build_payload(self, context: RescueContext) -> dict[str, Any]:
        metadata = context.metadata if isinstance(context.metadata, dict) else {}
        return {
            'incident_id': context.incident_id,
            'health_level': context.health_level,
            'conversation_status': context.conversation_status,
            'available_executors': list(context.available_executors),
            'editable_paths': list(context.editable_paths),
            'editable_keys': list(context.editable_keys),
            'model': str(getattr(self.config, 'watchdog_litellm_model', '') or ''),
            'api_base': str(getattr(self.config, 'watchdog_litellm_api_base', '') or ''),
            'failure_signature': str(metadata.get('failure_signature', '') or ''),
            'recent_cases': list(metadata.get('recent_cases', [])) if isinstance(metadata.get('recent_cases', []), list) else [],
            'known_rules': list(metadata.get('known_rules', [])) if isinstance(metadata.get('known_rules', []), list) else [],
            'openclaw_policy': rescue_policy.openclaw_policy_snapshot(self.config),
        }

    def propose_plan(self, context: RescueContext) -> RescuePlan:
        if not self.is_available(context):
            raise ValueError('LiteLLM specialist agent is not available')
        response = self.client.generate_plan(self.build_payload(context))
        if not isinstance(response, dict):
            raise ValueError('LiteLLM response must be a JSON object')
        if 'shell' in response:
            raise ValueError('free-form shell output is not allowed')
        if 'actions' not in response or 'plan_id' not in response:
            raise ValueError('LiteLLM response must contain plan_id and actions')
        return RescuePlan.from_dict(response)
