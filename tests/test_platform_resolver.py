from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def _build_config(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        watchdog_state_dir=root / 'state',
        watchdog_run_state_file=root / 'state' / 'run-state.json',
        watchdog_rollback_archive_dir=root / 'rollback',
        watchdog_incidents_dir=root / 'incidents',
        watchdog_log_file=root / 'logs' / 'watchdog.log',
        watchdog_event_history_file=root / 'history' / 'events.jsonl',
        watchdog_incident_index_file=root / 'incidents' / 'index.json',
        watchdog_last_report_file=root / 'reports' / 'last-report.json',
        watchdog_last_metrics_file=root / 'metrics' / 'last-metrics.json',
        watchdog_survival_config_file=root / 'survival' / 'config.json',
        watchdog_survival_state_file=root / 'survival' / 'state.json',
        watchdog_guard_manifest_file=root / 'guard' / 'manifest.json',
        watchdog_lock_file=root / 'lock' / 'watchdog.lock',
        watchdog_failure_count_file=root / 'state' / 'failure-count',
        watchdog_notify_account='bot-account',
        watchdog_notify_channel='',
        watchdog_notify_target='',
        watchdog_message_timeout_seconds=17,
        watchdog_survival_stable_ready_runs=2,
    )


class PlatformResolverTests(unittest.TestCase):
    def test_linux_systemd_user_resolves_linux_adapter(self) -> None:
        from openclaw_watchdog.platforms import resolver

        platform = resolver.resolve_platform_adapter(
            host_family='linux',
            available_commands={'systemctl', 'ss', 'ps'},
            systemd_user_supported=True,
        )

        self.assertEqual(platform.capabilities.host_family, 'linux')
        self.assertEqual(platform.capabilities.supervisor, 'systemd_user')
        self.assertEqual(platform.capabilities.listener_tool, 'ss')
        self.assertTrue(platform.capabilities.supports_managed_restart)
        self.assertTrue(platform.capabilities.supports_listener_pid_tree)

    def test_missing_supervisor_falls_back_to_manual_capability(self) -> None:
        from openclaw_watchdog.platforms import resolver

        platform = resolver.resolve_platform_adapter(
            host_family='darwin',
            available_commands={'lsof', 'ps'},
            systemd_user_supported=False,
        )

        self.assertEqual(platform.capabilities.host_family, 'darwin')
        self.assertEqual(platform.capabilities.supervisor, 'manual')
        self.assertEqual(platform.capabilities.listener_tool, 'manual')
        self.assertFalse(platform.capabilities.supports_managed_restart)
        self.assertFalse(platform.capabilities.supports_listener_pid_tree)

    def test_engine_resolves_platform_dependency_during_init(self) -> None:
        from openclaw_watchdog.engine import WatchdogEngine

        with TemporaryDirectory() as temp_dir:
            config = _build_config(Path(temp_dir))
            resolved_platform = object()

            with patch('openclaw_watchdog.engine.engine_support_runtime.prepare_state_dirs'):
                with patch('openclaw_watchdog.engine.resolver.resolve_platform', return_value=resolved_platform) as resolve_platform:
                    engine = WatchdogEngine(config)

        self.assertIs(engine.platform, resolved_platform)
        resolve_platform.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
