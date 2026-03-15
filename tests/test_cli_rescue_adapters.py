from __future__ import annotations

import unittest
from pathlib import Path

from openclaw_watchdog.rescue_models import RescueContext
from openclaw_watchdog.runtime import CommandResult


class FakeRunner:
    def __init__(self, result: CommandResult) -> None:
        self.result = result
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, args: list[str], **kwargs) -> CommandResult:
        self.calls.append((list(args), dict(kwargs)))
        return self.result


class CliRescueAdaptersTest(unittest.TestCase):
    def test_codex_adapter_prefers_last_nonempty_plan_from_noisy_stdout(self) -> None:
        from openclaw_watchdog.rescue_agents.codex_adapter import CodexAdapter

        runner = FakeRunner(
            CommandResult(
                args=['codex'],
                returncode=0,
                stdout=(
                    '{"plan_id":"plan-empty","diagnosis":"no safe plan","actions":[],"validations":["minimal_usable_ready"]}\n'
                    'thinking...\n'
                    '{"plan_id":"plan-codex-final","diagnosis":"codex restart","actions":[{"kind":"restart_service","params":{}}],"validations":["minimal_usable_ready"]}\n'
                ),
                stderr='',
            )
        )
        adapter = CodexAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        plan = adapter.propose_plan(RescueContext(incident_id='incident-last-plan', health_level='failed'))

        self.assertIsNotNone(plan)
        self.assertEqual(plan.plan_id, 'plan-codex-final')
        self.assertEqual(plan.actions[0].kind, 'restart_service')

    def test_codex_adapter_extracts_structured_plan_from_noisy_stdout(self) -> None:
        from openclaw_watchdog.rescue_agents.codex_adapter import CodexAdapter

        runner = FakeRunner(
            CommandResult(
                args=['codex'],
                returncode=0,
                stdout='planning rescue...\n{"plan_id":"plan-codex-noisy","diagnosis":"codex restart","actions":[{"kind":"restart_service","params":{}}],"validations":["minimal_usable_ready"]}\n',
                stderr='',
            )
        )
        adapter = CodexAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        plan = adapter.propose_plan(RescueContext(incident_id='incident-noisy', health_level='failed'))

        self.assertEqual(plan.plan_id, 'plan-codex-noisy')
        self.assertEqual(plan.actions[0].kind, 'restart_service')

    def test_codex_adapter_parses_structured_plan_from_stdout(self) -> None:
        from openclaw_watchdog.rescue_agents.codex_adapter import CodexAdapter

        runner = FakeRunner(
            CommandResult(
                args=['codex'],
                returncode=0,
                stdout='{"plan_id":"plan-codex","diagnosis":"codex restart","actions":[{"kind":"restart_service","params":{}}],"validations":["minimal_usable_ready"]}\n',
                stderr='',
            )
        )
        adapter = CodexAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        plan = adapter.propose_plan(RescueContext(incident_id='incident-1', health_level='failed'))

        self.assertEqual(plan.plan_id, 'plan-codex')
        self.assertEqual(plan.actions[0].kind, 'restart_service')
        self.assertEqual(runner.calls[0][0][:2], ['codex', 'exec'])

    def test_claude_code_adapter_unwraps_nested_response_json(self) -> None:
        from openclaw_watchdog.rescue_agents.claude_code_adapter import ClaudeCodeAdapter

        runner = FakeRunner(
            CommandResult(
                args=['claude'],
                returncode=0,
                stdout='{"response":"{\\"plan_id\\":\\"plan-claude\\",\\"diagnosis\\":\\"claude rollback\\",\\"actions\\":[{\\"kind\\":\\"restore_last_good\\",\\"params\\":{}}],\\"validations\\":[\\"minimal_usable_ready\\"]}"}',
                stderr='',
            )
        )
        adapter = ClaudeCodeAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        plan = adapter.propose_plan(RescueContext(incident_id='incident-2', health_level='failed'))

        self.assertEqual(plan.plan_id, 'plan-claude')
        self.assertEqual(plan.actions[0].kind, 'restore_last_good')
        self.assertEqual(runner.calls[0][0][:2], ['claude', '-p'])

    def test_gemini_adapter_rejects_freeform_shell_payload(self) -> None:
        from openclaw_watchdog.rescue_agents.gemini_cli_adapter import GeminiCliAdapter

        runner = FakeRunner(
            CommandResult(
                args=['gemini'],
                returncode=0,
                stdout='{"response":"{\\"shell\\":\\"rm -rf /\\"}"}',
                stderr='',
            )
        )
        adapter = GeminiCliAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        with self.assertRaises(ValueError):
            adapter.propose_plan(RescueContext(incident_id='incident-3', health_level='failed'))

        self.assertEqual(runner.calls[0][0][:2], ['gemini', '-p'])

    def test_opencode_adapter_rejects_unknown_top_level_keys(self) -> None:
        from openclaw_watchdog.rescue_agents.opencode_adapter import OpenCodeAdapter

        runner = FakeRunner(
            CommandResult(
                args=['opencode'],
                returncode=0,
                stdout='{"plan_id":"plan-opencode","diagnosis":"restart","actions":[{"kind":"restart_service","params":{}}],"validations":["minimal_usable_ready"],"unexpected":"value"}',
                stderr='',
            )
        )
        adapter = OpenCodeAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        with self.assertRaises(ValueError):
            adapter.propose_plan(RescueContext(incident_id='incident-unknown-keys', health_level='failed'))

    def test_opencode_adapter_returns_none_for_empty_actions(self) -> None:
        from openclaw_watchdog.rescue_agents.opencode_adapter import OpenCodeAdapter

        runner = FakeRunner(
            CommandResult(
                args=['opencode'],
                returncode=0,
                stdout='{"plan_id":"plan-empty","diagnosis":"no safe plan","actions":[],"validations":["minimal_usable_ready"]}',
                stderr='',
            )
        )
        adapter = OpenCodeAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        plan = adapter.propose_plan(RescueContext(incident_id='incident-4', health_level='failed'))

        self.assertIsNone(plan)
        self.assertEqual(runner.calls[0][0][:2], ['opencode', 'run'])

    def test_claude_code_adapter_rejects_malformed_action_params(self) -> None:
        from openclaw_watchdog.rescue_agents.claude_code_adapter import ClaudeCodeAdapter

        runner = FakeRunner(
            CommandResult(
                args=['claude'],
                returncode=0,
                stdout=(
                    '{"response":"{\\"plan_id\\":\\"plan-bad\\",\\"diagnosis\\":\\"bad params\\",'
                    '\\"actions\\":[{\\"kind\\":\\"restart_service\\",\\"params\\":[\\"oops\\"]}],'
                    '\\"validations\\":[\\"minimal_usable_ready\\"]}"}'
                ),
                stderr='',
            )
        )
        adapter = ClaudeCodeAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        with self.assertRaises(ValueError):
            adapter.propose_plan(RescueContext(incident_id='incident-bad-params', health_level='failed'))

    def test_gemini_adapter_rejects_payload_missing_actions(self) -> None:
        from openclaw_watchdog.rescue_agents.gemini_cli_adapter import GeminiCliAdapter

        runner = FakeRunner(
            CommandResult(
                args=['gemini'],
                returncode=0,
                stdout='{"plan_id":"plan-missing-actions","diagnosis":"missing actions","validations":["minimal_usable_ready"]}',
                stderr='',
            )
        )
        adapter = GeminiCliAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        with self.assertRaises(ValueError):
            adapter.propose_plan(RescueContext(incident_id='incident-missing-actions', health_level='failed'))

    def test_claude_code_adapter_prefers_nested_plan_over_wrapper_metadata(self) -> None:
        from openclaw_watchdog.rescue_agents.claude_code_adapter import ClaudeCodeAdapter

        runner = FakeRunner(
            CommandResult(
                args=['claude'],
                returncode=0,
                stdout=(
                    '{"content":"{\\"plan_id\\":\\"plan-nested\\",\\"diagnosis\\":\\"nested restart\\",'
                    '\\"actions\\":[{\\"kind\\":\\"restart_service\\",\\"params\\":{}}],'
                    '\\"validations\\":[\\"minimal_usable_ready\\"]}","risk_level":"low"}'
                ),
                stderr='',
            )
        )
        adapter = ClaudeCodeAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.'))

        plan = adapter.propose_plan(RescueContext(incident_id='incident-wrapper-metadata', health_level='failed'))

        self.assertIsNotNone(plan)
        self.assertEqual(plan.plan_id, 'plan-nested')
        self.assertEqual(plan.risk_level, 'medium')


if __name__ == '__main__':
    unittest.main()
