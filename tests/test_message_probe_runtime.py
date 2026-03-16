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


def _build_engine(root: Path) -> SimpleNamespace:
    events_file = root / 'state' / 'message-probe-events.jsonl'
    return SimpleNamespace(
        config=SimpleNamespace(
            watchdog_enable_message_loop_probe=True,
            watchdog_message_loop_probe_channel='telegram',
            watchdog_message_loop_probe_target='@echo-bot',
            watchdog_message_loop_probe_account='default',
            watchdog_message_loop_probe_reply_from='@echo-bot',
            watchdog_message_loop_probe_events_file=events_file,
            watchdog_message_loop_probe_timeout_seconds=1,
            watchdog_message_loop_probe_cooldown_seconds=30,
            watchdog_message_timeout_seconds=5,
        ),
        now_iso=lambda: '2026-03-16T12:00:30+08:00',
        run_command=lambda args, **kwargs: _Result(returncode=0, stdout='{"ok":true}', stderr=''),
    )


class MessageProbeRuntimeTests(unittest.TestCase):
    def test_message_loop_probe_is_disabled_when_flag_is_off(self) -> None:
        import openclaw_watchdog.message_probe_runtime as message_probe_runtime

        with TemporaryDirectory() as temp_dir:
            engine = _build_engine(Path(temp_dir))
            engine.config.watchdog_enable_message_loop_probe = False

            result = message_probe_runtime.message_loop_probe(engine)

        self.assertFalse(result['message_loop_probe_enabled'])
        self.assertFalse(result['message_loop_probe_attempted'])
        self.assertEqual(result['message_loop_probe_summary'], 'disabled')

    def test_message_loop_probe_reuses_recent_cached_success(self) -> None:
        import openclaw_watchdog.message_probe_runtime as message_probe_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = _build_engine(root)
            engine.config.watchdog_message_loop_probe_events_file.parent.mkdir(parents=True, exist_ok=True)
            engine.config.watchdog_message_loop_probe_events_file.write_text(
                '\n'.join(
                    [
                        json.dumps(
                            {
                                'type': 'message',
                                'action': 'sent',
                                'timestamp': '2026-03-16T12:00:20+08:00',
                                'context': {
                                    'channelId': 'telegram',
                                    'accountId': 'default',
                                    'to': '@echo-bot',
                                    'content': 'openclaw-watchdog-probe:cachednonce',
                                    'success': True,
                                },
                            }
                        ),
                        json.dumps(
                            {
                                'type': 'message',
                                'action': 'received',
                                'timestamp': '2026-03-16T12:00:22+08:00',
                                'context': {
                                    'channelId': 'telegram',
                                    'accountId': 'default',
                                    'from': '@echo-bot',
                                    'content': 'openclaw-watchdog-probe:cachednonce',
                                },
                            }
                        ),
                    ]
                )
                + '\n',
                encoding='utf-8',
            )
            commands: list[list[str]] = []
            engine.run_command = lambda args, **kwargs: commands.append(args) or _Result(returncode=0, stdout='{"ok":true}', stderr='')

            result = message_probe_runtime.message_loop_probe(engine)

        self.assertTrue(result['message_loop_probe_enabled'])
        self.assertTrue(result['message_loop_probe_ready'])
        self.assertTrue(result['message_loop_probe_cached'])
        self.assertFalse(result['message_loop_probe_attempted'])
        self.assertEqual(commands, [])

    def test_message_loop_probe_reports_send_failure(self) -> None:
        import openclaw_watchdog.message_probe_runtime as message_probe_runtime

        with TemporaryDirectory() as temp_dir:
            engine = _build_engine(Path(temp_dir))
            engine.run_command = lambda args, **kwargs: _Result(returncode=1, stdout='', stderr='send failed')

            with patch('openclaw_watchdog.message_probe_runtime.generate_probe_nonce', return_value='failnonce'):
                result = message_probe_runtime.message_loop_probe(engine)

        self.assertTrue(result['message_loop_probe_attempted'])
        self.assertFalse(result['message_loop_probe_ready'])
        self.assertFalse(result['message_loop_probe_sent'])
        self.assertIn('send failed', result['message_loop_probe_summary'])

    def test_message_loop_probe_does_not_send_when_channel_or_target_is_missing(self) -> None:
        import openclaw_watchdog.message_probe_runtime as message_probe_runtime

        with TemporaryDirectory() as temp_dir:
            engine = _build_engine(Path(temp_dir))
            engine.config.watchdog_message_loop_probe_channel = ''
            commands: list[list[str]] = []
            engine.run_command = lambda args, **kwargs: commands.append(args) or _Result(returncode=0, stdout='{"ok":true}', stderr='')

            result = message_probe_runtime.message_loop_probe(engine)

        self.assertTrue(result['message_loop_probe_enabled'])
        self.assertFalse(result['message_loop_probe_attempted'])
        self.assertFalse(result['message_loop_probe_ready'])
        self.assertIn('misconfigured', result['message_loop_probe_summary'])
        self.assertEqual(commands, [])

    def test_message_loop_probe_matches_sent_and_received_events_for_current_nonce(self) -> None:
        import openclaw_watchdog.message_probe_runtime as message_probe_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = _build_engine(root)
            engine.config.watchdog_message_loop_probe_cooldown_seconds = 0
            engine.config.watchdog_message_loop_probe_events_file.parent.mkdir(parents=True, exist_ok=True)
            engine.config.watchdog_message_loop_probe_events_file.write_text(
                '\n'.join(
                    [
                        json.dumps(
                            {
                                'type': 'message',
                                'action': 'sent',
                                'timestamp': '2026-03-16T12:00:30+08:00',
                                'context': {
                                    'channelId': 'telegram',
                                    'accountId': 'default',
                                    'to': '@echo-bot',
                                    'content': 'openclaw-watchdog-probe:liveloop',
                                    'success': True,
                                },
                            }
                        ),
                        json.dumps(
                            {
                                'type': 'message',
                                'action': 'received',
                                'timestamp': '2026-03-16T12:00:31+08:00',
                                'context': {
                                    'channelId': 'telegram',
                                    'accountId': 'default',
                                    'from': '@echo-bot',
                                    'content': 'openclaw-watchdog-probe:liveloop',
                                },
                            }
                        ),
                    ]
                )
                + '\n',
                encoding='utf-8',
            )

            with patch('openclaw_watchdog.message_probe_runtime.generate_probe_nonce', return_value='liveloop'):
                result = message_probe_runtime.message_loop_probe(engine)

        self.assertTrue(result['message_loop_probe_attempted'])
        self.assertTrue(result['message_loop_probe_sent'])
        self.assertTrue(result['message_loop_probe_echo_received'])
        self.assertTrue(result['message_loop_probe_ready'])


if __name__ == '__main__':
    unittest.main()
