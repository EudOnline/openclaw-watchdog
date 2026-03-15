from __future__ import annotations

import unittest
from pathlib import Path

from openclaw_watchdog.rescue_models import RescueAction, RescueContext, RescuePlan
from openclaw_watchdog.runtime import CommandResult


class StubAdapter:
    def __init__(self, name: str, *, available: bool, plan: RescuePlan | None = None) -> None:
        self.name = name
        self._available = available
        self._plan = plan

    def is_available(self, context: RescueContext) -> bool:
        return self._available

    def propose_plan(self, context: RescueContext) -> RescuePlan | None:
        return self._plan


class FailingAdapter(StubAdapter):
    def __init__(self, name: str, *, available: bool, error: Exception) -> None:
        super().__init__(name, available=available, plan=None)
        self._error = error

    def propose_plan(self, context: RescueContext) -> RescuePlan | None:
        raise self._error


class RescueDispatchTests(unittest.TestCase):
    def test_dispatch_tries_executors_in_priority_order(self) -> None:
        from openclaw_watchdog.rescue_dispatch import RescueDispatcher

        context = RescueContext(incident_id='incident-1', available_executors=('codex', 'gemini-cli', 'rule-agent'))
        dispatcher = RescueDispatcher(
            adapters=[
                StubAdapter('codex', available=True, plan=None),
                StubAdapter('claude-code', available=False, plan=None),
                StubAdapter('gemini-cli', available=True, plan=None),
                StubAdapter(
                    'rule-agent',
                    available=True,
                    plan=RescuePlan(
                        plan_id='plan-rule',
                        diagnosis='offline fallback',
                        actions=[RescueAction(kind='restart_service', params={})],
                        validations=['minimal_usable_ready'],
                    ),
                ),
            ]
        )

        attempt = dispatcher.dispatch(context)

        self.assertEqual(attempt.executor_order, ['codex', 'gemini-cli', 'rule-agent'])
        self.assertEqual(attempt.final_executor, 'rule-agent')

    def test_dispatch_skips_unavailable_tools_without_install(self) -> None:
        from openclaw_watchdog.rescue_dispatch import RescueDispatcher

        context = RescueContext(incident_id='incident-2', available_executors=('rule-agent',))
        dispatcher = RescueDispatcher(
            adapters=[
                StubAdapter('codex', available=False, plan=None),
                StubAdapter('claude-code', available=False, plan=None),
                StubAdapter('gemini-cli', available=False, plan=None),
                StubAdapter('opencode', available=False, plan=None),
                StubAdapter('litellm', available=False, plan=None),
                StubAdapter(
                    'rule-agent',
                    available=True,
                    plan=RescuePlan(
                        plan_id='plan-local',
                        diagnosis='local fallback',
                        actions=[RescueAction(kind='restart_service', params={})],
                        validations=['minimal_usable_ready'],
                    ),
                ),
            ]
        )

        attempt = dispatcher.dispatch(context)

        self.assertEqual(attempt.final_executor, 'rule-agent')
        self.assertFalse(attempt.installed_anything)

    def test_dispatch_rejects_unsafe_config_mutation_plan_and_falls_through(self) -> None:
        from openclaw_watchdog.rescue_dispatch import RescueDispatcher

        allowed_file = Path('~/.openclaw/openclaw.json').expanduser()
        context = RescueContext(
            incident_id='incident-3',
            available_executors=('litellm', 'rule-agent'),
            editable_paths=(str(allowed_file),),
            editable_keys=('channels',),
        )
        dispatcher = RescueDispatcher(
            adapters=[
                StubAdapter(
                    'litellm',
                    available=True,
                    plan=RescuePlan(
                        plan_id='plan-unsafe',
                        diagnosis='mutate disallowed namespace',
                        actions=[
                            RescueAction(
                                kind='update_openclaw_config',
                                params={
                                    'file': str(allowed_file),
                                    'path': 'secrets.api_key',
                                    'value': 'nope',
                                },
                            )
                        ],
                        validations=['minimal_usable_ready'],
                    ),
                ),
                StubAdapter(
                    'rule-agent',
                    available=True,
                    plan=RescuePlan(
                        plan_id='plan-safe',
                        diagnosis='restart locally',
                        actions=[RescueAction(kind='restart_service', params={})],
                        validations=['minimal_usable_ready'],
                    ),
                ),
            ]
        )

        attempt = dispatcher.dispatch(context)

        self.assertEqual(attempt.final_executor, 'rule-agent')
        self.assertEqual(attempt.plan.plan_id, 'plan-safe')
        self.assertEqual(attempt.attempts[0].executor, 'litellm')
        self.assertEqual(attempt.attempts[0].status, 'unsafe-plan')
        self.assertIn('secrets.api_key', attempt.attempts[0].error)

    def test_dispatch_continues_after_adapter_parse_failure(self) -> None:
        from openclaw_watchdog.rescue_dispatch import RescueDispatcher

        context = RescueContext(incident_id='incident-parse-failure', available_executors=('opencode', 'rule-agent'))
        dispatcher = RescueDispatcher(
            adapters=[
                FailingAdapter('opencode', available=True, error=ValueError('unexpected top-level keys: unexpected')),
                StubAdapter(
                    'rule-agent',
                    available=True,
                    plan=RescuePlan(
                        plan_id='plan-safe',
                        diagnosis='restart locally',
                        actions=[RescueAction(kind='restart_service', params={})],
                        validations=['minimal_usable_ready'],
                    ),
                ),
            ]
        )

        attempt = dispatcher.dispatch(context)

        self.assertEqual(attempt.final_executor, 'rule-agent')
        self.assertEqual(attempt.attempts[0].executor, 'opencode')
        self.assertEqual(attempt.attempts[0].status, 'error')
        self.assertIn('unexpected top-level keys', attempt.attempts[0].error)

    def test_dispatch_continues_after_real_adapter_returns_malformed_output(self) -> None:
        from openclaw_watchdog.rescue_agents.codex_adapter import CodexAdapter
        from openclaw_watchdog.rescue_dispatch import RescueDispatcher

        runner_calls: list[list[str]] = []

        def runner(args: list[str], **kwargs) -> CommandResult:
            runner_calls.append(list(args))
            return CommandResult(
                args=args,
                returncode=0,
                stdout='{"plan_id":"plan-bad","diagnosis":"missing actions"}',
                stderr='',
            )

        context = RescueContext(incident_id='incident-real-parse-failure', available_executors=('codex', 'rule-agent'))
        dispatcher = RescueDispatcher(
            adapters=[
                CodexAdapter(available=True, runner=runner, timeout_seconds=30, cwd=Path('.')),
                StubAdapter(
                    'rule-agent',
                    available=True,
                    plan=RescuePlan(
                        plan_id='plan-safe',
                        diagnosis='restart locally',
                        actions=[RescueAction(kind='restart_service', params={})],
                        validations=['minimal_usable_ready'],
                    ),
                ),
            ]
        )

        attempt = dispatcher.dispatch(context)

        self.assertEqual(attempt.final_executor, 'rule-agent')
        self.assertEqual(attempt.attempts[0].executor, 'codex')
        self.assertEqual(attempt.attempts[0].status, 'error')
        self.assertIn('actions', attempt.attempts[0].error)
        self.assertEqual(runner_calls[0][:2], ['codex', 'exec'])


if __name__ == '__main__':
    unittest.main()
