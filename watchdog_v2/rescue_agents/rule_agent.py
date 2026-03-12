from __future__ import annotations

from typing import Any

from watchdog_v2 import learning_signatures, rescue_policy
from watchdog_v2.learning import LearningStore
from watchdog_v2.rescue_models import RescueContext, RescuePlan


class RuleBasedRescueAgent:
    name = 'rule-agent'

    def __init__(self, *, rule_store: LearningStore) -> None:
        self.rule_store = rule_store

    def is_available(self, context: RescueContext) -> bool:
        return True

    def _context_metadata(self, context: RescueContext) -> dict[str, Any]:
        metadata = dict(context.metadata) if isinstance(context.metadata, dict) else {}
        metadata['normalized_failure_signature'] = learning_signatures.normalized_failure_signature(metadata)
        return metadata

    def _is_active_rule(self, rule: dict[str, Any]) -> bool:
        if bool(rule.get('suppressed', False)):
            return False
        if str(rule.get('status', '') or '') == 'pending-review':
            return False
        return True

    def _matches(self, rule: dict[str, Any], context: RescueContext) -> bool:
        match = rule.get('match', {}) if isinstance(rule.get('match', {}), dict) else {}
        metadata = self._context_metadata(context)
        for key, expected in match.items():
            if metadata.get(key) != expected:
                return False
        return True

    def propose_plan(self, context: RescueContext) -> RescuePlan:
        metadata = self._context_metadata(context)
        for rule in self.rule_store.load_rules():
            if not self._is_active_rule(rule):
                continue
            if not self._matches(rule, context):
                continue
            similar_cases = self.rule_store.similar_cases(metadata)
            rationale_parts: list[str] = []
            if similar_cases:
                rationale_parts.extend(f"case:{case.get('case_id', '')}" for case in similar_cases if case.get('case_id'))
            return RescuePlan.from_dict(
                {
                    'plan_id': str(rule.get('rule_id', '') or 'rule-plan'),
                    'diagnosis': str(rule.get('diagnosis', '') or ''),
                    'actions': list(rule.get('actions', [])) if isinstance(rule.get('actions', []), list) else [],
                    'validations': list(rule.get('validations', [])) if isinstance(rule.get('validations', []), list) else [],
                    'rationale': ', '.join(rationale_parts),
                }
            )
        heuristic = rescue_policy.heuristic_plan(context)
        if heuristic is not None:
            return RescuePlan.from_dict(heuristic)
        raise ValueError('no matching rescue rule found')
