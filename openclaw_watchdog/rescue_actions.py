from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openclaw_watchdog import doctor_runtime
from openclaw_watchdog import file_ops
from openclaw_watchdog import health as health_ops
from openclaw_watchdog import last_good_runtime
from openclaw_watchdog import repair_action_runtime
from openclaw_watchdog import rescue_policy
from openclaw_watchdog import rollback_runtime
from openclaw_watchdog.rescue_models import RescuePlan, RescueResult


class RescueActionExecutor:
    def __init__(self, *, config, engine) -> None:
        self.config = config
        self.engine = engine

    def _expanded_allowed_paths(self) -> tuple[Path, ...]:
        return tuple(Path(raw).expanduser() for raw in rescue_policy.editable_paths(self.config))

    def _allowed_keys(self) -> tuple[str, ...]:
        return tuple(str(item) for item in rescue_policy.editable_keys(self.config))

    def _ensure_path_allowed(self, target: Path) -> None:
        if rescue_policy.path_allowed(target, [str(item) for item in self._expanded_allowed_paths()]):
            return
        raise PermissionError(f'rescue write not allowed for {target.expanduser().resolve(strict=False)}')

    def _ensure_key_allowed(self, dotted_path: str) -> None:
        if rescue_policy.key_allowed(dotted_path, list(self._allowed_keys())):
            return
        raise PermissionError(f'rescue key not allowed: {dotted_path}')

    def _set_json_path(self, payload: dict[str, Any], dotted_path: str, value: Any) -> Any:
        parts = [part for part in dotted_path.split('.') if part]
        if not parts:
            raise ValueError('config path must not be empty')
        cursor: dict[str, Any] = payload
        for part in parts[:-1]:
            current = cursor.get(part)
            if current is None:
                current = {}
                cursor[part] = current
            if not isinstance(current, dict):
                raise ValueError(f'config path segment is not an object: {part}')
            cursor = current
        previous_value = cursor.get(parts[-1])
        cursor[parts[-1]] = value
        return previous_value

    def _restore_snapshot(self, target: Path, snapshot: str | None) -> None:
        if snapshot is None:
            target.unlink(missing_ok=True)
            return
        file_ops.write_text_atomic(target, snapshot, encoding='utf-8')

    def _needs_config_validation(self, validations: list[str]) -> bool:
        for validation in validations:
            key = validation.strip().lower()
            if key in {'config_invalid', 'config_valid', 'config_reload_success'}:
                return True
        return False

    def _guarding_available(self) -> bool:
        required = (
            'watchdog_guard_manifest_file',
            'openclaw_config',
            'watchdog_survival_config_file',
            'watchdog_protected_paths',
        )
        return all(hasattr(self.config, name) for name in required)

    def _protected_paths_snapshot(self) -> list[dict[str, object]] | None:
        if not self._guarding_available():
            return None
        return last_good_runtime.protected_paths_snapshot(self.config)

    def _record_guard_event(
        self,
        *,
        phase: str,
        before: list[dict[str, object]] | None,
        after: list[dict[str, object]] | None = None,
        validation: str = '',
        context: dict[str, object] | None = None,
    ) -> None:
        if not self._guarding_available():
            return
        last_good_runtime.record_guard_event(
            self.config,
            operation='rescue-update-openclaw-config',
            phase=phase,
            before=before,
            after=after,
            validation=validation,
            context=context,
        )

    def update_openclaw_config(self, file: str, dotted_path: str, value: Any) -> Any:
        target = Path(file).expanduser()
        self._ensure_path_allowed(target)
        self._ensure_key_allowed(dotted_path)
        current: dict[str, Any] = {}
        if target.exists():
            current_payload = json.loads(target.read_text(encoding='utf-8'))
            if not isinstance(current_payload, dict):
                raise ValueError('OpenClaw config root must be a JSON object')
            current = current_payload
        previous_value = self._set_json_path(current, dotted_path, value)
        file_ops.write_json_atomic(target, current)
        return previous_value

    def _probe(self, *, include_doctor: bool) -> dict[str, Any]:
        return dict(health_ops.live_probe(self.engine, include_doctor=include_doctor, apply_grace=False))

    def _validation_worsened(self, before: dict[str, Any], after: dict[str, Any], validations: list[str]) -> bool:
        for validation in validations:
            key = validation.strip().lower()
            if not key:
                continue
            if key == 'minimal_usable_ready':
                if bool(before.get('minimal_usable_ready', False)) and not bool(after.get('minimal_usable_ready', False)):
                    return True
            elif key == 'conversation_ready':
                if bool(before.get('conversation_ready', False)) and not bool(after.get('conversation_ready', False)):
                    return True
            elif key == 'service_layer_healthy':
                if bool(before.get('service_layer_healthy', False)) and not bool(after.get('service_layer_healthy', False)):
                    return True
            elif key in {'config_invalid', 'config_valid', 'config_reload_success'}:
                if not bool(before.get('config_invalid', False)) and bool(after.get('config_invalid', False)):
                    return True
        return False

    def apply_plan(self, plan: RescuePlan) -> RescueResult:
        needs_config_validation = self._needs_config_validation(plan.validations)
        before_probe = self._probe(include_doctor=needs_config_validation)
        snapshots: dict[Path, str | None] = {}
        mutation_before = None
        mutation_context = {
            'plan_id': plan.plan_id,
            'validations': list(plan.validations),
        }
        try:
            for action in plan.actions:
                if action.kind == 'update_openclaw_config':
                    if mutation_before is None:
                        mutation_before = self._protected_paths_snapshot()
                        self._record_guard_event(phase='before', before=mutation_before, context=mutation_context)
                    target = Path(str(action.params.get('file', '') or '')).expanduser()
                    snapshots.setdefault(target, target.read_text(encoding='utf-8') if target.exists() else None)
                    self.update_openclaw_config(
                        str(target),
                        str(action.params.get('path', '') or ''),
                        action.params.get('value'),
                    )
                elif action.kind == 'restart_service':
                    repair_action_runtime.restart_service(self.engine)
                elif action.kind == 'restore_last_good':
                    rollback_runtime.restore_last_good(self.engine, reason='rescue-plan')
                elif action.kind == 'enter_survival_mode' and hasattr(self.engine, 'enter_survival_mode'):
                    self.engine.enter_survival_mode(reason='rescue-plan')
                elif action.kind == 'run_doctor':
                    doctor_runtime.run_doctor(self.engine)

            after_probe = self._probe(include_doctor=needs_config_validation)
            if self._validation_worsened(before_probe, after_probe, plan.validations):
                for target, snapshot in snapshots.items():
                    self._restore_snapshot(target, snapshot)
                mutation_after = self._protected_paths_snapshot()
                if mutation_before is not None:
                    self._record_guard_event(
                        phase='after',
                        before=mutation_before,
                        after=mutation_after,
                        validation='rolled-back',
                        context=mutation_context,
                    )
                return RescueResult(
                    status='rolled-back',
                    executor='local-actions',
                    plan_id=plan.plan_id,
                    rollback_performed=bool(snapshots),
                    details={'before': before_probe, 'after': after_probe},
                )
            mutation_after = self._protected_paths_snapshot()
            if mutation_before is not None:
                self._record_guard_event(
                    phase='after',
                    before=mutation_before,
                    after=mutation_after,
                    validation='applied',
                    context=mutation_context,
                )
            return RescueResult(
                status='applied',
                executor='local-actions',
                plan_id=plan.plan_id,
                rollback_performed=False,
                details={'before': before_probe, 'after': after_probe},
            )
        except Exception:
            for target, snapshot in snapshots.items():
                self._restore_snapshot(target, snapshot)
            mutation_after = self._protected_paths_snapshot()
            if mutation_before is not None:
                self._record_guard_event(
                    phase='after',
                    before=mutation_before,
                    after=mutation_after,
                    validation='exception-rolled-back',
                    context=mutation_context,
                )
            raise
