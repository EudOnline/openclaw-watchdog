from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, Any

from openclaw_watchdog.rescue_models import ALLOWED_ACTIONS, RescueContext, RescuePlan
from openclaw_watchdog.runtime import CommandResult


class RescueAgentAdapter(Protocol):
    name: str

    def is_available(self, context: RescueContext) -> bool: ...

    def propose_plan(self, context: RescueContext) -> RescuePlan | None: ...


Runner = Callable[..., CommandResult]
ALLOWED_PLAN_TOP_LEVEL_KEYS = frozenset(
    {
        'plan_id',
        'diagnosis',
        'actions',
        'validations',
        'rollback_strategy',
        'risk_level',
        'rationale',
    }
)


@dataclass
class StaticCommandAdapter:
    name: str
    command: str
    available: bool = False

    def is_available(self, context: RescueContext) -> bool:
        return self.available

    def propose_plan(self, context: RescueContext) -> RescuePlan | None:
        return None


@dataclass
class StructuredCliAdapter:
    name: str
    command: str
    prompt_args: tuple[str, ...] = field(default_factory=tuple)
    available: bool = False
    runner: Runner | None = None
    timeout_seconds: int = 120
    cwd: Path | None = None
    provider_label: str = ''

    def is_available(self, context: RescueContext) -> bool:
        return self.available

    def build_payload(self, context: RescueContext) -> dict[str, Any]:
        return {
            'incident_id': context.incident_id,
            'health_level': context.health_level,
            'conversation_status': context.conversation_status,
            'available_executors': list(context.available_executors),
            'editable_paths': list(context.editable_paths),
            'editable_keys': list(context.editable_keys),
            'probe': dict(context.probe),
            'metadata': dict(context.metadata),
        }

    def build_prompt(self, context: RescueContext) -> str:
        payload = self.build_payload(context)
        return (
            f'You are the {self.provider_label or self.name} OpenClaw rescue planner. '
            'Return exactly one JSON object and no prose. '
            'Never emit shell commands, scripts, or arbitrary command strings. '
            f'Allowed action kinds: {", ".join(ALLOWED_ACTIONS)}. '
            'Use only these top-level keys: plan_id, diagnosis, actions, validations, rollback_strategy, risk_level, rationale. '
            'If no safe plan exists, return a JSON object with actions as an empty list. '
            'Context:\n'
            + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )

    def command_args(self, prompt: str) -> list[str]:
        return [self.command, *self.prompt_args, prompt]

    def _validate_plan_payload(self, payload: dict[str, Any]) -> None:
        unknown_keys = sorted(set(payload) - ALLOWED_PLAN_TOP_LEVEL_KEYS)
        if unknown_keys:
            raise ValueError(f'{self.name} returned unexpected top-level keys: {", ".join(unknown_keys)}')
        if 'actions' not in payload:
            raise ValueError(f'{self.name} returned a plan without actions')
        if 'validations' not in payload:
            raise ValueError(f'{self.name} returned a plan without validations')
        if not str(payload.get('plan_id', '') or '').strip():
            raise ValueError(f'{self.name} returned an empty plan_id')
        if not str(payload.get('diagnosis', '') or '').strip():
            raise ValueError(f'{self.name} returned an empty diagnosis')
        actions = payload.get('actions', [])
        if not isinstance(actions, list):
            raise ValueError(f'{self.name} returned non-list actions')
        validations = payload.get('validations', [])
        if 'validations' in payload and not isinstance(validations, list):
            raise ValueError(f'{self.name} returned non-list validations')
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                raise ValueError(f'{self.name} returned non-object action at index {index}')
            if not str(action.get('kind', '') or '').strip():
                raise ValueError(f'{self.name} returned an action without kind at index {index}')
            params = action.get('params', {})
            if 'params' in action and not isinstance(params, dict):
                raise ValueError(f'{self.name} returned non-dict params for action {index}')

    def _extract_json_candidates(self, text: str) -> list[Any]:
        candidates: list[Any] = []
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char not in '{[':
                continue
            try:
                payload, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            candidates.append(payload)
        return candidates

    def _find_plan_payload(self, value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            if 'shell' in value:
                return value
            for key in ('response', 'result', 'content', 'text', 'message'):
                nested = value.get(key)
                found = self._find_plan_payload(nested)
                if found is not None:
                    return found
            if set(value).intersection(ALLOWED_PLAN_TOP_LEVEL_KEYS):
                return value
            for nested in value.values():
                found = self._find_plan_payload(nested)
                if found is not None:
                    return found
            return None
        if isinstance(value, list):
            for item in value:
                found = self._find_plan_payload(item)
                if found is not None:
                    return found
            return None
        if isinstance(value, str):
            for candidate in self._extract_json_candidates(value):
                found = self._find_plan_payload(candidate)
                if found is not None:
                    return found
        return None

    def propose_plan(self, context: RescueContext) -> RescuePlan | None:
        if not self.is_available(context):
            raise ValueError(f'{self.name} is not available')
        if self.runner is None:
            raise ValueError(f'{self.name} runner is not configured')
        result = self.runner(
            self.command_args(self.build_prompt(context)),
            timeout=self.timeout_seconds,
            cwd=self.cwd,
            merge_stderr=True,
        )
        if result.returncode != 0:
            raise ValueError(f'{self.name} command failed: rc={result.returncode} output={result.output.strip()}')
        payloads: list[dict[str, Any]] = []
        for candidate in self._extract_json_candidates(result.output):
            payload = self._find_plan_payload(candidate)
            if isinstance(payload, dict):
                payloads.append(payload)
        if not payloads:
            raise ValueError(f'{self.name} did not return a structured rescue plan')
        validation_error: ValueError | None = None
        for payload in reversed(payloads):
            try:
                if 'shell' in payload:
                    raise ValueError(f'{self.name} returned forbidden shell payload')
                self._validate_plan_payload(payload)
                plan = RescuePlan.from_dict(payload)
            except ValueError as exc:
                validation_error = exc
                continue
            if plan.actions:
                return plan
        if validation_error is not None:
            raise validation_error
        return None
