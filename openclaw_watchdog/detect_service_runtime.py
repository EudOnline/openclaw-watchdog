from __future__ import annotations

from urllib.parse import urlparse

from openclaw_watchdog import service_runtime


def parse_kv_output(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def coerce_bool(value: object) -> bool | None:
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


def gateway_probe(engine, status_payload: dict[str, object] | None) -> dict[str, object]:
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
    info = parse_kv_output(show.output)
    return {
        "service": engine.config.openclaw_gateway_service,
        "show": info,
        "service_active": service_runtime.service_active(engine),
        "service_main_pid": service_runtime.service_main_pid(engine),
        "listener_pids": service_runtime.listener_pids(engine),
        "configured_port": engine.config.openclaw_gateway_port,
        "detected_port": parsed.port if parsed and parsed.port else engine.config.openclaw_gateway_port,
        "url": url,
        "reachable": bool(gateway.get("reachable", False)),
        "misconfigured": bool(gateway.get("misconfigured", False)),
    }


def channel_probe(health_payload: dict[str, object] | None) -> dict[str, object]:
    channels = health_payload.get("channels") if isinstance(health_payload, dict) else {}
    channels = channels if isinstance(channels, dict) else {}
    configured: list[str] = []
    activeish: list[str] = []
    details: dict[str, dict[str, object]] = {}
    for name, raw in sorted(channels.items()):
        if not isinstance(raw, dict):
            continue
        probe = raw.get("probe") if isinstance(raw.get("probe"), dict) else {}
        configured_flag = coerce_bool(raw.get("configured"))
        connected_flag = coerce_bool(raw.get("connected"))
        running_flag = coerce_bool(raw.get("running"))
        probe_ok = coerce_bool(probe.get("ok"))
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
