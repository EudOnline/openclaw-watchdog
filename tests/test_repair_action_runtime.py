from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog.runtime import CommandResult


def _result(args: list[str], *, returncode: int = 0, stdout: str = '', stderr: str = '') -> CommandResult:
    return CommandResult(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


class RepairActionRuntimeTests(unittest.TestCase):
    def test_run_pre_repair_backup_marks_missing_script_and_writes_marker(self) -> None:
        from openclaw_watchdog import repair_action_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            marker = root / 'incident-backup-done'
            logs: list[tuple[str, str]] = []
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_enable_pre_repair_backup=True,
                    watchdog_backup_script=root / 'missing.js',
                    watchdog_backup_env_file=root / 'backup.env',
                    watchdog_backup_timeout_seconds=30,
                    watchdog_log_file=root / 'watchdog.log',
                ),
                incident_backup_marker=marker,
                ctx=SimpleNamespace(
                    pre_repair_backup_result='',
                    run_ts='2026-03-12 21:00:00 CST',
                ),
                log=lambda level, message: logs.append((level, message)),
            )

            repair_action_runtime.run_pre_repair_backup(engine)

            marker_text = marker.read_text(encoding='utf-8')

        self.assertEqual(engine.ctx.pre_repair_backup_result, 'backup-script-missing')
        self.assertIn('backup-script-missing', marker_text)
        self.assertEqual(logs, [('WARN', f'pre-repair backup skipped: missing script {engine.config.watchdog_backup_script}')])

    def test_restart_service_resets_failed_and_waits_on_success(self) -> None:
        from openclaw_watchdog import repair_action_runtime

        calls: list[tuple[list[str], int]] = []

        def run_command(args: list[str], *, timeout: int, merge_stderr: bool = False):
            calls.append((list(args), timeout))
            if args[-2:] == ['restart', 'openclaw-gateway.service']:
                return SimpleNamespace(returncode=0, output='')
            return SimpleNamespace(returncode=0, output='')

        engine = SimpleNamespace(
            config=SimpleNamespace(
                openclaw_gateway_service='openclaw-gateway.service',
                watchdog_restart_wait_seconds=2,
            ),
            run_command=run_command,
            log=lambda level, message: None,
        )

        with patch('openclaw_watchdog.repair_action_runtime.time.sleep') as sleep_mock:
            restarted = repair_action_runtime.restart_service(engine)

        self.assertTrue(restarted)
        self.assertEqual(
            calls,
            [
                (['systemctl', '--user', 'reset-failed', 'openclaw-gateway.service'], 15),
                (['systemctl', '--user', 'restart', 'openclaw-gateway.service'], 30),
            ],
        )
        sleep_mock.assert_called_once_with(2)

    def test_restart_service_delegates_to_platform_supervisor_when_present(self) -> None:
        from openclaw_watchdog import repair_action_runtime

        supervisor = SimpleNamespace(restart_service=unittest.mock.Mock(return_value=True))
        engine = SimpleNamespace(platform=SimpleNamespace(supervisor=supervisor))

        restarted = repair_action_runtime.restart_service(engine)

        self.assertTrue(restarted)
        supervisor.restart_service.assert_called_once_with(engine)

    def test_kill_stray_listeners_does_not_require_engine_listener_wrapper(self) -> None:
        from openclaw_watchdog import repair_action_runtime

        logs: list[tuple[str, str]] = []

        def run_command(args: list[str], *, timeout: int, merge_stderr: bool = False):
            if args == ['ss', '-tlnp']:
                return _result(
                    args,
                    stdout='\n'.join(
                        [
                            'LISTEN 0 128 *:5700 *:* users:(("node",pid=123,fd=21))',
                            'LISTEN 0 128 *:5700 *:* users:(("node",pid=456,fd=22))',
                        ]
                    ),
                )
            if args == ['ps', '-p', '456', '-o', 'args=']:
                return _result(args, stdout='openclaw gateway --port 5700\n')
            return _result(args, returncode=1)

        engine = SimpleNamespace(
            config=SimpleNamespace(openclaw_gateway_port=5700),
            run_command=run_command,
            log=lambda level, message: logs.append((level, message)),
        )

        with patch('openclaw_watchdog.repair_action_runtime.os.kill') as kill_mock:
            with patch('openclaw_watchdog.repair_action_runtime.time.sleep') as sleep_mock:
                repair_action_runtime.kill_stray_listeners(engine, '123')

        kill_mock.assert_called_once()
        kill_args, _ = kill_mock.call_args
        self.assertEqual(kill_args[0], 456)
        self.assertEqual(logs, [('WARN', 'killing stray listener pid=456 cmd=openclaw gateway --port 5700')])
        sleep_mock.assert_called_once_with(2)

    def test_run_doctor_repair_logs_warning_on_failure(self) -> None:
        from openclaw_watchdog import repair_action_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            logs: list[tuple[str, str]] = []

            def run_command(args: list[str], *, timeout: int, merge_stderr: bool = False):
                self.assertEqual(args, ['openclaw', 'doctor', '--repair', '--non-interactive', '--yes'])
                self.assertTrue(merge_stderr)
                return SimpleNamespace(returncode=9, output='doctor failed\n')

            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_enable_doctor_repair=True,
                    watchdog_doctor_timeout_seconds=20,
                    watchdog_log_file=root / 'watchdog.log',
                ),
                run_command=run_command,
                log=lambda level, message: logs.append((level, message)),
            )

            repaired = repair_action_runtime.run_doctor_repair(engine)

            log_file_text = engine.config.watchdog_log_file.read_text(encoding='utf-8')

        self.assertFalse(repaired)
        self.assertIn('doctor failed', log_file_text)
        self.assertEqual(
            logs,
            [
                ('INFO', 'running openclaw doctor --repair --non-interactive --yes'),
                ('WARN', 'doctor repair exited rc=9'),
            ],
        )

    def test_run_doctor_repair_returns_true_on_success(self) -> None:
        from openclaw_watchdog import repair_action_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            logs: list[tuple[str, str]] = []

            def run_command(args: list[str], *, timeout: int, merge_stderr: bool = False):
                return SimpleNamespace(returncode=0, output='doctor fixed config\n')

            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_enable_doctor_repair=True,
                    watchdog_doctor_timeout_seconds=20,
                    watchdog_log_file=root / 'watchdog.log',
                ),
                run_command=run_command,
                log=lambda level, message: logs.append((level, message)),
            )

            repaired = repair_action_runtime.run_doctor_repair(engine)

        self.assertTrue(repaired)
        self.assertEqual(
            logs,
            [
                ('INFO', 'running openclaw doctor --repair --non-interactive --yes'),
                ('INFO', 'doctor repair completed'),
            ],
        )


if __name__ == '__main__':
    unittest.main()
