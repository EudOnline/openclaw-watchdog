from __future__ import annotations

import unittest

from watchdog_v2.rescue_models import RescueAction, RescueContext, RescuePlan


class StubAdapter:
    def __init__(self, name: str, *, available: bool, plan: RescuePlan | None = None) -> None:
        self.name = name
        self._available = available
        self._plan = plan

    def is_available(self, context: RescueContext) -> bool:
        return self._available

    def propose_plan(self, context: RescueContext) -> RescuePlan | None:
        return self._plan


class RescueDispatchTests(unittest.TestCase):
    def test_dispatch_tries_executors_in_priority_order(self) -> None:
        from watchdog_v2.rescue_dispatch import RescueDispatcher

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
        from watchdog_v2.rescue_dispatch import RescueDispatcher

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


if __name__ == '__main__':
    unittest.main()
