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
    files_changed = payload.get('files_changed') or []
    flow = payload.get('flow') or []
    lines = [
        f'state={outcome.state}',
        f'summary={outcome.summary}',
        f"opencode_installed={str(bool(opencode.get('installed'))).lower()}",
        f"opencode_install_planned={str(bool(opencode.get('would_install'))).lower()}",
        f"opencode_config_path={opencode_config.get('path', 'none')}",
        f"opencode_model={opencode_config.get('configured_model') or opencode.get('desired_model') or 'none'}",
        f"opencode_config_changed={str(bool(opencode_config.get('changed'))).lower()}",
        f"opencode_backup_path={opencode_config.get('backup_path') or 'none'}",
        f"opencode_watchdog_bin_ready={str(bool(opencode.get('watchdog_bin_available'))).lower()}",
        f"codex_available={str(bool(codex.get('available'))).lower()}",
        f"codex_binary={codex.get('detected_binary') or 'none'}",
        f"openclaw_installed={str(bool(openclaw.get('installed'))).lower()}",
        f"confirmation_required={str(bool(openclaw.get('confirmation_required'))).lower()}",
        f"qq_plugin_installed={str(bool(qq_plugin.get('installed'))).lower()}",
        f"config_path={config.get('path', 'none')}",
        f"config_changed={str(bool(config.get('changed'))).lower()}",
        f"backup_path={config.get('backup_path') or 'none'}",
        f"feishu_markers_found={str(bool(feishu_runtime.get('found'))).lower()}",
        f"placeholders_remaining={','.join(placeholders) if placeholders else 'none'}",
        f"files_changed={','.join(files_changed) if files_changed else 'none'}",
        f"bootstrap_flow={' -> '.join(flow) if flow else 'none'}",
    ]
    return '\n'.join(lines)
