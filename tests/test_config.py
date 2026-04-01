import os
import tempfile
import unittest
from pathlib import Path

from openclaw_watchdog.config import Config


class ConfigDefaultsTest(unittest.TestCase):
    def _load_with_home(self, temp_home: str, env_text: str | None = None) -> Config:
        env_file = Path(temp_home) / 'watchdog.env'
        if env_text is not None:
            env_file.write_text(env_text, encoding='utf-8')
        old_home = os.environ.get('HOME')
        os.environ['HOME'] = temp_home
        try:
            return Config.load(env_file if env_text is not None else Path(temp_home) / 'missing.env')
        finally:
            if old_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = old_home

    def test_safe_defaults_without_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home:
            expected_home = Path(temp_home)
            config = self._load_with_home(temp_home)

        self.assertFalse(config.watchdog_enable_pre_repair_backup)
        self.assertFalse(hasattr(config, 'openclaw_install_command'))
        self.assertFalse(hasattr(config, 'opencode_install_command'))
        self.assertFalse(hasattr(config, 'watchdog_enable_codex_autorun'))
        self.assertEqual(config.watchdog_backup_script, Path('./tools/openclaw-backup.js').expanduser())
        self.assertEqual(config.watchdog_backup_env_file, Path('./config/openclaw-backup.env').expanduser())
        self.assertEqual(config.watchdog_restart_wait_seconds, 12)
        self.assertEqual(config.watchdog_active_no_listener_grace_seconds, 30)
        self.assertEqual(config.watchdog_service_level_timeout_seconds, 12)
        self.assertEqual(config.watchdog_service_level_retry_grace_seconds, 60)
        self.assertEqual(config.watchdog_service_level_failure_threshold, 6)
        self.assertFalse(config.watchdog_enable_model_http_error_failover)
        self.assertEqual(config.watchdog_model_http_error_threshold, 3)
        self.assertEqual(config.watchdog_model_http_error_window_minutes, 15)
        self.assertEqual(config.watchdog_model_http_error_cooldown_seconds, 1800)
        self.assertEqual(config.watchdog_model_failover_max_applies_per_day, 3)
        self.assertEqual(config.watchdog_codex_workdir, expected_home)
        self.assertEqual(config.watchdog_claude_code_workdir, expected_home)
        self.assertEqual(config.watchdog_gemini_cli_workdir, expected_home)
        self.assertEqual(config.watchdog_opencode_workdir, expected_home)
        self.assertEqual(config.openclaw_config, expected_home / '.openclaw/openclaw.json')
        self.assertEqual(config.watchdog_state_dir, expected_home / '.openclaw-backup/watchdog')
        self.assertFalse(hasattr(config, 'watchdog_rescue_executor_priority'))
        self.assertFalse(config.watchdog_litellm_enabled)
        self.assertEqual(config.watchdog_rescue_knowledge_root, expected_home / '.openclaw-backup/watchdog/rescue')
        self.assertEqual(config.watchdog_rescue_cases_dir, expected_home / '.openclaw-backup/watchdog/rescue/cases')
        self.assertEqual(config.watchdog_rescue_candidate_rules_dir, expected_home / '.openclaw-backup/watchdog/rescue/candidate-rules')
        self.assertEqual(config.watchdog_rescue_rules_dir, expected_home / '.openclaw-backup/watchdog/rescue/rules')
        self.assertEqual(config.watchdog_rescue_reviews_dir, expected_home / '.openclaw-backup/watchdog/rescue/reviews')
        self.assertEqual(
            config.watchdog_rescue_editable_paths,
            ('~/.openclaw/openclaw.json', '~/.openclaw-backup/watchdog/openclaw.survival.json'),
        )
        self.assertEqual(
            config.watchdog_rescue_editable_keys,
            ('channels', 'extensions', 'mcpServers', 'services', 'workers', 'schedules'),
        )
        self.assertFalse(hasattr(config, 'watchdog_codex_last_trigger_file'))
        self.assertFalse(hasattr(config, 'watchdog_codex_min_failures'))
        self.assertFalse(hasattr(config, 'watchdog_codex_cooldown_seconds'))
        self.assertFalse(hasattr(config, 'watchdog_opencode_fallback_workdir'))

    def test_legacy_rescue_executor_priority_env_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home:
            config = self._load_with_home(
                temp_home,
                '\n'.join(
                    [
                        'WATCHDOG_RESCUE_EXECUTOR_PRIORITY=rule-agent,litellm,opencode,codex',
                        'WATCHDOG_LITELLM_ENABLED=true',
                        'WATCHDOG_LITELLM_MODEL=openai/gpt-5',
                    ]
                ),
            )

        self.assertFalse(hasattr(config, 'watchdog_rescue_executor_priority'))
        self.assertTrue(config.watchdog_litellm_enabled)
        self.assertEqual(config.watchdog_litellm_model, 'openai/gpt-5')

    def test_parses_litellm_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home:
            config = self._load_with_home(
                temp_home,
                '\n'.join(
                    [
                        'WATCHDOG_LITELLM_ENABLED=true',
                        'WATCHDOG_LITELLM_MODEL=openai/gpt-5',
                        'WATCHDOG_LITELLM_API_BASE=https://example.invalid/v1',
                        'WATCHDOG_LITELLM_API_KEY_ENV=OPENAI_API_KEY',
                        'WATCHDOG_LITELLM_TIMEOUT_SECONDS=45',
                    ]
                ),
            )

        self.assertTrue(config.watchdog_litellm_enabled)
        self.assertEqual(config.watchdog_litellm_model, 'openai/gpt-5')
        self.assertEqual(config.watchdog_litellm_api_base, 'https://example.invalid/v1')
        self.assertEqual(config.watchdog_litellm_api_key_env, 'OPENAI_API_KEY')
        self.assertEqual(config.watchdog_litellm_timeout_seconds, 45)

    def test_parses_rescue_editable_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home:
            config = self._load_with_home(
                temp_home,
                '\n'.join(
                    [
                        'WATCHDOG_RESCUE_EDITABLE_PATHS=~/.openclaw/openclaw.json,~/.openclaw/extensions',
                        'WATCHDOG_RESCUE_EDITABLE_KEYS=channels.qqbot.enabled,extensions,services',
                    ]
                ),
            )

        self.assertEqual(
            config.watchdog_rescue_editable_paths,
            ('~/.openclaw/openclaw.json', '~/.openclaw/extensions'),
        )
        self.assertEqual(
            config.watchdog_rescue_editable_keys,
            ('channels.qqbot.enabled', 'extensions', 'services'),
        )

    def test_parses_executor_specific_runtime_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home:
            config = self._load_with_home(
                temp_home,
                '\n'.join(
                    [
                        'WATCHDOG_CLAUDE_CODE_BIN=claude-code-custom',
                        'WATCHDOG_CLAUDE_CODE_WORKDIR=~/claude-work',
                        'WATCHDOG_CLAUDE_CODE_TIMEOUT_SECONDS=41',
                        'WATCHDOG_GEMINI_CLI_BIN=gemini-custom',
                        'WATCHDOG_GEMINI_CLI_WORKDIR=~/gemini-work',
                        'WATCHDOG_GEMINI_CLI_TIMEOUT_SECONDS=42',
                        'WATCHDOG_OPENCODE_BIN=opencode-custom',
                        'WATCHDOG_OPENCODE_WORKDIR=~/opencode-work',
                        'WATCHDOG_OPENCODE_TIMEOUT_SECONDS=43',
                    ]
                ),
            )

        self.assertEqual(config.watchdog_claude_code_bin, 'claude-code-custom')
        self.assertEqual(config.watchdog_claude_code_workdir, Path(temp_home) / 'claude-work')
        self.assertEqual(config.watchdog_claude_code_timeout_seconds, 41)
        self.assertEqual(config.watchdog_gemini_cli_bin, 'gemini-custom')
        self.assertEqual(config.watchdog_gemini_cli_workdir, Path(temp_home) / 'gemini-work')
        self.assertEqual(config.watchdog_gemini_cli_timeout_seconds, 42)
        self.assertEqual(config.watchdog_opencode_bin, 'opencode-custom')
        self.assertEqual(config.watchdog_opencode_workdir, Path(temp_home) / 'opencode-work')
        self.assertEqual(config.watchdog_opencode_timeout_seconds, 43)

    def test_parses_model_http_error_failover_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home:
            config = self._load_with_home(
                temp_home,
                '\n'.join(
                    [
                        'WATCHDOG_ENABLE_MODEL_HTTP_ERROR_FAILOVER=true',
                        'WATCHDOG_MODEL_HTTP_ERROR_THRESHOLD=4',
                        'WATCHDOG_MODEL_HTTP_ERROR_WINDOW_MINUTES=20',
                        'WATCHDOG_MODEL_HTTP_ERROR_COOLDOWN_SECONDS=2700',
                        'WATCHDOG_MODEL_HTTP_ERROR_LOGS_LIMIT=300',
                        'WATCHDOG_MODEL_HTTP_ERROR_LOG_MAX_BYTES=131072',
                        'WATCHDOG_MODEL_FAILOVER_MAX_APPLIES_PER_DAY=5',
                    ]
                ),
            )

        self.assertTrue(config.watchdog_enable_model_http_error_failover)
        self.assertEqual(config.watchdog_model_http_error_threshold, 4)
        self.assertEqual(config.watchdog_model_http_error_window_minutes, 20)
        self.assertEqual(config.watchdog_model_http_error_cooldown_seconds, 2700)
        self.assertEqual(config.watchdog_model_http_error_logs_limit, 300)
        self.assertEqual(config.watchdog_model_http_error_log_max_bytes, 131072)
        self.assertEqual(config.watchdog_model_failover_max_applies_per_day, 5)



if __name__ == '__main__':
    unittest.main()
