from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog import health
from openclaw_watchdog.engine import WatchdogEngine
from openclaw_watchdog.runtime import CommandResult


def _result(args: list[str], *, returncode: int = 0, stdout: str = '', stderr: str = '') -> CommandResult:
    return CommandResult(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


class ServiceRuntimeEngineDouble:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            openclaw_gateway_service='openclaw-gateway.service',
            openclaw_gateway_port=5700,
        )
        self.calls: list[list[str]] = []
        self._responses: dict[tuple[str, ...], CommandResult] = {}

    def run_command(self, args: list[str], **kwargs) -> CommandResult:
        self.calls.append(list(args))
        return self._responses.get(tuple(args), _result(args, returncode=1))


class ServiceRuntimeTests(unittest.TestCase):
    def test_watchdog_engine_no_longer_exposes_service_runtime_proxies(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'service_active'))
        self.assertFalse(hasattr(WatchdogEngine, 'service_main_pid'))
        self.assertFalse(hasattr(WatchdogEngine, 'listener_pids'))
        self.assertFalse(hasattr(WatchdogEngine, 'listener_count'))
        self.assertFalse(hasattr(WatchdogEngine, 'listener_contains_pid'))
        self.assertFalse(hasattr(WatchdogEngine, 'pid_descends_from'))
        self.assertFalse(hasattr(WatchdogEngine, 'listener_matches_service_tree'))

    def test_health_raw_live_probe_does_not_require_engine_service_wrappers(self) -> None:
        engine = ServiceRuntimeEngineDouble()
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

        payload = health.raw_live_probe(engine)

        self.assertTrue(payload['service_active'])
        self.assertEqual(payload['service_main_pid'], '123')
        self.assertEqual(payload['listener_pids'], ['123'])
        self.assertTrue(payload['service_tree_listener_match'])
        self.assertEqual(payload['listener_match_kind'], 'direct')
        self.assertEqual(payload['matching_listener_pid'], '123')
        self.assertTrue(payload['healthy'])

    def test_health_facade_raw_live_probe_delegates_to_probe_runtime(self) -> None:
        engine = object()
        expected = {'healthy': True}
        runtime = SimpleNamespace(raw_live_probe=unittest.mock.Mock(return_value=expected))

        with patch.object(health, 'health_probe_runtime', runtime, create=True):
            payload = health.raw_live_probe(engine)

        self.assertEqual(payload, expected)
        runtime.raw_live_probe.assert_called_once_with(engine)

    def test_listener_pids_filters_by_gateway_port_and_sorts(self) -> None:
        from openclaw_watchdog import service_runtime

        engine = ServiceRuntimeEngineDouble()
        ss_output = '\n'.join(
            [
                'LISTEN 0 128 *:5700 *:* users:(("node",pid=42,fd=21))',
                'LISTEN 0 128 *:80 *:* users:(("nginx",pid=7,fd=8))',
                'LISTEN 0 128 *:5700 *:* users:(("node",pid=11,fd=20))',
            ]
        )
        engine._responses[('ss', '-tlnp')] = _result(['ss', '-tlnp'], stdout=ss_output)

        self.assertEqual(service_runtime.listener_pids(engine), ['11', '42'])

    def test_pid_descends_from_walks_parent_chain(self) -> None:
        from openclaw_watchdog import service_runtime

        engine = ServiceRuntimeEngineDouble()
        engine._responses[('ps', '-o', 'ppid=', '-p', '456')] = _result(['ps'], stdout='  123 \n')
        engine._responses[('ps', '-o', 'ppid=', '-p', '789')] = _result(['ps'], stdout='  456 \n')

        self.assertTrue(service_runtime.pid_descends_from(engine, '789', '123'))
        self.assertFalse(service_runtime.pid_descends_from(engine, '789', '999'))

    def test_listener_matches_service_tree_detects_direct_and_child_matches(self) -> None:
        from openclaw_watchdog import service_runtime

        engine = ServiceRuntimeEngineDouble()

        with patch('openclaw_watchdog.service_runtime.listener_pids', return_value=['321', '654']):
            with patch('openclaw_watchdog.service_runtime.pid_descends_from', side_effect=lambda _engine, pid, ancestor: pid == '654' and ancestor == '123'):
                self.assertEqual(service_runtime.listener_matches_service_tree(engine, '321'), (True, 'direct', '321'))
                self.assertEqual(service_runtime.listener_matches_service_tree(engine, '123'), (True, 'child', '654'))
                self.assertEqual(service_runtime.listener_matches_service_tree(engine, '0'), (False, 'none', ''))


if __name__ == '__main__':
    unittest.main()
