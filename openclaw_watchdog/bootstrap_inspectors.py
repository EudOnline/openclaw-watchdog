from __future__ import annotations

import json
from pathlib import Path
from typing import Any

QQ_PLUGIN_PACKAGE = '@sliverp/qqbot@latest'
OPENCODE_CONFIG_SCHEMA_URL = 'https://opencode.ai/config.json'
QQBOT_APP_ID_PLACEHOLDER = 'REPLACE_WITH_QQBOT_APP_ID'
QQBOT_CLIENT_SECRET_PLACEHOLDER = 'REPLACE_WITH_QQBOT_CLIENT_SECRET'
FEISHU_APP_ID_PLACEHOLDER = 'REPLACE_WITH_FEISHU_APP_ID'
FEISHU_APP_SECRET_PLACEHOLDER = 'REPLACE_WITH_FEISHU_APP_SECRET'
FEISHU_LOG_MARKERS = [
    'feishu_doc: Registered feishu_doc, feishu_app_scopes',
    'feishu_chat: Registered feishu_chat tool',
    'feishu_wiki: Registered feishu_wiki tool',
    'feishu_drive: Registered feishu_drive tool',
    'feishu_perm: Registered feishu_perm tool',
    'feishu_bitable: Registered bitable tools',
    '[MCP] Plugin registered',
]


def inspect_opencode_config(bootstrapper) -> dict[str, Any]:
    path = bootstrapper.config.opencode_bootstrap_config_path.expanduser()
    payload: dict[str, Any] = {
        'path': str(path),
        'exists': path.exists(),
        'configured_model': '',
        'desired_model': bootstrapper.config.opencode_bootstrap_model,
        'ready': False,
        '$schema': OPENCODE_CONFIG_SCHEMA_URL,
    }
    if not path.exists():
        return payload
    try:
        current = load_json_object(bootstrapper, path, label='existing OpenCode config', allow_jsonc=True)
    except bootstrapper.bootstrap_error as exc:
        payload['error'] = str(exc)
        return payload
    configured_model = str(current.get('model', '') or '')
    payload['configured_model'] = configured_model
    payload['ready'] = bool(configured_model)
    return payload


def inspect_qq_plugin(bootstrapper) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'status': 'ready',
        'installed': False,
        'detect_returncode': 0,
        'detect_output': '',
        'package': QQ_PLUGIN_PACKAGE,
    }
    list_result = bootstrapper.run_shell('openclaw plugins list', timeout=60)
    output = list_result.output.lower()
    installed = list_result.returncode == 0 and ('@sliverp/qqbot' in output or 'qqbot' in output)
    payload['installed'] = installed
    payload['detect_returncode'] = list_result.returncode
    payload['detect_output'] = list_result.output.strip()
    if not installed:
        payload['status'] = 'missing'
    return payload


def inspect_default_channel_config(bootstrapper) -> dict[str, Any]:
    path = bootstrapper.config.openclaw_config
    payload: dict[str, Any] = {
        'status': 'ready',
        'path': str(path),
        'exists': path.exists(),
        'placeholders_remaining': [],
        'channels': {},
    }
    if not path.exists():
        payload['status'] = 'missing'
        return payload
    try:
        current = load_json_object(bootstrapper, path, label='existing OpenClaw config', allow_jsonc=False)
    except bootstrapper.bootstrap_error as exc:
        payload['status'] = 'failed'
        payload['error'] = str(exc)
        return payload
    channels = current.get('channels') if isinstance(current.get('channels'), dict) else {}
    qqbot = channels.get('qqbot') if isinstance(channels.get('qqbot'), dict) else {}
    feishu = channels.get('feishu') if isinstance(channels.get('feishu'), dict) else {}
    placeholders: list[str] = []
    qq_app_id = str(qqbot.get('appId', '') or '')
    qq_secret = str(qqbot.get('clientSecret', '') or '')
    if not qq_app_id or qq_app_id == QQBOT_APP_ID_PLACEHOLDER:
        placeholders.append('qqbot.appid')
    if not qq_secret or qq_secret == QQBOT_CLIENT_SECRET_PLACEHOLDER:
        placeholders.append('qqbot.clientSecret')
    feishu_payload = feishu
    if not any(key in feishu for key in ('appId', 'appSecret')):
        accounts = feishu.get('accounts') if isinstance(feishu.get('accounts'), dict) else {}
        feishu_payload = accounts.get('main') if isinstance(accounts.get('main'), dict) else {}
    feishu_app_id = str(feishu_payload.get('appId', '') or '')
    feishu_secret = str(feishu_payload.get('appSecret', '') or '')
    if not feishu_app_id or feishu_app_id == FEISHU_APP_ID_PLACEHOLDER:
        placeholders.append('feishu.appId')
    if not feishu_secret or feishu_secret == FEISHU_APP_SECRET_PLACEHOLDER:
        placeholders.append('feishu.appSecret')
    payload['placeholders_remaining'] = placeholders
    payload['channels'] = {
        'qqbot': {'enabled': bool(qqbot.get('enabled', False))},
        'feishu': {'enabled': bool(feishu.get('enabled', False))},
    }
    return payload


