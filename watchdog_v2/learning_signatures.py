from __future__ import annotations

from typing import Any


def normalized_failure_signature(payload: dict[str, Any] | None) -> str:
    data = payload if isinstance(payload, dict) else {}
    explicit = str(data.get('normalized_failure_signature', '') or '').strip()
    if explicit:
        return explicit

    signature_parts: list[str] = []
    if bool(data.get('config_invalid', False)):
        signature_parts.append('config-invalid')
    else:
        process_layer_known = 'process_layer_healthy' in data or 'service_active' in data
        process_layer_healthy = bool(data.get('process_layer_healthy', data.get('service_active', True)))
        if process_layer_known and not process_layer_healthy:
            signature_parts.append('process-down')
        else:
            if 'service_layer_healthy' in data and not bool(data.get('service_layer_healthy', True)):
                signature_parts.append('service-layer-degraded')
            elif 'minimal_usable_ready' in data and not bool(data.get('minimal_usable_ready', False)):
                signature_parts.append('minimal-unavailable')
            elif 'conversation_ready' in data and not bool(data.get('conversation_ready', False)):
                signature_parts.append('conversation-degraded')

    if bool(data.get('config_drift_detected', False)) or bool(data.get('drift_scope')):
        signature_parts.append('drift-detected')

    if signature_parts:
        return '+'.join(signature_parts)

    raw_failure_signature = str(data.get('failure_signature', '') or '').strip()
    return raw_failure_signature or 'unknown-failure'
