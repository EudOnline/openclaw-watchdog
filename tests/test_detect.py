from __future__ import annotations

from types import SimpleNamespace
import unittest

from openclaw_watchdog.detect import _gateway_probe
from openclaw_watchdog.runtime import CommandResult


def _result(args: list[str], *, returncode: int = 0, stdout: str = '', stderr: str = '') -> CommandResult:
    return CommandResult(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


class DetectEngineDouble:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            openclaw_gateway_service='openclaw-gateway.service',
            openclaw_gateway_port=5700,
        )
        self._responses: dict[tuple[str, ...], CommandResult] = {}

    def run_command(self, args: list[str], **kwargs) -> CommandResult:
        return self._responses.get(tuple(args), _result(args, returncode=1))


class DetectTests(unittest.TestCase):
    def test_gateway_probe_does_not_require_engine_service_wrappers(self) -> None:
        engine = DetectEngineDouble()
        engine._responses[
            (
                'systemctl',
                '--user',
                'show',
                '-p',
                'LoadState,UnitFileState,FragmentPath,ActiveState,SubState',
                'openclaw-gateway.service',
            )
        ] = _result(
            ['systemctl'],
            stdout='LoadState=loaded\nUnitFileState=enabled\nActiveState=active\nSubState=running\n',
        )
        engine._responses[
            ('systemctl', '--user', 'is-active', '--quiet', 'openclaw-gateway.service')
        ] = _result(['systemctl'], returncode=0)
        engine._responses[
            ('systemctl', '--user', 'show', '-p', 'MainPID', '--value', 'openclaw-gateway.service')
        ] = _result(['systemctl'], stdout='123\n')
        engine._responses[('ss', '-tlnp')] = _result(
            ['ss', '-tlnp'],
            stdout='LISTEN 0 128 *:5700 *:* users:(("node",pid=123,fd=21))',
        )

        payload = _gateway_probe(
            engine,
            {
                'gateway': {
                    'url': 'http://127.0.0.1:5700',
                    'reachable': True,
                    'misconfigured': False,
                }
            },
        )

        self.assertEqual(payload['service'], 'openclaw-gateway.service')
        self.assertEqual(payload['show']['ActiveState'], 'active')
        self.assertTrue(payload['service_active'])
        self.assertEqual(payload['service_main_pid'], '123')
        self.assertEqual(payload['listener_pids'], ['123'])
        self.assertEqual(payload['configured_port'], 5700)
        self.assertEqual(payload['detected_port'], 5700)
        self.assertTrue(payload['reachable'])
        self.assertFalse(payload['misconfigured'])


if __name__ == '__main__':
    unittest.main()
