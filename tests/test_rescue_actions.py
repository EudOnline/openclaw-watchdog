from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from watchdog_v2.rescue_models import RescueAction, RescuePlan


class FakeEngine:
    def __init__(self, probes: list[dict[str, object]]) -> None:
        self._probes = list(probes)
        self.restarts = 0

    def live_probe(self, *, include_doctor: bool, apply_grace: bool) -> dict[str, object]:
        if self._probes:
            return dict(self._probes.pop(0))
        return {}

    def restart_service(self) -> bool:
        self.restarts += 1
        return True


class RescueActionTests(unittest.TestCase):
    def _build_executor(self, config_file: Path, probes: list[dict[str, object]] | None = None):
        from watchdog_v2.rescue_actions import RescueActionExecutor

        config = SimpleNamespace(
            watchdog_rescue_editable_paths=(str(config_file),),
            watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
        )
        engine = FakeEngine(probes or [])
        return RescueActionExecutor(config=config, engine=engine)

    def test_rejects_writes_outside_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            config = SimpleNamespace(
                watchdog_rescue_editable_paths=(str(config_file),),
                watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
            )
            engine = FakeEngine([{'minimal_usable_ready': True}, {'minimal_usable_ready': True}])

            from watchdog_v2.rescue_actions import RescueActionExecutor

            executor = RescueActionExecutor(config=config, engine=engine)
            with self.assertRaises(PermissionError):
                executor.update_openclaw_config('/tmp/not-allowed.json', 'channels.qqbot.enabled', False)

    def test_update_openclaw_config_preserves_original_file_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            original_text = config_file.read_text(encoding='utf-8')
            executor = self._build_executor(config_file)

            with patch('watchdog_v2.file_ops.os.replace', side_effect=OSError('replace failed')):
                with self.assertRaises(OSError):
                    executor.update_openclaw_config(str(config_file), 'channels.qqbot.enabled', False)

            self.assertEqual(config_file.read_text(encoding='utf-8'), original_text)
            payload = json.loads(config_file.read_text(encoding='utf-8'))
            self.assertTrue(payload['channels']['qqbot']['enabled'])

    def test_update_openclaw_config_cleans_up_temp_file_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            executor = self._build_executor(config_file)

            executor.update_openclaw_config(str(config_file), 'channels.qqbot.enabled', False)

            payload = json.loads(config_file.read_text(encoding='utf-8'))
            self.assertFalse(payload['channels']['qqbot']['enabled'])
            self.assertEqual(list(config_file.parent.glob(f'.{config_file.name}.tmp-*')), [])

    def test_rolls_back_when_service_layer_degrades_after_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            config = SimpleNamespace(
                watchdog_rescue_editable_paths=(str(config_file),),
                watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
            )
            engine = FakeEngine(
                [
                    {'service_layer_healthy': True, 'minimal_usable_ready': True, 'conversation_ready': True},
                    {'service_layer_healthy': False, 'minimal_usable_ready': True, 'conversation_ready': True},
                ]
            )

            from watchdog_v2.rescue_actions import RescueActionExecutor

            executor = RescueActionExecutor(config=config, engine=engine)
            plan = RescuePlan(
                plan_id='plan-service-gate',
                diagnosis='test service gate rollback',
                actions=[
                    RescueAction(
                        kind='update_openclaw_config',
                        params={
                            'file': str(config_file),
                            'path': 'channels.qqbot.enabled',
                            'value': False,
                        },
                    )
                ],
                validations=['service_layer_healthy'],
            )

            result = executor.apply_plan(plan)

            self.assertEqual(result.status, 'rolled-back')
            restored = json.loads(config_file.read_text(encoding='utf-8'))
            self.assertTrue(restored['channels']['qqbot']['enabled'])

    def test_rolls_back_when_config_validation_fails_after_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            config = SimpleNamespace(
                watchdog_rescue_editable_paths=(str(config_file),),
                watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
            )
            engine = FakeEngine(
                [
                    {'config_invalid': False, 'minimal_usable_ready': True, 'conversation_ready': True},
                    {'config_invalid': True, 'minimal_usable_ready': True, 'conversation_ready': True},
                ]
            )

            from watchdog_v2.rescue_actions import RescueActionExecutor

            executor = RescueActionExecutor(config=config, engine=engine)
            plan = RescuePlan(
                plan_id='plan-config-gate',
                diagnosis='test config gate rollback',
                actions=[
                    RescueAction(
                        kind='update_openclaw_config',
                        params={
                            'file': str(config_file),
                            'path': 'channels.qqbot.enabled',
                            'value': False,
                        },
                    )
                ],
                validations=['config_invalid'],
            )

            result = executor.apply_plan(plan)

            self.assertEqual(result.status, 'rolled-back')
            restored = json.loads(config_file.read_text(encoding='utf-8'))
            self.assertTrue(restored['channels']['qqbot']['enabled'])

    def test_update_openclaw_config_rejects_non_object_json_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps(['not-an-object']), encoding='utf-8')
            executor = self._build_executor(config_file)

            with self.assertRaisesRegex(ValueError, 'JSON object'):
                executor.update_openclaw_config(str(config_file), 'channels.qqbot.enabled', False)

    def test_rolls_back_when_validation_worsens_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            engine = FakeEngine(
                [
                    {'minimal_usable_ready': True, 'conversation_ready': True},
                    {'minimal_usable_ready': False, 'conversation_ready': False},
                ]
            )

            from watchdog_v2.rescue_actions import RescueActionExecutor

            config = SimpleNamespace(
                watchdog_rescue_editable_paths=(str(config_file),),
                watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
            )
            executor = RescueActionExecutor(config=config, engine=engine)
            plan = RescuePlan(
                plan_id='plan-rollback',
                diagnosis='disable qqbot to test rollback',
                actions=[
                    RescueAction(
                        kind='update_openclaw_config',
                        params={
                            'file': str(config_file),
                            'path': 'channels.qqbot.enabled',
                            'value': False,
                        },
                    )
                ],
                validations=['minimal_usable_ready'],
            )

            result = executor.apply_plan(plan)

            self.assertEqual(result.status, 'rolled-back')
            self.assertTrue(result.rollback_performed)
            restored = json.loads(config_file.read_text(encoding='utf-8'))
            self.assertTrue(restored['channels']['qqbot']['enabled'])


if __name__ == '__main__':
    unittest.main()
