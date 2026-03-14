from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


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
    )


class EngineSupportRuntimeTests(unittest.TestCase):
    def test_prepare_state_dirs_creates_expected_paths_and_bootstraps_run_state(self) -> None:
        from openclaw_watchdog import engine_support_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            writes: list[dict[str, object]] = []

            engine = SimpleNamespace(
                config=config,
                run_state_file=config.watchdog_run_state_file,
            )

            def write_run_state(updates: dict[str, object]) -> None:
                writes.append(dict(updates))
                engine.run_state_file.parent.mkdir(parents=True, exist_ok=True)
                engine.run_state_file.write_text('{}\n', encoding='utf-8')

            engine.write_run_state = write_run_state

            engine_support_runtime.prepare_state_dirs(engine)

            self.assertTrue(config.watchdog_state_dir.exists())
            self.assertTrue(config.watchdog_rollback_archive_dir.exists())
            self.assertTrue(config.watchdog_incidents_dir.exists())
            self.assertTrue(config.watchdog_log_file.exists())
            self.assertTrue(config.watchdog_event_history_file.exists())
            self.assertEqual(writes, [{}])

            writes.clear()
            engine_support_runtime.prepare_state_dirs(engine)
            self.assertEqual(writes, [])

    def test_acquire_lock_closes_failed_handle_and_release_unlocks(self) -> None:
        from openclaw_watchdog import engine_support_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)

            first = SimpleNamespace(config=config, lock_handle=None)
            second = SimpleNamespace(config=config, lock_handle=None)

            self.assertTrue(engine_support_runtime.acquire_lock(first))
            self.assertFalse(engine_support_runtime.acquire_lock(second))
            self.assertIsNone(second.lock_handle)

            engine_support_runtime.release_lock(first)
            self.assertIsNone(first.lock_handle)

            self.assertTrue(engine_support_runtime.acquire_lock(second))
            engine_support_runtime.release_lock(second)
            self.assertIsNone(second.lock_handle)

    def test_log_notify_and_simple_state_helpers_behave_as_expected(self) -> None:
        from openclaw_watchdog import engine_support_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            config.watchdog_log_file.parent.mkdir(parents=True, exist_ok=True)
            config.watchdog_failure_count_file.parent.mkdir(parents=True, exist_ok=True)

            commands: list[dict[str, object]] = []

            def run_command(args, *, timeout=None, cwd=None, merge_stderr=False, input_text=None):
                commands.append(
                    {
                        'args': args,
                        'timeout': timeout,
                        'cwd': cwd,
                        'merge_stderr': merge_stderr,
                        'input_text': input_text,
                    }
                )
                return SimpleNamespace(returncode=0, output='')

            engine = SimpleNamespace(
                config=config,
                ctx=SimpleNamespace(rollback_summary='已执行回退', consecutive_failures=0),
                run_command=run_command,
            )

            engine_support_runtime.log(engine, 'WARN', 'unit-test')
            self.assertIn('[WARN] unit-test', config.watchdog_log_file.read_text(encoding='utf-8'))

            engine_support_runtime.notify(engine, 'skip me')
            self.assertEqual(commands, [])

            config.watchdog_notify_channel = 'alerts'
            config.watchdog_notify_target = 'ops-room'
            engine_support_runtime.notify(engine, 'hello')
            self.assertEqual(
                commands,
                [
                    {
                        'args': [
                            'openclaw',
                            'message',
                            'send',
                            '--account',
                            'bot-account',
                            '--channel',
                            'alerts',
                            '--target',
                            'ops-room',
                            '--message',
                            'hello',
                        ],
                        'timeout': 17,
                        'cwd': None,
                        'merge_stderr': False,
                        'input_text': None,
                    }
                ],
            )

            self.assertEqual(
                engine_support_runtime.append_rollback_summary(engine, '状态摘要'),
                '状态摘要\n\n回退摘要：\n已执行回退',
            )
            self.assertEqual(engine_support_runtime.read_failure_count(engine), 0)
            engine_support_runtime.write_failure_count(engine, 3)
            self.assertEqual(engine.ctx.consecutive_failures, 3)
            self.assertEqual(engine_support_runtime.read_failure_count(engine), 3)
            self.assertEqual(engine_support_runtime.increment_failure_count(engine), 4)
            self.assertEqual(engine_support_runtime.read_failure_count(engine), 4)
            engine_support_runtime.reset_failure_count(engine)
            self.assertEqual(engine_support_runtime.read_failure_count(engine), 0)

            self.assertEqual(engine_support_runtime.current_mode(maintenance=True, degraded=True, survival=True), 'maintenance')
            self.assertEqual(engine_support_runtime.current_mode(maintenance=False, degraded=False, survival=True), 'survival')
            self.assertEqual(engine_support_runtime.current_mode(maintenance=False, degraded=True, survival=False), 'degraded')
            self.assertEqual(engine_support_runtime.current_mode(maintenance=False, degraded=False, survival=False), 'normal')
            self.assertEqual(
                engine_support_runtime.sibling_json_path(Path('/tmp/watchdog-event')),
                Path('/tmp/watchdog-event.json'),
            )
            datetime.fromisoformat(engine_support_runtime.now_iso(engine))


if __name__ == '__main__':
    unittest.main()
