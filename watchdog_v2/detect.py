from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from watchdog_v2.engine import WatchdogEngine


CORE_COMMANDS: tuple[str, ...] = (
    "python3",
    "openclaw",
    "systemctl",
    "ss",
    "ps",
    "journalctl",
    "codex",
    "claude",
    "claude-code",
    "gemini",
    "gemini-cli",
    "opencode",
)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_json(text: str) -> dict[str, object] | None:
    text = text.strip()
    if not text:
        return None
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _run_json(engine: WatchdogEngine, command: list[str], *, timeout: int = 20) -> dict[str, object] | None:
    result = engine.run_command(command, timeout=timeout)
    return _extract_json(result.output)


def _parse_kv_output(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "configured", "connected", "ready", "ok", "active"}:
        return True
    if text in {"0", "false", "no", "off", "missing", "down", "none", "inactive", "not-configured"}:
        return False
    return None


def _path_probe(path: Path) -> dict[str, object]:
    existing = path
    while not existing.exists() and existing.parent != existing:
        existing = existing.parent
    return {
        "path": str(path),
        "exists": path.exists(),
        "writable": os.access(path if path.exists() else existing, os.W_OK),
        "existing_anchor": str(existing),
    }


def _detect_commands() -> dict[str, dict[str, object]]:
    payload: dict[str, dict[str, object]] = {}
    for name in CORE_COMMANDS:
        resolved = shutil.which(name)
        payload[name] = {
            "available": bool(resolved),
            "path": resolved or "",
        }
    return payload


