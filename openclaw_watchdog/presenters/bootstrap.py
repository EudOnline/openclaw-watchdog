from __future__ import annotations

from typing import Any


def render_bootstrap(outcome: Any) -> str:
    payload = outcome.payload
    opencode = payload.get('opencode', {})
    opencode_config = opencode.get('config', {})
    codex = payload.get('codex', {})
    openclaw = payload.get('openclaw', {})
    qq_plugin = payload.get('qq_plugin', {})
    config = payload.get('config', {})
    feishu_runtime = payload.get('feishu_runtime', {})
    placeholders = config.get('placeholders_remaining') or []
    flow = payload.get('flow') or []
    lines = [
        f'state={outcome.state}',
        f'summary={outcome.summary}',
        f"opencode_available={str(bool(opencode.get('available'))).lower()}",
        f"opencode_binary={opencode.get('detected_binary') or 'none'}",
        f"opencode_config_path={opencode_config.get('path', 'none')}",
        f"opencode_model={opencode_config.get('configured_model') or opencode.get('desired_model') or 'none'}",
        f"opencode_watchdog_bin_ready={str(bool(opencode.get('watchdog_bin_available'))).lower()}",
        f"codex_available={str(bool(codex.get('available'))).lower()}",
        f"codex_binary={codex.get('detected_binary') or 'none'}",
        f"openclaw_available={str(bool(openclaw.get('available'))).lower()}",
        f"qq_plugin_installed={str(bool(qq_plugin.get('installed'))).lower()}",
        f"config_path={config.get('path', 'none')}",
        f"feishu_markers_found={str(bool(feishu_runtime.get('found'))).lower()}",
        f"placeholders_remaining={','.join(placeholders) if placeholders else 'none'}",
        f"bootstrap_flow={' -> '.join(flow) if flow else 'none'}",
    ]
    return '\n'.join(lines)