def load_json_object(bootstrapper, path: Path, *, label: str, allow_jsonc: bool) -> dict[str, Any]:
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise bootstrapper.bootstrap_error(f'failed to read {label}: {exc}') from exc
    if allow_jsonc:
        text = normalize_jsonc(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise bootstrapper.bootstrap_error(f'failed to parse {label}: {exc}') from exc
    if not isinstance(payload, dict):
        raise bootstrapper.bootstrap_error(f'{label} must be a JSON object')
    return payload


def normalize_jsonc(text: str) -> str:
    return strip_trailing_commas(strip_jsonc_comments(text))


def strip_jsonc_comments(text: str) -> str:
    result: list[str] = []
    index = 0
    length = len(text)
    in_string = False
    escape = False
    while index < length:
        char = text[index]
        next_char = text[index + 1] if index + 1 < length else ''
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == '/' and next_char == '/':
            index += 2
            while index < length and text[index] not in {'\n', '\r'}:
                index += 1
            continue
        if char == '/' and next_char == '*':
            index += 2
            while index + 1 < length and not (text[index] == '*' and text[index + 1] == '/'):
                index += 1
            index += 2
            continue
        result.append(char)
        index += 1
    return ''.join(result)


def strip_trailing_commas(text: str) -> str:
    result: list[str] = []
    in_string = False
    escape = False
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char in '}]':
            cursor = len(result) - 1
            while cursor >= 0 and result[cursor].isspace():
                cursor -= 1
            if cursor >= 0 and result[cursor] == ',':
                del result[cursor]
            result.append(char)
            index += 1
            continue
        result.append(char)
        index += 1
    return ''.join(result)


def detect_feishu_runtime_markers(bootstrapper) -> dict[str, Any]:
    candidates = log_candidates(bootstrapper)
    payload: dict[str, Any] = {
        'checked': False,
        'found': False,
        'log_file': '',
        'matched_markers': [],
    }
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        payload['checked'] = True
        payload['log_file'] = str(candidate)
        text = read_tail(candidate)
        matched = [marker for marker in FEISHU_LOG_MARKERS if marker in text]
        if matched:
            payload['found'] = True
            payload['matched_markers'] = matched
            return payload
    return payload


def log_candidates(bootstrapper) -> list[Path]:
    candidates: list[Path] = []
    if bootstrapper.config.openclaw_bootstrap_log_file is not None:
        candidates.append(bootstrapper.config.openclaw_bootstrap_log_file)
    config_log = read_logging_file_from_config(bootstrapper)
    if config_log is not None:
        candidates.append(config_log)
    default_dir = Path('/tmp/openclaw')
    if default_dir.exists():
        candidates.extend(sorted(default_dir.glob('openclaw-*.log'), reverse=True)[:3])
    seen: set[Path] = set()
    ordered: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            ordered.append(resolved)
    return ordered


def read_logging_file_from_config(bootstrapper) -> Path | None:
    if not bootstrapper.config.openclaw_config.exists():
        return None
    try:
        current = load_json_object(bootstrapper, bootstrapper.config.openclaw_config, label='existing OpenClaw config', allow_jsonc=False)
    except bootstrapper.bootstrap_error:
        return None
    logging = current.get('logging')
    if not isinstance(logging, dict):
        return None
    file_value = logging.get('file')
    if not isinstance(file_value, str) or not file_value.strip():
        return None
    return Path(file_value).expanduser()


def read_tail(path: Path, max_bytes: int = 262144) -> str:
    with path.open('rb') as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        return handle.read().decode('utf-8', errors='replace')
