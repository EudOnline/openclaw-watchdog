from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog.runtime import CommandResult


def _result(args: list[str], *, returncode: int = 0, stdout: str = '', stderr: str = '') -> CommandResult:
    return CommandResult(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


class MacosLaunchdEngineDouble:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            openclaw_gateway_service='com.openclaw.gateway',
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


class MacosLaunchdAdapterTests(unittest.TestCase):
    def test_describe_service_parses_launchctl_print_output(self) -> None:
        from openclaw_watchdog.platforms.macos_launchd import MacosLaunchdPlatform

        engine = MacosLaunchdEngineDouble()
        engine._responses[
            ('launchctl', 'print', 'gui/501/com.openclaw.gateway')
        ] = _result(
            ['launchctl'],
            stdout='''\nstate = running\npid = 321\n''',
        )
        adapter = MacosLaunchdPlatform(uid=501)

        self.assertEqual(
            adapter.describe_service(engine),
            {
                'state': 'running',
                'pid': '321',
            },
        )

    def test_describe_service_returns_empty_info_when_launchctl_print_fails(self) -> None:
        from openclaw_watchdog.platforms.macos_launchd import MacosLaunchdPlatform

        engine = MacosLaunchdEngineDouble()
        engine._responses[
            ('launchctl', 'print', 'gui/501/com.openclaw.gateway')
        ] = _result(
            ['launchctl'],
            returncode=113,
            stdout='''\nstate = running\npid = 321\n''',
            stderr='Could not find service',
        )
        adapter = MacosLaunchdPlatform(uid=501)

        self.assertEqual(adapter.describe_service(engine), {})

    def test_listener_pids_reads_lsof_output(self) -> None:
        from openclaw_watchdog.platforms.macos_launchd import MacosLaunchdPlatform

        engine = MacosLaunchdEngineDouble()
        engine._responses[
            ('lsof', '-nP', '-iTCP:5700', '-sTCP:LISTEN')
        ] = _result(
            ['lsof'],
            stdout='\n'.join(
                [
                    'COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME',
                    'node      321 user   12u  IPv4 0x1        0t0  TCP *:5700 (LISTEN)',
                ]
            ),
        )
        adapter = MacosLaunchdPlatform(uid=501)

        self.assertEqual(adapter.listener_pids(engine), ['321'])

    def test_restart_service_uses_launchctl_kickstart(self) -> None:
        from openclaw_watchdog.platforms.macos_launchd import MacosLaunchdPlatform

        engine = MacosLaunchdEngineDouble()
        engine._responses[
            ('launchctl', 'kickstart', '-k', 'gui/501/com.openclaw.gateway')
        ] = _result(['launchctl'], returncode=0)
        adapter = MacosLaunchdPlatform(uid=501)

        with patch('openclaw_watchdog.platforms.macos_launchd.time.sleep') as sleep_mock:
            restarted = adapter.restart_service(engine)

        self.assertTrue(restarted)
        self.assertEqual(
            engine.calls,
            [
                (['launchctl', 'kickstart', '-k', 'gui/501/com.openclaw.gateway'], 30),
            ],
        )
        self.assertEqual(engine.logs, [('INFO', 'restarting com.openclaw.gateway')])
        sleep_mock.assert_called_once_with(2)


if __name__ == '__main__':
    unittest.main()
