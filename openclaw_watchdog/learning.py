from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openclaw_watchdog import learning_signatures, rescue_policy


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
        case_payload = self._normalized_case_payload(payload)
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
                cases.append(self._normalized_case_payload(payload))
        return cases

    def _normalized_case_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        case_payload = dict(payload)
        normalized_failure_signature = str(case_payload.get('normalized_failure_signature', '') or '').strip()
        if normalized_failure_signature:
            case_payload['normalized_failure_signature'] = normalized_failure_signature
        else:
            case_payload['normalized_failure_signature'] = learning_signatures.normalized_failure_signature(case_payload)
        case_payload['learning_phase'] = self._learning_phase(case_payload)
        case_payload['outcome_kind'] = self._outcome_kind(case_payload)
        case_payload['evidence_quality'] = self._evidence_quality(case_payload)
        case_payload['promotion_eligible'] = self._promotion_eligible(case_payload)
        return case_payload

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

    def _learning_phase(self, payload: dict[str, Any]) -> str:
        explicit = str(payload.get('learning_phase', '') or payload.get('recovery_kind', '') or '').strip().lower()
        if explicit in {'deterministic', 'rescue'}:
            return explicit
        if isinstance(payload.get('candidate_rule'), dict) or str(payload.get('executor', '') or '') or str(payload.get('strategy', '') or ''):
            return 'rescue'
        return 'rescue' if str(payload.get('status', '') or '').strip().lower() == 'recovered' else 'deterministic'

    def _outcome_kind(self, payload: dict[str, Any]) -> str:
        explicit = str(payload.get('outcome_kind', '') or '').strip()
        if explicit:
            return explicit
        phase = self._learning_phase(payload)
        status = str(payload.get('status', '') or '').strip().lower()
        rollback_performed = bool(payload.get('rollback_performed', False) or payload.get('rollback_occurred', False))
        if status == 'failed':
            if phase == 'rescue' and rollback_performed:
                return 'rolled-back-rescue'
            if phase == 'rescue':
                return 'rescue-failure'
            return 'deterministic-failure'
        if status == 'recovered':
            if phase == 'rescue':
                return 'successful-rescue'
            return 'deterministic-recovery'
        return 'observed'

    def _evidence_quality(self, payload: dict[str, Any]) -> str:
        explicit = str(payload.get('evidence_quality', '') or '').strip()
        if explicit:
            return explicit
        outcome_kind = self._outcome_kind(payload)
        risk_level = str(payload.get('risk_level', 'medium') or 'medium')
        candidate_rule = payload.get('candidate_rule') if isinstance(payload.get('candidate_rule'), dict) else {}
        has_candidate_rule = bool(str(candidate_rule.get('rule_id', '') or '').strip())
        has_validations = bool(
            isinstance(candidate_rule.get('validations', []), list)
            and any(str(item).strip() for item in candidate_rule.get('validations', []))
        )
        if outcome_kind in {'deterministic-failure', 'rescue-failure', 'rolled-back-rescue'}:
            return 'negative'
        if risk_level == 'high':
            return 'review-required'
        if outcome_kind == 'successful-rescue':
            if has_candidate_rule and has_validations:
                return 'strong'
            return 'medium'
        if outcome_kind == 'deterministic-recovery':
            return 'weak'
        return 'weak'

    def _promotion_eligible(self, payload: dict[str, Any]) -> bool:
        candidate_rule = payload.get('candidate_rule') if isinstance(payload.get('candidate_rule'), dict) else {}
        if not str(candidate_rule.get('rule_id', '') or '').strip():
            return False
        outcome_kind = self._outcome_kind(payload)
        evidence_quality = self._evidence_quality(payload)
        return outcome_kind == 'successful-rescue' and evidence_quality in {'strong', 'medium', 'review-required'}

    def _promotion_metadata(self, *, candidate_rule: dict[str, Any], cases: list[dict[str, Any]], risk_level: str) -> dict[str, Any]:
        latest_case = cases[-1] if cases else {}
        strong_evidence_count = sum(1 for case in cases if str(case.get('evidence_quality', '') or '') == 'strong')
        medium_evidence_count = sum(1 for case in cases if str(case.get('evidence_quality', '') or '') == 'medium')
        review_required_evidence_count = sum(1 for case in cases if str(case.get('evidence_quality', '') or '') == 'review-required')
        evidence_score = strong_evidence_count * 2 + medium_evidence_count + review_required_evidence_count
        phase_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        for case in cases:
            phase = str(case.get('learning_phase', '') or 'unknown')
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
            outcome = str(case.get('outcome_kind', '') or 'unknown')
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        return {
            'evidence_count': len(cases),
            'evidence_score': evidence_score,
            'strong_evidence_count': strong_evidence_count,
            'medium_evidence_count': medium_evidence_count,
            'review_required_evidence_count': review_required_evidence_count,
            'last_case_id': str(latest_case.get('case_id', '') or ''),
            'last_seen_at': str(latest_case.get('recovered_at', '') or latest_case.get('created_at', '') or ''),
            'mutation_scope': rescue_policy.mutation_scope(candidate_rule.get('actions', [])),
            'phase_counts': phase_counts,
            'outcome_counts': outcome_counts,
            'confidence': rescue_policy.confidence_label(evidence_count=evidence_score, risk_level=risk_level),
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
            outcome_kind = str(case.get('outcome_kind', '') or '')
            if bool(case.get('promotion_eligible', False)):
                candidate_groups.setdefault(rule_id, []).append(case)
                candidate_path = self.candidate_rules_dir / f'{rule_id}.json'
                if not candidate_path.exists():
                    candidate_path.write_text(json.dumps(candidate_rule, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            elif status == 'failed' or outcome_kind in {'deterministic-failure', 'rescue-failure', 'rolled-back-rescue'}:
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
            if risk_level == 'high' or int(metadata.get('review_required_evidence_count', 0) or 0) > 0:
                target = self.reviews_dir / f'{rule_id}.json'
                target.write_text(json.dumps({'status': 'pending-review', 'candidate_rule': candidate_rule_payload, 'cases': [case.get('case_id', '') for case in cases], **metadata}, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
                result.pending_review += 1
                continue
            if int(metadata.get('strong_evidence_count', 0) or 0) >= 1 and int(metadata.get('evidence_score', 0) or 0) >= 3:
                target = self.rules_dir / f'{rule_id}.json'
                target.write_text(json.dumps(candidate_rule_payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
                result.auto_promoted += 1

        self._apply_negative_evidence(result=result, failed_groups=failed_groups)
        return result