def _executor_inventory(engine: WatchdogEngine, commands: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    def _pick(*names: str) -> dict[str, object]:
        for name in names:
            command = commands.get(name, {}) if isinstance(commands.get(name, {}), dict) else {}
            if command.get('available'):
                return {
                    'available': True,
                    'command': name,
                    'path': str(command.get('path', '') or ''),
                }
        return {
            'available': False,
            'command': names[0] if names else '',
            'path': '',
        }

    litellm_enabled = bool(getattr(engine.config, 'watchdog_litellm_enabled', False))
    litellm_model = str(getattr(engine.config, 'watchdog_litellm_model', '') or '')
    litellm_available = litellm_enabled and bool(litellm_model)
    return {
        'codex': _pick('codex'),
        'claude-code': _pick('claude', 'claude-code'),
        'gemini-cli': _pick('gemini', 'gemini-cli'),
        'opencode': _pick('opencode'),
        'litellm': {
            'available': litellm_available,
            'enabled': litellm_enabled,
            'configured': litellm_available,
            'model': litellm_model,
        },
    }


def _gateway_probe(engine: WatchdogEngine, status_payload: dict[str, object] | None) -> dict[str, object]:
    gateway = status_payload.get("gateway") if isinstance(status_payload, dict) else {}
    gateway = gateway if isinstance(gateway, dict) else {}
    url = str(gateway.get("url", "") or "")
    parsed = urlparse(url) if url else None
    show = engine.run_command(
        [
            "systemctl",
            "--user",
            "show",
            "-p",
            "LoadState,UnitFileState,FragmentPath,ActiveState,SubState",
            engine.config.openclaw_gateway_service,
        ],
        timeout=15,
    )
    info = _parse_kv_output(show.output)
    return {
        "service": engine.config.openclaw_gateway_service,
        "show": info,
        "service_active": engine.service_active(),
        "service_main_pid": engine.service_main_pid(),
        "listener_pids": engine.listener_pids(),
        "configured_port": engine.config.openclaw_gateway_port,
        "detected_port": parsed.port if parsed and parsed.port else engine.config.openclaw_gateway_port,
        "url": url,
        "reachable": bool(gateway.get("reachable", False)),
        "misconfigured": bool(gateway.get("misconfigured", False)),
    }


def _channel_probe(health_payload: dict[str, object] | None) -> dict[str, object]:
    channels = health_payload.get("channels") if isinstance(health_payload, dict) else {}
    channels = channels if isinstance(channels, dict) else {}
    configured: list[str] = []
    activeish: list[str] = []
    details: dict[str, dict[str, object]] = {}
    for name, raw in sorted(channels.items()):
        if not isinstance(raw, dict):
            continue
        probe = raw.get("probe") if isinstance(raw.get("probe"), dict) else {}
        configured_flag = _coerce_bool(raw.get("configured"))
        connected_flag = _coerce_bool(raw.get("connected"))
        running_flag = _coerce_bool(raw.get("running"))
        probe_ok = _coerce_bool(probe.get("ok"))
        configured_effective = any(flag is True for flag in [configured_flag, connected_flag, running_flag, probe_ok])
        active_effective = any(flag is True for flag in [connected_flag, running_flag, probe_ok])
        if configured_effective:
            configured.append(name)
        if active_effective:
            activeish.append(name)
        details[name] = {
            "configured": configured_effective,
            "connected": connected_flag is True,
            "running": running_flag is True,
            "probe_ok": probe_ok is True,
            "summary": str(raw.get("summary", "") or ""),
        }
    suggested_targets = ["gateway"]
    if configured:
        suggested_targets.append("channels")
    return {
        "configured": configured,
        "active": activeish,
        "details": details,
        "suggested_primary_targets": suggested_targets,
    }


def render_suggested_env(payload: dict[str, object]) -> str:
    suggestions = payload.get("suggested_env", {})
    if not isinstance(suggestions, dict):
        suggestions = {}
    lines = [
        "# Suggested config generated by `openclaw-watchdog detect`",
        "# Review carefully before promoting to a live deployment config.",
        "",
    ]
    sections = [
        (
            "Required / confirm-first",
            [
                "OPENCLAW_CONFIG",
                "OPENCLAW_GATEWAY_SERVICE",
                "OPENCLAW_GATEWAY_PORT",
                "WATCHDOG_PRIMARY_CONVERSATION_TARGETS",
            ],
        ),
        (
            "Recommended defaults",
            [
                "WATCHDOG_STATE_DIR",
                "WATCHDOG_LOG_FILE",
                "WATCHDOG_INCIDENTS_DIR",
                "WATCHDOG_ENABLE_SERVICE_LEVEL_PROBE",
                "WATCHDOG_ENABLE_CONVERSATION_PROBE",
            ],
        ),
        (
            "Safer first rollout",
            [
                "WATCHDOG_ENABLE_DOCTOR_REPAIR",
                "WATCHDOG_ENABLE_SURVIVABILITY_FLOW",
                "WATCHDOG_ENABLE_SURVIVAL_MODE",
            ],
        ),
    ]
    for title, keys in sections:
        lines.append(f"# {title}")
        for key in keys:
            if key not in suggestions:
                continue
            lines.append(f'{key}="{suggestions[key]}"')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_suggested_env(payload: dict[str, object], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_suggested_env(payload), encoding="utf-8")
    return target


def detect_payload(engine: WatchdogEngine) -> dict[str, object]:
    commands = _detect_commands()
    executor_inventory = _executor_inventory(engine, commands)
    status_payload = _run_json(engine, ["openclaw", "status", "--json", "--timeout", str(engine.config.watchdog_service_level_timeout_seconds * 1000)], timeout=engine.config.watchdog_service_level_timeout_seconds + 5) if commands["openclaw"]["available"] else None
    health_payload = _run_json(engine, ["openclaw", "health", "--json"], timeout=engine.config.watchdog_service_level_timeout_seconds + 5) if commands["openclaw"]["available"] else None
    gateway = _gateway_probe(engine, status_payload)
    channels = _channel_probe(health_payload)
    openclaw_config_probe = {
        "path": str(engine.config.openclaw_config),
        "exists": engine.config.openclaw_config.exists(),
    }
    env_file = engine.config.env_file
    suggested_env = {
        "OPENCLAW_CONFIG": str(engine.config.openclaw_config),
        "OPENCLAW_GATEWAY_SERVICE": engine.config.openclaw_gateway_service,
        "OPENCLAW_GATEWAY_PORT": str(gateway.get("detected_port", engine.config.openclaw_gateway_port)),
        "WATCHDOG_STATE_DIR": str(engine.config.watchdog_state_dir),
        "WATCHDOG_LOG_FILE": str(engine.config.watchdog_log_file),
        "WATCHDOG_INCIDENTS_DIR": str(engine.config.watchdog_incidents_dir),
        "WATCHDOG_PRIMARY_CONVERSATION_TARGETS": ",".join(channels["suggested_primary_targets"]),
        # Safer first rollout defaults.
        "WATCHDOG_ENABLE_SERVICE_LEVEL_PROBE": str(bool(engine.config.watchdog_enable_service_level_probe)).lower(),
        "WATCHDOG_ENABLE_CONVERSATION_PROBE": str(bool(engine.config.watchdog_enable_conversation_probe)).lower(),
        "WATCHDOG_ENABLE_DOCTOR_REPAIR": "false",
        "WATCHDOG_ENABLE_SURVIVABILITY_FLOW": "false",
        "WATCHDOG_ENABLE_SURVIVAL_MODE": "false",
    }
    return {
        "detected_at": _now_iso(),
        "repo_root": str(engine.config.repo_root),
        "env_file": str(env_file) if env_file else "",
        "commands": commands,
        "executors": executor_inventory,
        "openclaw": {
            "installed": commands["openclaw"]["available"],
            "config": openclaw_config_probe,
            "status_available": status_payload is not None,
            "health_available": health_payload is not None,
        },
        "gateway": gateway,
        "state_dir": _path_probe(engine.config.watchdog_state_dir),
        "log_file_parent": _path_probe(engine.config.watchdog_log_file.parent),
        "channels": channels,
        "status_summary": {
            "conversation_status": status_payload.get("conversation", {}).get("status", "") if isinstance(status_payload.get("conversation"), dict) else "",
            "channel_summary": status_payload.get("channelSummary", []) if isinstance(status_payload, dict) else [],
        },
        "suggested_env": suggested_env,
    }


def print_detect(payload: dict[str, object]) -> None:
    commands = payload.get("commands", {}) if isinstance(payload.get("commands"), dict) else {}
    executors = payload.get("executors", {}) if isinstance(payload.get("executors"), dict) else {}
    gateway = payload.get("gateway", {}) if isinstance(payload.get("gateway"), dict) else {}
    channels = payload.get("channels", {}) if isinstance(payload.get("channels"), dict) else {}
    state_dir = payload.get("state_dir", {}) if isinstance(payload.get("state_dir"), dict) else {}
    openclaw = payload.get("openclaw", {}) if isinstance(payload.get("openclaw"), dict) else {}

    print(f"detected_at={payload.get('detected_at', '')}")
    print(f"repo_root={payload.get('repo_root', '')}")
    print(f"env_file={payload.get('env_file', '') or 'none'}")
    print(f"openclaw_installed={str(bool(openclaw.get('installed', False))).lower()}")
    config_probe = openclaw.get("config", {}) if isinstance(openclaw.get("config"), dict) else {}
    print(f"openclaw_config={config_probe.get('path', '') or 'none'}")
    print(f"openclaw_config_exists={str(bool(config_probe.get('exists', False))).lower()}")
    print(f"gateway_service={gateway.get('service', '') or 'none'}")
    print(f"gateway_service_active={str(bool(gateway.get('service_active', False))).lower()}")
    print(f"gateway_port={gateway.get('detected_port', gateway.get('configured_port', 0))}")
    print(f"gateway_reachable={str(bool(gateway.get('reachable', False))).lower()}")
    print(f"gateway_url={gateway.get('url', '') or 'none'}")
    print(f"state_dir={state_dir.get('path', '') or 'none'}")
    print(f"state_dir_exists={str(bool(state_dir.get('exists', False))).lower()}")
    print(f"state_dir_writable={str(bool(state_dir.get('writable', False))).lower()}")
    configured = channels.get("configured", []) if isinstance(channels.get("configured"), list) else []
    active = channels.get("active", []) if isinstance(channels.get("active"), list) else []
    print(f"channels_configured={','.join(configured) if configured else 'none'}")
    print(f"channels_active={','.join(active) if active else 'none'}")
    suggested = channels.get("suggested_primary_targets", []) if isinstance(channels.get("suggested_primary_targets"), list) else []
    print(f"suggested_primary_targets={','.join(suggested) if suggested else 'gateway'}")
    available = [name for name, info in commands.items() if isinstance(info, dict) and info.get("available")]
    missing = [name for name, info in commands.items() if isinstance(info, dict) and not info.get("available")]
    rescue_available = [name for name, info in executors.items() if isinstance(info, dict) and info.get("available")]
    rescue_missing = [name for name, info in executors.items() if isinstance(info, dict) and not info.get("available")]
    print(f"commands_available={','.join(available) if available else 'none'}")
    print(f"commands_missing={','.join(missing) if missing else 'none'}")
    print(f"rescue_executors_available={','.join(rescue_available) if rescue_available else 'none'}")
    print(f"rescue_executors_missing={','.join(rescue_missing) if rescue_missing else 'none'}")
    print("next_step=review suggested_env and run preflight once implemented")
