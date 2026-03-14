import unittest
from types import SimpleNamespace

from openclaw_watchdog import executor_registry
from openclaw_watchdog.engine import WatchdogEngine


class ExecutorRegistryTest(unittest.TestCase):
    def test_configured_priority_defaults_to_canonical_order(self) -> None:
        config = SimpleNamespace()

        self.assertEqual(
            executor_registry.configured_priority(config),
            ('codex', 'claude-code', 'gemini-cli', 'opencode', 'litellm', 'rule-agent'),
        )

    def test_configured_priority_ignores_legacy_override_values(self) -> None:
        config = SimpleNamespace(watchdog_rescue_executor_priority=('rule-agent', 'litellm', 'codex'))

        self.assertEqual(
            executor_registry.configured_priority(config),
            ('codex', 'claude-code', 'gemini-cli', 'opencode', 'litellm', 'rule-agent'),
        )

    def test_available_executors_keeps_canonical_order_even_when_legacy_override_is_present(self) -> None:
        config = SimpleNamespace(
            watchdog_rescue_executor_priority=('rule-agent', 'litellm', 'opencode', 'codex'),
            watchdog_codex_bin='custom-codex',
            watchdog_opencode_bin='custom-open',
            watchdog_litellm_enabled=True,
            watchdog_litellm_model='openai/gpt-5',
        )
        available = {
            'custom-codex': '/usr/bin/custom-codex',
            'custom-open': '/usr/bin/custom-open',
        }

        self.assertEqual(
            executor_registry.available_executors(config, which=lambda command: available.get(command)),
            ('codex', 'opencode', 'litellm', 'rule-agent'),
        )

    def test_rescue_command_resolves_configured_and_fallback_candidates(self) -> None:
        config = SimpleNamespace(
            watchdog_codex_bin='custom-codex',
            watchdog_opencode_bin='custom-opencode',
        )
        available = {
            'custom-codex': '/usr/bin/custom-codex',
            'claude': '/usr/bin/claude',
            'gemini-cli': '/usr/bin/gemini-cli',
            'custom-opencode': '/usr/bin/custom-opencode',
        }
        which = lambda command: available.get(command)

        self.assertEqual(executor_registry.rescue_command(config, 'codex', which=which), 'custom-codex')
        self.assertEqual(executor_registry.rescue_command(config, 'claude-code', which=which), 'claude')
        self.assertEqual(executor_registry.rescue_command(config, 'gemini-cli', which=which), 'gemini-cli')
        self.assertEqual(executor_registry.rescue_command(config, 'opencode', which=which), 'custom-opencode')

    def test_runtime_settings_are_executor_specific(self) -> None:
        config = SimpleNamespace(
            watchdog_codex_timeout_seconds=11,
            watchdog_codex_workdir='/codex',
            watchdog_claude_code_timeout_seconds=22,
            watchdog_claude_code_workdir='/claude',
            watchdog_gemini_cli_timeout_seconds=33,
            watchdog_gemini_cli_workdir='/gemini',
            watchdog_opencode_timeout_seconds=44,
            watchdog_opencode_workdir='/opencode',
        )

        self.assertEqual(executor_registry.timeout_seconds(config, 'codex', default=120), 11)
        self.assertEqual(executor_registry.timeout_seconds(config, 'claude-code', default=120), 22)
        self.assertEqual(executor_registry.timeout_seconds(config, 'gemini-cli', default=120), 33)
        self.assertEqual(executor_registry.timeout_seconds(config, 'opencode', default=120), 44)
        self.assertEqual(executor_registry.workdir(config, 'codex'), '/codex')
        self.assertEqual(executor_registry.workdir(config, 'claude-code'), '/claude')
        self.assertEqual(executor_registry.workdir(config, 'gemini-cli'), '/gemini')
        self.assertEqual(executor_registry.workdir(config, 'opencode'), '/opencode')

    def test_executor_available_supports_direct_paths_and_builtins(self) -> None:
        config = SimpleNamespace(
            watchdog_codex_bin='./bin/codex',
            watchdog_litellm_enabled=True,
            watchdog_litellm_model='openai/gpt-5',
        )
        available = {
            './bin/codex': './bin/codex',
        }
        which = lambda command: available.get(command)

        self.assertTrue(executor_registry.executor_available(config, 'codex', which=which))
        self.assertTrue(executor_registry.executor_available(config, 'litellm', which=which))
        self.assertTrue(executor_registry.executor_available(config, 'rule-agent', which=which))
        self.assertFalse(executor_registry.executor_available(config, 'opencode', which=which))

    def test_watchdog_engine_no_longer_exposes_executor_availability_wrappers(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'codex_bin_available'))
        self.assertFalse(hasattr(WatchdogEngine, 'opencode_bin_available'))


if __name__ == '__main__':
    unittest.main()
