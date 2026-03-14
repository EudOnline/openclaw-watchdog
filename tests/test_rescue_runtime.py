from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog.rescue_dispatch import DispatchResult
from openclaw_watchdog.rescue_models import RescueAction, RescueContext, RescuePlan, RescueResult


class RescueRuntimeTest(unittest.TestCase):
    def test_build_rescue_adapters_uses_configured_priority_order(self) -> None:
        from openclaw_watchdog import rescue_runtime

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config = SimpleNamespace(
                watchdog_rescue_knowledge_root=temp_root / 'knowledge',
                watchdog_rescue_executor_priority=('opencode', 'codex', 'rule-agent'),
                watchdog_codex_bin='codex-custom',
                watchdog_codex_timeout_seconds=31,
                watchdog_codex_workdir=temp_root / 'codex',
                watchdog_claude_code_bin='claude',
                watchdog_claude_code_timeout_seconds=32,
                watchdog_claude_code_workdir=temp_root / 'claude',
                watchdog_gemini_cli_bin='gemini',
                watchdog_gemini_cli_timeout_seconds=33,
                watchdog_gemini_cli_workdir=temp_root / 'gemini',
                watchdog_opencode_bin='opencode-custom',
                watchdog_opencode_timeout_seconds=34,
                watchdog_opencode_workdir=temp_root / 'opencode',
                watchdog_litellm_enabled=False,
                watchdog_litellm_model='',
            )
            engine = SimpleNamespace(config=config, run_command=lambda *args, **kwargs: None)
            context = RescueContext(
                incident_id='incident-1',
                health_level='failed',
                available_executors=('opencode', 'codex', 'rule-agent'),
                metadata={'failure_signature': 'process-down', 'process_layer_healthy': False},
            )

            adapters = rescue_runtime.build_rescue_adapters(engine, context)

        self.assertEqual([adapter.name for adapter in adapters], ['opencode', 'codex', 'rule-agent'])
        self.assertEqual(adapters[0].timeout_seconds, 34)
        self.assertEqual(adapters[0].cwd, temp_root / 'opencode')
        self.assertEqual(adapters[1].timeout_seconds, 31)

    def test_runtime_dispatch_and_execute_entrypoints_use_runtime_owners(self) -> None:
        from openclaw_watchdog import rescue_runtime

        engine = SimpleNamespace(config=object())
        context = RescueContext(incident_id='incident-2')
        plan = RescuePlan(
            plan_id='plan-1',
            diagnosis='restart',
            actions=[RescueAction(kind='restart_service', params={})],
            validations=['minimal_usable_ready'],
        )
        dispatch_result = DispatchResult(final_executor='rule-agent', plan=plan)
        rescue_result = RescueResult(status='applied', executor='rule-agent', plan_id='plan-1')

        with patch('openclaw_watchdog.rescue_dispatch.RescueDispatcher.dispatch', return_value=dispatch_result) as dispatch_mock:
            with patch('openclaw_watchdog.rescue_runtime.build_rescue_adapters', return_value=['adapter-a']) as adapters_mock:
                self.assertIs(rescue_runtime.dispatch_rescue(engine, context), dispatch_result)
        with patch('openclaw_watchdog.rescue_actions.RescueActionExecutor.apply_plan', return_value=SimpleNamespace(status='applied', rollback_performed=False, details={})) as apply_mock:
            self.assertEqual(
                rescue_runtime.execute_rescue_plan(engine, plan, executor='rule-agent'),
                rescue_result,
            )

        adapters_mock.assert_called_once_with(engine, context)
        dispatch_mock.assert_called_once_with(context)
        apply_mock.assert_called_once_with(plan)


if __name__ == '__main__':
    unittest.main()
