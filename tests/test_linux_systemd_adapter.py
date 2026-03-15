from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog.runtime import CommandResult


def _result(args: list[str], *, returncode: int = 0, stdout: str = '', stderr: str = '') -> CommandResult:
    return CommandResult(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


class LinuxSystemdEngineDouble:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            openclaw_gateway_service='openclaw-gateway.service',
            openclaw_gateway_port=5700,
            watchdog_restart_wait_seconds=2,
        )
        self.calls: list[tuple[list[str], int]] = []
        self.logs: list[tuple[str, str]] = []
        self._responses: dict[tuple[str, ...], CommandResult] = {}

    def run_command(self, args: list[str], *, timeout: int, merge_stderr: bool = False):
        self.calls.append((list(args), timeout))
        return self._responses.get(tuple(args), _result(args, returncode=1))

    def log(self, level: str, message: str) -> None:
        self.logs.append((level, message))


class LinuxSystemdAdapterTests(unittest.TestCase):
    def test_restart_service_uses_systemctl_user(self) -> None:
        from openclaw_watchdog.platforms.linux_systemd import LinuxSystemdPlatform

        engine = LinuxSystemdEngineDouble()
        engine._responses[
            ('systemctl', '--user', 'reset-failed', 'openclaw-gateway.service')
        ] = _result(['systemctl'], returncode=0)
        engine._responses[
            ('systemctl', '--user', 'restart', 'openclaw-gateway.service')
        ] = _result(['systemctl'], returncode=0)
        adapter = LinuxSystemdPlatform()

        with patch('openclaw_watchdog.platforms.linux_systemd.time.sleep') as sleep_mock:
            restarted = adapter.restart_service(engine)

        self.assertTrue(restarted)
        self.assertEqual(
            engine.calls[:2],
            [
                (['systemctl', '--user', 'reset-failed', 'openclaw-gateway.service'], 15),
                (['systemctl', '--user', 'restart', 'openclaw-gateway.service'], 30),
            ],
        )
        self.assertEqual(
            engine.logs,
            [('INFO', 'restarting openclaw-gateway.service')],
        )
        sleep_mock.assert_called_once_with(2)

    def test_listener_pids_reads_ss_output(self) -> None:
        from openclaw_watchdog.platforms.linux_systemd import LinuxSystemdPlatform

        engine = LinuxSystemdEngineDouble()
        engine._responses[('ss', '-tlnp')] = _result(
            ['ss', '-tlnp'],
            stdout='\n'.join(
                [
                    'LISTEN 0 128 *:5700 *:* users:(("node",pid=456,fd=21))',
                    'LISTEN 0 128 *:80 *:* users:(("nginx",pid=7,fd=8))',
                    'LISTEN 0 128 *:5700 *:* users:(("node",pid=123,fd=22))',
                ]
            ),
        )
        adapter = LinuxSystemdPlatform()

        self.assertEqual(adapter.listener_pids(engine), ['123', '456'])

    def test_describe_service_parses_systemctl_show_output(self) -> None:
        from openclaw_watchdog.platforms.linux_systemd import LinuxSystemdPlatform

        engine = LinuxSystemdEngineDouble()
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
            stdout='LoadState=loaded\nActiveState=active\nSubState=running\n',
        )
        adapter = LinuxSystemdPlatform()

        self.assertEqual(
            adapter.describe_service(engine),
            {
                'LoadState': 'loaded',
                'ActiveState': 'active',
                'SubState': 'running',
            },
        )


if __name__ == '__main__':
    unittest.main()
