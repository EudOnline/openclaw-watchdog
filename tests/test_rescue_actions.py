from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openclaw_watchdog.rescue_models import RescueAction, RescuePlan


class FakeEngine:
    def __init__(self, probes: list[dict[str, object]], *, config=None) -> None:
        self._probes = list(probes)
        self.restarts = 0
        self.config = config

    def restart_service(self) -> bool:
        self.restarts += 1
        return True


class RescueActionTests(unittest.TestCase):
    def _build_executor(self, config_file: Path, probes: list[dict[str, object]] | None = None):
        from openclaw_watchdog.rescue_actions import RescueActionExecutor

        config = SimpleNamespace(
            watchdog_rescue_editable_paths=(str(config_file),),
            watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
            watchdog_guard_manifest_file=config_file.parent / 'guard.json',
            openclaw_config=config_file,
            env_file=None,
            watchdog_survival_config_file=config_file.parent / 'survival.json',
            watchdog_protected_paths=(),
        )
        engine = FakeEngine(probes or [], config=config)
        return RescueActionExecutor(config=config, engine=engine)

    def _apply_plan(self, executor, plan):
        def _next_probe(engine, *, include_doctor: bool, apply_grace: bool) -> dict[str, object]:
            probes = getattr(engine, '_probes', [])
            if probes:
                return dict(probes.pop(0))
            return {}

        with patch('openclaw_watchdog.rescue_actions.health_ops.live_probe', side_effect=_next_probe):
            return executor.apply_plan(plan)

    def test_probe_uses_health_module_directly_when_engine_live_probe_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            executor = self._build_executor(config_file, probes=[{'minimal_usable_ready': True}])

            with patch('openclaw_watchdog.rescue_actions.health_ops.live_probe', return_value={'minimal_usable_ready': True}) as probe_mock:
                payload = executor._probe(include_doctor=False)

        self.assertEqual(payload, {'minimal_usable_ready': True})
        probe_mock.assert_called_once_with(executor.engine, include_doctor=False, apply_grace=False)

    def test_rejects_writes_outside_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            config = SimpleNamespace(
                watchdog_rescue_editable_paths=(str(config_file),),
                watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
            )
            engine = FakeEngine([{'minimal_usable_ready': True}, {'minimal_usable_ready': True}])

            from openclaw_watchdog.rescue_actions import RescueActionExecutor

            executor = RescueActionExecutor(config=config, engine=engine)
            with self.assertRaises(PermissionError):
                executor.update_openclaw_config('/tmp/not-allowed.json', 'channels.qqbot.enabled', False)

    def test_update_openclaw_config_preserves_original_file_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            original_text = config_file.read_text(encoding='utf-8')
            executor = self._build_executor(config_file)

            with patch('openclaw_watchdog.file_ops.os.replace', side_effect=OSError('replace failed')):
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

    def test_update_openclaw_config_allows_descendant_key_when_namespace_prefix_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            config = SimpleNamespace(
                watchdog_rescue_editable_paths=(str(config_file),),
                watchdog_rescue_editable_keys=('channels',),
            )
            engine = FakeEngine([{'minimal_usable_ready': True}, {'minimal_usable_ready': True}])

            from openclaw_watchdog.rescue_actions import RescueActionExecutor

            executor = RescueActionExecutor(config=config, engine=engine)

            executor.update_openclaw_config(str(config_file), 'channels.qqbot.enabled', False)

            payload = json.loads(config_file.read_text(encoding='utf-8'))
            self.assertFalse(payload['channels']['qqbot']['enabled'])

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

            from openclaw_watchdog.rescue_actions import RescueActionExecutor

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

            result = self._apply_plan(executor, plan)

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

            from openclaw_watchdog.rescue_actions import RescueActionExecutor

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

            result = self._apply_plan(executor, plan)

            self.assertEqual(result.status, 'rolled-back')
            restored = json.loads(config_file.read_text(encoding='utf-8'))
            self.assertTrue(restored['channels']['qqbot']['enabled'])

    def test_enter_survival_mode_action_uses_transition_owner_when_engine_wrapper_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            executor = self._build_executor(
                config_file,
                probes=[
                    {'minimal_usable_ready': True, 'conversation_ready': True},
                    {'minimal_usable_ready': True, 'conversation_ready': True},
                ],
            )
            plan = RescuePlan(
                plan_id='plan-survival-fallback',
                diagnosis='enter survival mode through owner runtime',
                actions=[RescueAction(kind='enter_survival_mode', params={})],
                validations=['minimal_usable_ready'],
            )

            with patch(
                'openclaw_watchdog.rescue_actions.survival_transition_runtime.enter_survival_mode',
                return_value={'applied': True},
            ) as survival_mock:
                result = self._apply_plan(executor, plan)

        self.assertEqual(result.status, 'applied')
        survival_mock.assert_called_once_with(executor.engine, reason='rescue-plan')

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

            from openclaw_watchdog.rescue_actions import RescueActionExecutor

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

            result = self._apply_plan(executor, plan)

            self.assertEqual(result.status, 'rolled-back')
            self.assertTrue(result.rollback_performed)
            restored = json.loads(config_file.read_text(encoding='utf-8'))
            self.assertTrue(restored['channels']['qqbot']['enabled'])

    def test_guard_manifest_records_controlled_rescue_config_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            executor = self._build_executor(
                config_file,
                probes=[
                    {'minimal_usable_ready': True, 'conversation_ready': True},
                    {'minimal_usable_ready': True, 'conversation_ready': True},
                ],
            )
            plan = RescuePlan(
                plan_id='plan-guard-event',
                diagnosis='record guarded config update',
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

            result = self._apply_plan(executor, plan)

            from openclaw_watchdog import last_good_runtime

            self.assertEqual(result.status, 'applied')
            guard_status = last_good_runtime.guard_status(executor.config)
            self.assertEqual(guard_status['guard_last_operation'], 'rescue-update-openclaw-config')
            self.assertIn('after', guard_status['guard_last_summary'])

    def test_apply_plan_uses_runtime_modules_directly_when_engine_wrappers_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')

            from openclaw_watchdog.rescue_actions import RescueActionExecutor
            from openclaw_watchdog import rescue_actions

            config = SimpleNamespace(
                watchdog_rescue_editable_paths=(str(config_file),),
                watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
            )
            engine = SimpleNamespace(
                _probes=[
                    {'minimal_usable_ready': True, 'conversation_ready': True, 'config_invalid': False},
                    {'minimal_usable_ready': True, 'conversation_ready': True, 'config_invalid': False},
                ],
                config=config,
            )
            executor = RescueActionExecutor(config=config, engine=engine)
            plan = RescuePlan(
                plan_id='plan-runtime-owners',
                diagnosis='use direct runtime owners',
                actions=[
                    RescueAction(kind='restart_service', params={}),
                    RescueAction(kind='restore_last_good', params={}),
                    RescueAction(kind='run_doctor', params={}),
                ],
                validations=['minimal_usable_ready'],
            )

            restart_mock = Mock(return_value=True)
            restore_mock = Mock(return_value=True)
            doctor_mock = Mock(return_value=(0, 'doctor ok'))
            with patch.object(rescue_actions, 'repair_action_runtime', SimpleNamespace(restart_service=restart_mock), create=True):
                with patch.object(rescue_actions, 'rollback_runtime', SimpleNamespace(restore_last_good=restore_mock), create=True):
                    with patch.object(rescue_actions, 'doctor_runtime', SimpleNamespace(run_doctor=doctor_mock), create=True):
                        result = self._apply_plan(executor, plan)

        self.assertEqual(result.status, 'applied')
        restart_mock.assert_called_once_with(engine)
        restore_mock.assert_called_once_with(engine, reason='rescue-plan')
        doctor_mock.assert_called_once_with(engine)


if __name__ == '__main__':
    unittest.main()
