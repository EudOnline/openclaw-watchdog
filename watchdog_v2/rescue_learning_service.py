from __future__ import annotations

import re
from datetime import datetime

from watchdog_v2 import learning_signatures


def record_learning_from_recovery(
    engine,
    *,
    strategy: str,
    recovery_kind: str,
    probe: dict[str, object],
    context=None,
    dispatch_result=None,
    plan_result=None,
) -> dict[str, object]:
    from watchdog_v2.learning import LearningStore

    store = LearningStore(root=engine.config.watchdog_rescue_knowledge_root)
    metadata = context.metadata if context is not None and isinstance(getattr(context, 'metadata', None), dict) else {}
    failure_signature = str(metadata.get("failure_signature", "") or engine._rescue_failure_signature(probe))
    normalized_failure_signature = str(
        metadata.get('normalized_failure_signature', '')
        or learning_signatures.normalized_failure_signature(
            {
                'failure_signature': failure_signature,
                'config_invalid': bool(metadata.get('config_invalid', False) or probe.get('config_invalid', False)),
                'process_layer_healthy': bool(metadata.get('process_layer_healthy', probe.get('process_layer_healthy', False))),
                'service_layer_healthy': bool(metadata.get('service_layer_healthy', probe.get('service_layer_healthy', False))),
                'minimal_usable_ready': bool(metadata.get('minimal_usable_ready', probe.get('minimal_usable_ready', False))),
                'conversation_ready': bool(metadata.get('conversation_ready', probe.get('conversation_ready', False))),
                'config_drift_detected': bool(metadata.get('config_drift_detected', False) or probe.get('config_drift_detected', False)),
                'drift_scope': list(metadata.get('drift_scope', [])) if isinstance(metadata.get('drift_scope', []), list) else [],
            }
        )
    )
    rule_slug = re.sub(r"[^a-z0-9-]+", "-", normalized_failure_signature.lower()).strip("-") or "rescue-rule"
    plan = getattr(dispatch_result, 'plan', None) if dispatch_result is not None else None
    final_executor = str(getattr(dispatch_result, 'final_executor', '') or strategy)
    candidate_rule = None
    if plan is not None:
        match = {"normalized_failure_signature": normalized_failure_signature}
        if bool(metadata.get("config_invalid", False)):
            match["config_invalid"] = True
        candidate_rule = {
            "rule_id": f"{rule_slug}-{final_executor or 'rescue'}",
            "match": match,
            "diagnosis": plan.diagnosis,
            "actions": [action.to_dict() for action in plan.actions],
            "validations": list(plan.validations),
        }
    risk_level = plan.risk_level if plan is not None else 'low'
    payload = {
        "case_id": f"{engine.ctx.incident_id or 'incident'}-{final_executor or strategy}-{datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}",
        "incident_id": engine.ctx.incident_id,
        "failure_signature": failure_signature,
        "normalized_failure_signature": normalized_failure_signature,
        "status": "recovered",
        "executor": final_executor or strategy,
        "strategy": strategy,
        "recovery_kind": recovery_kind,
        "plan_id": plan.plan_id if plan is not None else '',
        "risk_level": risk_level,
        "candidate_rule": candidate_rule,
        "recovered_at": datetime.now().astimezone().isoformat(timespec='seconds'),
    }
    case_path = store.record_successful_case(payload)
    promotion = store.promote_candidates()
    candidate_rule_status = 'none'
    if candidate_rule is not None:
        if promotion.pending_review > 0:
            candidate_rule_status = 'pending-review'
        elif promotion.auto_promoted > 0:
            candidate_rule_status = 'auto-promoted'
        else:
            candidate_rule_status = 'candidate-recorded'
    return {
        'case_ingest_result': f'recorded:{case_path.name}',
        'candidate_rule_status': candidate_rule_status,
    }


def record_learning_from_rescue(engine, *, context, dispatch_result, plan_result) -> dict[str, object]:
    return record_learning_from_recovery(
        engine,
        strategy=str(getattr(dispatch_result, 'final_executor', '') or 'rescue'),
        recovery_kind='rescue',
        probe=context.probe if context is not None else {},
        context=context,
        dispatch_result=dispatch_result,
        plan_result=plan_result,
    )
