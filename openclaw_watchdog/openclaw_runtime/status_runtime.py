from __future__ import annotations

import json
from typing import cast
from urllib.parse import urlparse

from openclaw_watchdog.openclaw_runtime.contracts import GatewayContract
from openclaw_watchdog.openclaw_runtime.contracts import StatusContract


def coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'on', 'configured', 'connected', 'ready', 'ok', 'active'}:
        return True
    if text in {'0', 'false', 'no', 'off', 'missing', 'down', 'none', 'inactive', 'not-configured'}:
        return False
    return None


def extract_json(text: str) -> dict[str, object] | None:
    text = text.strip()
    if not text:
        return None
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != '{':
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def run_json(engine, command: list[str], *, timeout: int = 20) -> dict[str, object] | None:
    result = engine.run_command(command, timeout=timeout)
    return extract_json(result.output)


def object_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return cast(dict[str, object], value)
    return {}


def read_status(engine) -> dict[str, object] | None:
    timeout_seconds = int(engine.config.watchdog_service_level_timeout_seconds)
    return run_json(
        engine,
        ['openclaw', 'status', '--json', '--timeout', str(timeout_seconds * 1000)],
        timeout=timeout_seconds + 5,
    )


def read_health(engine) -> dict[str, object] | None:
    timeout_seconds = int(engine.config.watchdog_service_level_timeout_seconds)
    return run_json(
        engine,
        ['openclaw', 'health', '--json'],
        timeout=timeout_seconds + 5,
    )


def normalize_status_contract(status_payload: dict[str, object] | None, *, configured_port: int) -> StatusContract:
    payload = status_payload if isinstance(status_payload, dict) else {}
    gateway = object_dict(payload.get('gateway'))
    conversation = object_dict(payload.get('conversation'))
    url = str(gateway.get('url', '') or '')
    parsed = urlparse(url) if url else None
    reachable = coerce_bool(gateway.get('reachable'))
    misconfigured = coerce_bool(gateway.get('misconfigured'))
    detected_port = parsed.port if parsed and parsed.port else configured_port
    return StatusContract(
        gateway=GatewayContract(
            url=url,
            reachable=reachable is True,
            misconfigured=misconfigured is True,
            configured_port=configured_port,
            detected_port=detected_port,
        ),
        conversation=dict(conversation),
        raw=dict(payload),
    )


def detect_gateway_contract(engine, status_payload: dict[str, object] | None) -> GatewayContract:
    return normalize_status_contract(
        status_payload,
        configured_port=engine.config.openclaw_gateway_port,
    ).gateway
