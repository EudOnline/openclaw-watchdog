from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from watchdog_v2 import rescue_policy


@dataclass(eq=True)
class PromotionResult:
    auto_promoted: int = 0
    pending_review: int = 0


class LearningStore:
    def __init__(self, *, root: Path) -> None:
        self.root = Path(root)
        self.cases_dir = self.root / 'cases'
        self.candidate_rules_dir = self.root / 'candidate-rules'
        self.rules_dir = self.root / 'rules'
        self.reviews_dir = self.root / 'reviews'
        for directory in (self.cases_dir, self.candidate_rules_dir, self.rules_dir, self.reviews_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def record_case(self, payload: dict[str, Any]) -> Path:
        case_id = str(payload.get('case_id', '') or '').strip() or 'case'
        target = self.cases_dir / f'{case_id}.json'
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        return target

    def record_successful_case(self, payload: dict[str, Any]) -> Path:
        return self.record_case(payload)

    def load_rules(self) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        for path in sorted(self.rules_dir.glob('*.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rules.append(payload)
        return rules

    def load_cases(self) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        for path in sorted(self.cases_dir.glob('*.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                cases.append(payload)
        return cases

    def similar_cases(self, criteria: dict[str, Any]) -> list[dict[str, Any]]:
        signature = str(criteria.get('failure_signature', '') or '')
        if not signature:
            return []
        return [case for case in self.load_cases() if str(case.get('failure_signature', '') or '') == signature]



    def _promotion_metadata(self, *, candidate_rule: dict[str, Any], cases: list[dict[str, Any]], risk_level: str) -> dict[str, Any]:
        latest_case = cases[-1] if cases else {}
        return {
            'evidence_count': len(cases),
            'last_case_id': str(latest_case.get('case_id', '') or ''),
            'last_seen_at': str(latest_case.get('recovered_at', '') or latest_case.get('created_at', '') or ''),
            'mutation_scope': rescue_policy.mutation_scope(candidate_rule.get('actions', [])),
            'confidence': rescue_policy.confidence_label(evidence_count=len(cases), risk_level=risk_level),
        }

    def promote_candidates(self) -> PromotionResult:
        result = PromotionResult()
        candidate_groups: dict[str, list[dict[str, Any]]] = {}
        for case in self.load_cases():
            if str(case.get('status', '') or '') != 'recovered':
                continue
            candidate_rule = case.get('candidate_rule') if isinstance(case.get('candidate_rule'), dict) else None
            if not candidate_rule:
                continue
            rule_id = str(candidate_rule.get('rule_id', '') or '').strip()
            if not rule_id:
                continue
            candidate_groups.setdefault(rule_id, []).append(case)
            candidate_path = self.candidate_rules_dir / f'{rule_id}.json'
            if not candidate_path.exists():
                candidate_path.write_text(json.dumps(candidate_rule, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')

        for rule_id, cases in candidate_groups.items():
            latest_case = cases[-1]
            candidate_rule = latest_case.get('candidate_rule') if isinstance(latest_case.get('candidate_rule'), dict) else {}
            risk_level = str(latest_case.get('risk_level', 'medium') or 'medium')
            metadata = self._promotion_metadata(candidate_rule=candidate_rule, cases=cases, risk_level=risk_level)
            candidate_rule_payload = dict(candidate_rule)
            candidate_rule_payload.update(metadata)
            if risk_level == 'high':
                target = self.reviews_dir / f'{rule_id}.json'
                target.write_text(json.dumps({'status': 'pending-review', 'candidate_rule': candidate_rule_payload, 'cases': [case.get('case_id', '') for case in cases], **metadata}, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
                result.pending_review += 1
                continue
            if len(cases) >= 3:
                target = self.rules_dir / f'{rule_id}.json'
                target.write_text(json.dumps(candidate_rule_payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
                result.auto_promoted += 1
        return result
