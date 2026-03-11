from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from watchdog_v2.rescue_models import RescuePlan, RescueAction


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

    def test_rolls_back_when_validation_worsens_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / 'openclaw.json'
            config_file.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            config = SimpleNamespace(
                watchdog_rescue_editable_paths=(str(config_file),),
                watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
            )
            engine = FakeEngine(
                [
                    {'minimal_usable_ready': True, 'conversation_ready': True},
                    {'minimal_usable_ready': False, 'conversation_ready': False},
                ]
            )

            from watchdog_v2.rescue_actions import RescueActionExecutor

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
