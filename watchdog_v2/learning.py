from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from watchdog_v2 import learning_signatures, rescue_policy


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
        case_payload = dict(payload)
        case_payload['normalized_failure_signature'] = learning_signatures.normalized_failure_signature(case_payload)
        target = self.cases_dir / f'{case_id}.json'
        target.write_text(json.dumps(case_payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
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
        normalized_signature = learning_signatures.normalized_failure_signature(criteria)
        raw_signature = str(criteria.get('failure_signature', '') or '').strip()
        cases = self.load_cases()
        if normalized_signature:
            normalized_matches = [
                case
                for case in cases
                if learning_signatures.normalized_failure_signature(case) == normalized_signature
            ]
            if normalized_matches:
                return normalized_matches
        if not raw_signature:
            return []
        return [case for case in cases if str(case.get('failure_signature', '') or '') == raw_signature]

    def _promotion_metadata(self, *, candidate_rule: dict[str, Any], cases: list[dict[str, Any]], risk_level: str) -> dict[str, Any]:
        latest_case = cases[-1] if cases else {}
        return {
            'evidence_count': len(cases),
            'last_case_id': str(latest_case.get('case_id', '') or ''),
            'last_seen_at': str(latest_case.get('recovered_at', '') or latest_case.get('created_at', '') or ''),
            'mutation_scope': rescue_policy.mutation_scope(candidate_rule.get('actions', [])),
            'confidence': rescue_policy.confidence_label(evidence_count=len(cases), risk_level=risk_level),
        }

    def _rule_path(self, rule_id: str) -> Path:
        return self.rules_dir / f'{rule_id}.json'

    def _review_path(self, rule_id: str) -> Path:
        return self.reviews_dir / f'{rule_id}.json'

    def _load_rule_payload(self, rule_id: str) -> dict[str, Any] | None:
        path = self._rule_path(rule_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _apply_negative_evidence(self, *, result: PromotionResult, failed_groups: dict[str, list[dict[str, Any]]]) -> None:
        suppression_threshold = rescue_policy.learned_rule_suppression_threshold()
        for rule_id, cases in failed_groups.items():
            rule_payload = self._load_rule_payload(rule_id)
            if rule_payload is None:
                continue
            negative_evidence_count = len(cases)
            rule_payload['negative_evidence_count'] = negative_evidence_count
            high_risk_cases = [case for case in cases if str(case.get('risk_level', 'medium') or 'medium') == 'high']
            if high_risk_cases:
                latest_case = high_risk_cases[-1]
                rule_payload['status'] = 'pending-review'
                review_payload = {
                    'status': 'pending-review',
                    'candidate_rule': dict(rule_payload),
                    'cases': [str(case.get('case_id', '') or '') for case in cases],
                    'negative_evidence_count': negative_evidence_count,
                    'last_failure_case_id': str(latest_case.get('case_id', '') or ''),
                }
                self._review_path(rule_id).write_text(
                    json.dumps(review_payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                    encoding='utf-8',
                )
                result.pending_review += 1
            if negative_evidence_count >= suppression_threshold:
                rule_payload['suppressed'] = True
            self._rule_path(rule_id).write_text(
                json.dumps(rule_payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                encoding='utf-8',
            )

    def promote_candidates(self) -> PromotionResult:
        result = PromotionResult()
        candidate_groups: dict[str, list[dict[str, Any]]] = {}
        failed_groups: dict[str, list[dict[str, Any]]] = {}
        for case in self.load_cases():
            candidate_rule = case.get('candidate_rule') if isinstance(case.get('candidate_rule'), dict) else None
            if not candidate_rule:
                continue
            rule_id = str(candidate_rule.get('rule_id', '') or '').strip()
            if not rule_id:
                continue
            status = str(case.get('status', '') or '')
            if status == 'recovered':
                candidate_groups.setdefault(rule_id, []).append(case)
                candidate_path = self.candidate_rules_dir / f'{rule_id}.json'
                if not candidate_path.exists():
                    candidate_path.write_text(json.dumps(candidate_rule, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            elif status == 'failed':
                failed_groups.setdefault(rule_id, []).append(case)

        for rule_id, cases in candidate_groups.items():
            latest_case = cases[-1]
            candidate_rule = latest_case.get('candidate_rule') if isinstance(latest_case.get('candidate_rule'), dict) else {}
            risk_level = str(latest_case.get('risk_level', 'medium') or 'medium')
            metadata = self._promotion_metadata(candidate_rule=candidate_rule, cases=cases, risk_level=risk_level)
            candidate_rule_payload = dict(candidate_rule)
            candidate_rule_payload.update(metadata)
            existing_rule = self._load_rule_payload(rule_id) or {}
            candidate_rule_payload['negative_evidence_count'] = int(existing_rule.get('negative_evidence_count', 0) or 0)
            candidate_rule_payload['suppressed'] = bool(existing_rule.get('suppressed', False))
            if str(existing_rule.get('status', '') or '') == 'pending-review':
                candidate_rule_payload['status'] = 'pending-review'
            if risk_level == 'high':
                target = self.reviews_dir / f'{rule_id}.json'
                target.write_text(json.dumps({'status': 'pending-review', 'candidate_rule': candidate_rule_payload, 'cases': [case.get('case_id', '') for case in cases], **metadata}, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
                result.pending_review += 1
                continue
            if len(cases) >= 3:
                target = self.rules_dir / f'{rule_id}.json'
                target.write_text(json.dumps(candidate_rule_payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
                result.auto_promoted += 1

        self._apply_negative_evidence(result=result, failed_groups=failed_groups)
        return result
