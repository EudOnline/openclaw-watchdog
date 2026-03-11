from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os


@dataclass
class _Message:
    content: str


@dataclass
class _Choice:
    message: _Message


@dataclass
class _Response:
    choices: list[_Choice]


DEFAULT_RESPONSE = {
    'plan_id': 'rehearsal-default-plan',
    'diagnosis': 'rehearsal default restart',
    'actions': [{'kind': 'restart_service', 'params': {}}],
    'validations': ['minimal_usable_ready'],
    'rollback_strategy': 'auto',
    'risk_level': 'medium',
    'rationale': 'rehearsal shim default response',
}


def completion(**kwargs):
    response_path = Path(os.environ.get('HOME', '.')) / 'litellm-response.json'
    if response_path.exists():
        content = response_path.read_text(encoding='utf-8')
    else:
        content = json.dumps(DEFAULT_RESPONSE, ensure_ascii=False)
    return _Response(choices=[_Choice(message=_Message(content=content))])
