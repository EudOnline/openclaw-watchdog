from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class _Result(SimpleNamespace):
    @property
    def output(self) -> str:
        return f"{getattr(self, 'stdout', '')}{getattr(self, 'stderr', '')}"


def _conversation_engine(*, optional_failures_allowed: bool = True):
    return SimpleNamespace(
        config=SimpleNamespace(
            watchdog_minimal_usable_allow_optional_failures=optional_failures_allowed,
            watchdog_enable_conversation_probe=True,
            watchdog_primary_conversation_targets=('gateway', 'channels'),
        ),
        now_iso=lambda: '2026-03-16T12:00:00+08:00',
    )


class HealthProbeRuntimeTests(unittest.TestCase):
    def test_service_level_probe_treats_string_false_gateway_flag_as_unhealthy(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        engine = SimpleNamespace(
            config=SimpleNamespace(
                watchdog_enable_service_level_probe=True,
                watchdog_service_level_timeout_seconds=12,
                openclaw_gateway_port=18789,
            ),
            now_iso=lambda: '2026-03-16T12:00:00+08:00',
            run_command=lambda args, **kwargs: _Result(
                returncode=0,
                stdout=json.dumps({'gateway': {'reachable': 'false', 'misconfigured': 'false'}}),
                stderr='',
            ),
        )

        probe = health_probe_runtime.service_level_probe(engine)

        self.assertFalse(probe['service_layer_healthy'])
        self.assertEqual(probe['service_probe_summary'], 'gateway.reachable=false')

    def test_conversation_probe_does_not_promote_minimal_to_ready_without_explicit_signal(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        probe = health_probe_runtime.conversation_level_probe(
            _conversation_engine(),
            {
                'gateway': {'reachable': True, 'misconfigured': False},
                'conversation': {'minimalUsable': True},
            },
            service_layer_healthy=True,
        )

        self.assertFalse(probe['conversation_ready'])
        self.assertTrue(probe['minimal_usable_ready'])
        self.assertEqual(probe['conversation_status'], 'minimal')

    def test_conversation_probe_does_not_report_ready_when_only_gateway_is_reachable(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        probe = health_probe_runtime.conversation_level_probe(
            _conversation_engine(),
            {'gateway': {'reachable': True, 'misconfigured': False}},
            service_layer_healthy=True,
        )

        self.assertFalse(probe['conversation_ready'])
        self.assertFalse(probe['minimal_usable_ready'])
        self.assertEqual(probe['conversation_status'], 'down')

    def test_conversation_probe_treats_string_false_flags_as_false(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        probe = health_probe_runtime.conversation_level_probe(
            _conversation_engine(),
            {
                'gateway': {'reachable': 'false', 'misconfigured': 'false'},
                'conversation': {'ready': 'false', 'minimalUsable': 'false'},
            },
            service_layer_healthy=False,
        )

        self.assertFalse(probe['conversation_ready'])
        self.assertFalse(probe['minimal_usable_ready'])
        self.assertEqual(probe['conversation_status'], 'down')

    def test_conversation_probe_legacy_fixture_stays_minimal(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        payload = json.loads(
            Path('tests/fixtures/openclaw_contracts/status/legacy.json').read_text(encoding='utf-8')
        )

        probe = health_probe_runtime.conversation_level_probe(
            _conversation_engine(),
            payload,
            service_layer_healthy=True,
        )

        self.assertFalse(probe['conversation_ready'])
        self.assertTrue(probe['minimal_usable_ready'])
        self.assertEqual(probe['conversation_status'], 'minimal')

    def test_conversation_probe_missing_gateway_fixture_stays_down(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        payload = json.loads(
            Path('tests/fixtures/openclaw_contracts/status/edge-missing-gateway.json').read_text(encoding='utf-8')
        )

        probe = health_probe_runtime.conversation_level_probe(
            _conversation_engine(),
            payload,
            service_layer_healthy=True,
        )

        self.assertFalse(probe['conversation_ready'])
        self.assertFalse(probe['minimal_usable_ready'])
        self.assertEqual(probe['conversation_status'], 'down')

    def test_live_probe_prefers_message_loop_probe_when_enabled_and_ready(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_active_no_listener_grace_seconds=0,
                    watchdog_service_level_retry_grace_seconds=0,
                    watchdog_enable_survivability_flow=True,
                    watchdog_survival_stable_ready_runs=2,
                    watchdog_guard_manifest_file=root / 'guard.json',
                    watchdog_maintenance_file=root / 'maintenance.flag',
                    watchdog_enable_message_loop_probe=True,
                ),
                now_iso=lambda: '2026-03-16T12:00:00+08:00',
                read_run_state=lambda: {},
                current_mode=lambda **kwargs: 'normal',
            )

            with patch('openclaw_watchdog.health_probe_runtime.raw_live_probe', return_value={'service_active': True, 'service_main_pid': '123', 'listener_pids': ['123'], 'service_tree_listener_match': True, 'listener_match_kind': 'direct', 'matching_listener_pid': '123', 'healthy': True}):
                with patch('openclaw_watchdog.health_probe_runtime.service_level_probe', return_value={'enabled': True, 'service_layer_healthy': True, 'service_probe_rc': 0, 'service_probe_summary': 'gateway.reachable=true', 'service_status_payload': {}, 'service_probe_checked_at': '2026-03-16T12:00:00+08:00'}):
                    with patch('openclaw_watchdog.health_probe_runtime.conversation_level_probe', return_value={'conversation_ready': False, 'minimal_usable_ready': False, 'conversation_status': 'down', 'conversation_probe_summary': 'heuristic-down', 'conversation_probe_checked_at': '2026-03-16T12:00:00+08:00', 'conversation_probe_targets': []}):
                        with patch('openclaw_watchdog.health_probe_runtime.message_probe_runtime.message_loop_probe', return_value={'message_loop_probe_enabled': True, 'message_loop_probe_attempted': True, 'message_loop_probe_ready': True, 'message_loop_probe_sent': True, 'message_loop_probe_echo_received': True, 'message_loop_probe_summary': 'message loop ready', 'message_loop_probe_cached': False, 'message_loop_probe_checked_at': '2026-03-16T12:00:00+08:00'}):
                            payload = health_probe_runtime.live_probe(engine, include_doctor=False, apply_grace=False)

        self.assertTrue(payload['conversation_ready'])
        self.assertTrue(payload['minimal_usable_ready'])
        self.assertEqual(payload['conversation_status'], 'ready')
        self.assertEqual(payload['conversation_probe_summary'], 'message loop ready')

    def test_live_probe_marks_conversation_down_when_message_loop_probe_enabled_and_fails(self) -> None:
        from openclaw_watchdog import health_probe_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_active_no_listener_grace_seconds=0,
                    watchdog_service_level_retry_grace_seconds=0,
                    watchdog_enable_survivability_flow=True,
                    watchdog_survival_stable_ready_runs=2,
                    watchdog_guard_manifest_file=root / 'guard.json',
                    watchdog_maintenance_file=root / 'maintenance.flag',
                    watchdog_enable_message_loop_probe=True,
                ),
                now_iso=lambda: '2026-03-16T12:00:00+08:00',
                read_run_state=lambda: {},
                current_mode=lambda **kwargs: 'normal',
            )

            with patch('openclaw_watchdog.health_probe_runtime.raw_live_probe', return_value={'service_active': True, 'service_main_pid': '123', 'listener_pids': ['123'], 'service_tree_listener_match': True, 'listener_match_kind': 'direct', 'matching_listener_pid': '123', 'healthy': True}):
                with patch('openclaw_watchdog.health_probe_runtime.service_level_probe', return_value={'enabled': True, 'service_layer_healthy': True, 'service_probe_rc': 0, 'service_probe_summary': 'gateway.reachable=true', 'service_status_payload': {}, 'service_probe_checked_at': '2026-03-16T12:00:00+08:00'}):
                    with patch('openclaw_watchdog.health_probe_runtime.conversation_level_probe', return_value={'conversation_ready': True, 'minimal_usable_ready': True, 'conversation_status': 'ready', 'conversation_probe_summary': 'heuristic-ready', 'conversation_probe_checked_at': '2026-03-16T12:00:00+08:00', 'conversation_probe_targets': []}):
                        with patch('openclaw_watchdog.health_probe_runtime.message_probe_runtime.message_loop_probe', return_value={'message_loop_probe_enabled': True, 'message_loop_probe_attempted': True, 'message_loop_probe_ready': False, 'message_loop_probe_sent': True, 'message_loop_probe_echo_received': False, 'message_loop_probe_summary': 'message loop timeout', 'message_loop_probe_cached': False, 'message_loop_probe_checked_at': '2026-03-16T12:00:00+08:00'}):
                            payload = health_probe_runtime.live_probe(engine, include_doctor=False, apply_grace=False)

        self.assertFalse(payload['conversation_ready'])
        self.assertFalse(payload['minimal_usable_ready'])
        self.assertEqual(payload['conversation_status'], 'down')
        self.assertEqual(payload['conversation_probe_summary'], 'message loop timeout')


if __name__ == '__main__':
    unittest.main()
