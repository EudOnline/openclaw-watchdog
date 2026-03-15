from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
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
    def test_gateway_probe_delegates_to_service_runtime_owner(self) -> None:
        from openclaw_watchdog import detect

        engine = DetectEngineDouble()
        status_payload = {'gateway': {'url': 'http://127.0.0.1:5700'}}
        gateway_mock = unittest.mock.Mock(return_value={'service': 'delegated'})

        with unittest.mock.patch.object(
            detect,
            'detect_service_runtime',
            SimpleNamespace(gateway_probe=gateway_mock),
            create=True,
        ):
            payload = detect._gateway_probe(engine, status_payload)

        self.assertEqual(payload, {'service': 'delegated'})
        gateway_mock.assert_called_once_with(engine, status_payload)

    def test_executor_inventory_and_payload_delegate_to_owner_runtimes(self) -> None:
        from openclaw_watchdog import detect

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_litellm_enabled=False,
                    watchdog_litellm_model='',
                    watchdog_service_level_timeout_seconds=1,
                    openclaw_config=root / 'openclaw.json',
                    env_file=None,
                    repo_root=root,
                    openclaw_gateway_service='openclaw-gateway.service',
                    openclaw_gateway_port=5700,
                    watchdog_state_dir=root / 'state',
                    watchdog_log_file=root / 'state' / 'watchdog.log',
                    watchdog_incidents_dir=root / 'incidents',
                    watchdog_enable_service_level_probe=False,
                    watchdog_enable_conversation_probe=False,
                ),
                run_command=lambda args, **kwargs: _result(args, returncode=1),
            )
            commands = {'codex': {'available': True, 'path': '/usr/bin/codex'}}
            commands_mock = unittest.mock.Mock(return_value=commands)
            inventory_mock = unittest.mock.Mock(return_value={'codex': {'available': True}})
            payload_mock = unittest.mock.Mock(return_value={'detected_at': 'delegated'})

            with unittest.mock.patch.object(
                detect,
                'detect_executor_runtime',
                SimpleNamespace(detect_commands=commands_mock, executor_inventory=inventory_mock),
                create=True,
            ):
                with unittest.mock.patch.object(
                    detect,
                    'detect_health_runtime',
                    SimpleNamespace(detect_payload=payload_mock),
                    create=True,
                ):
                    detected_commands = detect._detect_commands()
                    executors = detect._executor_inventory(engine, commands)
                    payload = detect.detect_payload(engine)

        self.assertEqual(detected_commands, commands)
        self.assertEqual(executors, {'codex': {'available': True}})
        self.assertEqual(payload, {'detected_at': 'delegated'})
        commands_mock.assert_called_once_with()
        inventory_mock.assert_called_once_with(engine, commands)
        payload_mock.assert_called_once_with(engine)

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

    def test_gateway_probe_prefers_platform_supervisor_description_when_present(self) -> None:
        supervisor = SimpleNamespace(
            describe_service=unittest.mock.Mock(return_value={'ActiveState': 'active', 'SubState': 'running'}),
            service_active=unittest.mock.Mock(return_value=True),
            service_main_pid=unittest.mock.Mock(return_value='123'),
        )
        listeners = SimpleNamespace(
            listener_pids=unittest.mock.Mock(return_value=['123']),
        )
        engine = SimpleNamespace(
            config=SimpleNamespace(
                openclaw_gateway_service='openclaw-gateway.service',
                openclaw_gateway_port=5700,
            ),
            platform=SimpleNamespace(supervisor=supervisor, listeners=listeners),
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

        self.assertEqual(payload['show'], {'ActiveState': 'active', 'SubState': 'running'})
        self.assertTrue(payload['service_active'])
        self.assertEqual(payload['service_main_pid'], '123')
        self.assertEqual(payload['listener_pids'], ['123'])
        supervisor.describe_service.assert_called_once_with(engine)

    def test_gateway_probe_normalizes_string_gateway_flags(self) -> None:
        supervisor = SimpleNamespace(
            describe_service=unittest.mock.Mock(return_value={'ActiveState': 'active'}),
            service_active=unittest.mock.Mock(return_value=True),
            service_main_pid=unittest.mock.Mock(return_value='123'),
        )
        listeners = SimpleNamespace(listener_pids=unittest.mock.Mock(return_value=['123']))
        engine = SimpleNamespace(
            config=SimpleNamespace(
                openclaw_gateway_service='openclaw-gateway.service',
                openclaw_gateway_port=5700,
            ),
            platform=SimpleNamespace(supervisor=supervisor, listeners=listeners),
        )

        payload = _gateway_probe(
            engine,
            {
                'gateway': {
                    'url': 'http://127.0.0.1:5700',
                    'reachable': 'configured',
                    'misconfigured': 'not-configured',
                }
            },
        )

        self.assertTrue(payload['reachable'])
        self.assertFalse(payload['misconfigured'])


if __name__ == '__main__':
    unittest.main()
