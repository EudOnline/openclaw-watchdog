from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ConfigLoadError(ValueError):
    pass


def load_json_object(path: Path, *, label: str, allow_jsonc: bool) -> dict[str, Any]:
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise ConfigLoadError(f'failed to read {label}: {exc}') from exc
    if allow_jsonc:
        text = normalize_jsonc(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(f'failed to parse {label}: {exc}') from exc
    if not isinstance(payload, dict):
        raise ConfigLoadError(f'{label} must be a JSON object')
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


def read_logging_file_from_config(config_path: Path) -> Path | None:
    if not config_path.exists():
        return None
    try:
        current = load_json_object(config_path, label='existing OpenClaw config', allow_jsonc=False)
    except ConfigLoadError:
        return None
    logging = current.get('logging')
    if not isinstance(logging, dict):
        return None
    file_value = logging.get('file')
    if not isinstance(file_value, str) or not file_value.strip():
        return None
    return Path(file_value).expanduser()
