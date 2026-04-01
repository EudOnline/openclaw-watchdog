from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


class _Result(SimpleNamespace):
    @property
    def output(self) -> str:
        return f"{getattr(self, 'stdout', '')}{getattr(self, 'stderr', '')}"


class ModelFailoverRuntimeTests(unittest.TestCase):
    def _build_engine(
        self,
        *,
        config_path: Path,
        logs_output: str = '',
        returncode: int = 0,
        run_state: dict[str, object] | None = None,
    ):
        state = dict(run_state or {})

        def _write_run_state(updates: dict[str, object]) -> dict[str, object]:
            state.update(updates)
            return dict(state)

        return SimpleNamespace(
            config=SimpleNamespace(
                openclaw_config=config_path,
                watchdog_enable_model_http_error_failover=True,
                watchdog_model_http_error_threshold=3,
                watchdog_model_http_error_window_minutes=15,
                watchdog_model_http_error_cooldown_seconds=1800,
                watchdog_model_failover_max_applies_per_day=3,
                watchdog_model_http_error_logs_limit=200,
                watchdog_model_http_error_log_max_bytes=262144,
            ),
            now_iso=lambda: '2026-04-01T12:00:00+08:00',
            run_command=lambda args, **kwargs: _Result(returncode=returncode, stdout=logs_output, stderr=''),
            read_run_state=lambda: dict(state),
            write_run_state=_write_run_state,
            log=Mock(),
        )

    def test_model_http_error_summary_counts_recent_non_200_entries(self) -> None:
        from openclaw_watchdog import model_failover_runtime

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'openclaw.json'
            config_path.write_text('{}\n', encoding='utf-8')
            logs_output = '\n'.join(
                [
                    json.dumps(
                        {
                            'timestamp': '2026-04-01T11:55:00+08:00',
                            'message': 'provider model request failed with upstream status',
                            'status': 503,
                            'model': 'openai/gpt-4.1',
                        }
                    ),
                    json.dumps(
                        {
                            'timestamp': '2026-04-01T11:56:00+08:00',
                            'message': 'upstream provider error',
                            'statusCode': 502,
                            'provider': 'openai',
                        }
                    ),
                    json.dumps(
                        {
                            'timestamp': '2026-04-01T11:57:00+08:00',
                            'message': 'model completion failed',
                            'http_status': 429,
                        }
                    ),
                    json.dumps(
                        {
                            'timestamp': '2026-04-01T11:58:00+08:00',
                            'message': 'model completion ok',
                            'status': 200,
                        }
                    ),
                    json.dumps(
                        {
                            'timestamp': '2026-04-01T11:00:00+08:00',
                            'message': 'provider model request failed earlier',
                            'status': 500,
                            'model': 'openai/gpt-4.1',
                        }
                    ),
                ]
            )
            engine = self._build_engine(config_path=config_path, logs_output=logs_output)

            payload = model_failover_runtime.model_http_error_summary(engine)

        self.assertTrue(payload['enabled'])
        self.assertEqual(payload['count'], 3)
        self.assertEqual(payload['latest_status'], 429)
        self.assertEqual(payload['latest_at'], '2026-04-01T11:57:00+08:00')
        self.assertTrue(payload['threshold_reached'])

    def test_rotate_primary_to_next_fallback_moves_old_primary_to_tail(self) -> None:
        from openclaw_watchdog import model_failover_runtime

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'openclaw.json'
            config_path.write_text(
                json.dumps(
                    {
                        'agents': {
                            'defaults': {
                                'model': {
                                    'primary': 'openai/gpt-4.1',
                                    'fallbacks': ['anthropic/claude-sonnet-4', 'openai/gpt-4o'],
                                }
                            }
                        }
                    }
                ),
                encoding='utf-8',
            )

            result = model_failover_runtime.rotate_primary_model(config_path)
            payload = json.loads(config_path.read_text(encoding='utf-8'))

        self.assertEqual(result['from_model'], 'openai/gpt-4.1')
        self.assertEqual(result['to_model'], 'anthropic/claude-sonnet-4')
        self.assertEqual(payload['agents']['defaults']['model']['primary'], 'anthropic/claude-sonnet-4')
        self.assertEqual(payload['agents']['defaults']['model']['fallbacks'], ['openai/gpt-4o', 'openai/gpt-4.1'])

    def test_apply_model_http_error_failover_skips_when_cooldown_is_active(self) -> None:
        from openclaw_watchdog import model_failover_runtime

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'openclaw.json'
            config_path.write_text(
                json.dumps(
                    {
                        'agents': {
                            'defaults': {
                                'model': {
                                    'primary': 'openai/gpt-4.1',
                                    'fallbacks': ['anthropic/claude-sonnet-4'],
                                }
                            }
                        }
                    }
                ),
                encoding='utf-8',
            )
            engine = self._build_engine(
                config_path=config_path,
                logs_output=json.dumps(
                    {
                        'timestamp': '2026-04-01T11:57:00+08:00',
                        'message': 'provider model request failed',
                        'status': 503,
                        'model': 'openai/gpt-4.1',
                    }
                ),
                run_state={'model_failover_last_applied_at': '2026-04-01T11:45:30+08:00'},
            )

            payload = model_failover_runtime.apply_model_http_error_failover(engine)
            config_after = json.loads(config_path.read_text(encoding='utf-8'))

        self.assertFalse(payload['applied'])
        self.assertEqual(payload['status'], 'cooldown')
        self.assertEqual(config_after['agents']['defaults']['model']['primary'], 'openai/gpt-4.1')

    def test_apply_model_http_error_failover_rate_limits_after_daily_cap(self) -> None:
        from openclaw_watchdog import model_failover_runtime

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'openclaw.json'
            config_path.write_text(
                json.dumps(
                    {
                        'agents': {
                            'defaults': {
                                'model': {
                                    'primary': 'openai/gpt-4.1',
                                    'fallbacks': ['anthropic/claude-sonnet-4', 'openai/gpt-4o'],
                                }
                            }
                        }
                    }
                ),
                encoding='utf-8',
            )
            engine = self._build_engine(
                config_path=config_path,
                logs_output='\n'.join(
                    [
                        json.dumps(
                            {
                                'timestamp': '2026-04-01T11:55:00+08:00',
                                'message': 'provider model request failed',
                                'status': 503,
                                'model': 'openai/gpt-4.1',
                            }
                        ),
                        json.dumps(
                            {
                                'timestamp': '2026-04-01T11:56:00+08:00',
                                'message': 'provider model request failed',
                                'status': 502,
                                'model': 'openai/gpt-4.1',
                            }
                        ),
                        json.dumps(
                            {
                                'timestamp': '2026-04-01T11:57:00+08:00',
                                'message': 'provider model request failed',
                                'status': 429,
                                'model': 'openai/gpt-4.1',
                            }
                        ),
                    ]
                ),
                run_state={
                    'model_failover_last_applied_at': '2026-03-31T08:00:00+08:00',
                    'model_failover_apply_history': [
                        '2026-04-01T02:00:00+08:00',
                        '2026-04-01T05:00:00+08:00',
                        '2026-04-01T08:00:00+08:00',
                    ],
                    'model_failover_last_summary': 'switched primary model openai/gpt-4.1 -> anthropic/claude-sonnet-4',
                },
            )

            payload = model_failover_runtime.apply_model_http_error_failover(engine)
            config_after = json.loads(config_path.read_text(encoding='utf-8'))
            run_state_after = engine.read_run_state()

        self.assertFalse(payload['applied'])
        self.assertEqual(payload['status'], 'rate-limited')
        self.assertEqual(config_after['agents']['defaults']['model']['primary'], 'openai/gpt-4.1')
        self.assertEqual(run_state_after['model_failover_last_status'], 'rate-limited')
        self.assertIn('daily rate limit', run_state_after['model_failover_last_summary'])
