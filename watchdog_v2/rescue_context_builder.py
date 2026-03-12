from __future__ import annotations

import json
import os
import shutil
from datetime import datetime

from watchdog_v2 import learning_signatures


def failure_signature_for(probe: dict[str, object]) -> str:
    if bool(probe.get("config_invalid", False)):
        return "config-invalid"
    if not bool(probe.get("process_layer_healthy", False)):
        return "process-down"
    if bool(probe.get("service_layer_healthy", True)) and not bool(probe.get("minimal_usable_ready", False)):
        return "conversation-down"
    if not bool(probe.get("service_layer_healthy", True)):
        return "service-layer-degraded"
    return "unknown-failure"


def available_executors(config) -> tuple[str, ...]:
    priority = list(getattr(config, "watchdog_rescue_executor_priority", [])) or [
        "codex",
        "claude-code",
        "gemini-cli",
        "opencode",
        "litellm",
        "rule-agent",
    ]
    available: list[str] = []
    command_map = {
        "codex": ("codex",),
        "claude-code": ("claude", "claude-code"),
        "gemini-cli": ("gemini", "gemini-cli"),
        "opencode": ("opencode",),
    }
    for name in priority:
        if name == "rule-agent":
            available.append(name)
            continue
        if name == "litellm":
            litellm_enabled = bool(getattr(config, "watchdog_litellm_enabled", False))
            litellm_model = str(getattr(config, "watchdog_litellm_model", "") or "")
            if litellm_enabled and litellm_model:
                available.append(name)
            continue
        for command in command_map.get(name, (name,)):
            if shutil.which(command):
                available.append(name)
                break
    if "rule-agent" not in available:
        available.append("rule-agent")
    return tuple(available)


def rescue_command(config, name: str) -> str:
    if name == "codex":
        configured = str(getattr(config, "watchdog_codex_bin", "codex") or "codex")
        return configured if shutil.which(configured) else "codex"
    if name == "opencode":
        configured = str(getattr(config, "watchdog_opencode_fallback_bin", "opencode") or "opencode")
        return configured if shutil.which(configured) else "opencode"
    candidates = {
        "claude-code": ("claude", "claude-code"),
        "gemini-cli": ("gemini", "gemini-cli"),
    }
    for candidate in candidates.get(name, (name,)):
        if shutil.which(candidate):
            return candidate
    return name


def build_rescue_context(engine, probe: dict[str, object]):
    from watchdog_v2.learning import LearningStore
    from watchdog_v2.rescue_models import RescueContext

    failure_signature = failure_signature_for(probe)
    normalized_failure_signature = learning_signatures.normalized_failure_signature(
        {
            'failure_signature': failure_signature,
            'config_invalid': bool(probe.get('config_invalid', False)),
            'process_layer_healthy': bool(probe.get('process_layer_healthy', False)),
            'service_layer_healthy': bool(probe.get('service_layer_healthy', False)),
            'minimal_usable_ready': bool(probe.get('minimal_usable_ready', False)),
            'conversation_ready': bool(probe.get('conversation_ready', False)),
            'config_drift_detected': bool(probe.get('config_drift_detected', False)),
            'drift_scope': list(probe.get('drift_scope', [])) if isinstance(probe.get('drift_scope', []), list) else [],
        }
    )
    store = LearningStore(root=engine.config.watchdog_rescue_knowledge_root)
    recent_case_criteria = {
        'failure_signature': failure_signature,
        'normalized_failure_signature': normalized_failure_signature,
        'config_invalid': bool(probe.get('config_invalid', False)),
        'process_layer_healthy': bool(probe.get('process_layer_healthy', False)),
        'service_layer_healthy': bool(probe.get('service_layer_healthy', False)),
        'minimal_usable_ready': bool(probe.get('minimal_usable_ready', False)),
        'conversation_ready': bool(probe.get('conversation_ready', False)),
        'config_drift_detected': bool(probe.get('config_drift_detected', False)),
        'drift_scope': list(probe.get('drift_scope', [])) if isinstance(probe.get('drift_scope', []), list) else [],
    }
    recent_cases = [
        {
            'case_id': str(case.get('case_id', '') or ''),
            'executor': str(case.get('executor', '') or ''),
            'strategy': str(case.get('strategy', '') or ''),
            'status': str(case.get('status', '') or ''),
        }
        for case in store.similar_cases(recent_case_criteria)[-3:]
    ]
    known_rules = [
        {
            'rule_id': str(rule.get('rule_id', '') or ''),
            'match': dict(rule.get('match', {})) if isinstance(rule.get('match', {}), dict) else {},
            'diagnosis': str(rule.get('diagnosis', '') or ''),
        }
        for rule in store.load_rules()[-5:]
    ]
    metadata = {
        "config_invalid": bool(probe.get("config_invalid", False)),
        "failure_signature": failure_signature,
        "normalized_failure_signature": normalized_failure_signature,
        "conversation_status": str(probe.get("conversation_status", "down") or "down"),
        "process_layer_healthy": bool(probe.get("process_layer_healthy", False)),
        "service_layer_healthy": bool(probe.get("service_layer_healthy", False)),
        "minimal_usable_ready": bool(probe.get("minimal_usable_ready", False)),
        "service_active": bool(probe.get("service_active", False)),
        "recent_cases": recent_cases,
        "known_rules": known_rules,
    }
    incident_id = engine.ctx.incident_id or f"incident-{datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}"
    engine.ctx.incident_id = incident_id
    return RescueContext(
        incident_id=incident_id,
        health_level=str(engine.read_run_state().get("health_level", "failed") or "failed"),
        conversation_status=str(probe.get("conversation_status", "down") or "down"),
        available_executors=available_executors(engine.config),
        editable_paths=tuple(str(item) for item in getattr(engine.config, "watchdog_rescue_editable_paths", [])),
        editable_keys=tuple(str(item) for item in getattr(engine.config, "watchdog_rescue_editable_keys", [])),
        probe=dict(probe),
        metadata=metadata,
    )


def build_litellm_client(config):
    if not bool(getattr(config, "watchdog_litellm_enabled", False)):
        return None
    model = str(getattr(config, "watchdog_litellm_model", "") or "")
    if not model:
        return None
    try:
        import litellm  # type: ignore
    except ImportError:
        return None

    class _LiteLLMClient:
        def generate_plan(self, payload: dict[str, object]) -> dict[str, object]:
            api_key_env = str(getattr(config, "watchdog_litellm_api_key_env", "") or "")
            api_key = os.environ.get(api_key_env, "") if api_key_env else ""
            response = litellm.completion(
                model=model,
                api_base=str(getattr(config, "watchdog_litellm_api_base", "") or "") or None,
                api_key=api_key or None,
                timeout=int(getattr(config, "watchdog_litellm_timeout_seconds", 60) or 60),
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the OpenClaw rescue planner. Return JSON only with plan_id, diagnosis, actions, validations, rollback_strategy, risk_level, and rationale. "
                            "Never emit shell commands or arbitrary execution."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
            content = ""
            choices = getattr(response, "choices", None)
            if choices:
                first = choices[0]
                message = getattr(first, "message", None)
                content = getattr(message, "content", "") if message is not None else ""
            elif isinstance(response, dict):
                try:
                    content = response["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError):
                    content = ""
            if isinstance(content, list):
                content = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
            if not isinstance(content, str) or not content.strip():
                raise ValueError("LiteLLM did not return structured JSON content")
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("LiteLLM response must be a JSON object")
            return parsed

    return _LiteLLMClient()
