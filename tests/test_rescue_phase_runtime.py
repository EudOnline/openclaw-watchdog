from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from openclaw_watchdog.rescue_dispatch import DispatchResult
from openclaw_watchdog.rescue_models import RescueAction, RescueAttempt, RescueContext, RescuePlan, RescueResult
from openclaw_watchdog.run_context import RunContext


class RescuePhaseRuntimeTests(unittest.TestCase):
    def _engine(self):
        return SimpleNamespace(
            config=SimpleNamespace(
                watchdog_rescue_knowledge_root=Path('knowledge'),
            ),
            ctx=RunContext.initial(stable_required_runs=2),
            finalize_recovery_tracking=Mock(),
        )

    def _failed_state(self):
        from openclaw_watchdog.flows.recovery_probe_runtime import RecoveryPhaseState

        return RecoveryPhaseState(
            probe={'conversation_status': 'down'},
            config_invalid=False,
            health_level='failed',
        )

    def _degraded_state(self):
        from openclaw_watchdog.flows.recovery_probe_runtime import RecoveryPhaseState

        return RecoveryPhaseState(
            probe={
                'conversation_status': 'minimal',
                'minimal_usable_ready': True,
                'conversation_ready': False,
                'conversation_probe_summary': 'minimal conversation remains available',
            },
            config_invalid=False,
            health_level='degraded',
        )

    def test_run_rescue_phase_builds_dispatches_executes_and_marks_ctx(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._engine()
        state = self._failed_state()
        context = RescueContext(incident_id='incident-1', health_level='failed', available_executors=('litellm', 'rule-agent'))
        plan = RescuePlan(
            plan_id='plan-litellm',
            diagnosis='litellm fallback',
            actions=[
                RescueAction(
                    kind='update_openclaw_config',
                    params={
                        'file': '/tmp/openclaw.json',
                        'path': 'channels.qqbot.enabled',
                        'value': False,
                    },
                )
            ],
            validations=['minimal_usable_ready'],
        )
        dispatch_result = DispatchResult(
            executor_order=['codex', 'litellm'],
            final_executor='litellm',
            attempts=[
                RescueAttempt(executor='codex', status='no-plan'),
                RescueAttempt(executor='litellm', status='plan-generated', plan_id='plan-litellm'),
            ],
            plan=plan,
        )
        plan_result = RescueResult(status='applied', executor='litellm', plan_id='plan-litellm')
        recovered_state = self._degraded_state()
        outcome = RunOutcome(exit_code=0, state='recovered', summary='litellm restored minimal usability')

        with patch('openclaw_watchdog.rescue_context_builder.build_rescue_context', return_value=context) as context_mock:
            with patch('openclaw_watchdog.rescue_runtime.dispatch_rescue', return_value=dispatch_result) as dispatch_mock:
                with patch('openclaw_watchdog.rescue_runtime.execute_rescue_plan', return_value=plan_result) as execute_mock:
                    with patch('openclaw_watchdog.health.live_probe', return_value={'minimal_usable_ready': True}) as live_probe_mock:
                        with patch.object(recovery_probe_runtime, 'phase_state_from_probe', return_value=recovered_state) as phase_state_mock:
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                return_value=outcome,
                            ) as finalize_mock:
                                from openclaw_watchdog.flows import rescue_phase_runtime

                                result = rescue_phase_runtime.run_rescue_phase(engine, engine.ctx, state)

        self.assertEqual(result, outcome)
        context_mock.assert_called_once_with(engine, state.probe)
        dispatch_mock.assert_called_once_with(engine, context)
        execute_mock.assert_called_once_with(engine, plan, executor='litellm')
        live_probe_mock.assert_called_once_with(engine, include_doctor=False, apply_grace=True)
        phase_state_mock.assert_called_once_with(engine, {'minimal_usable_ready': True}, config_invalid=False)
        finalize_mock.assert_called_once_with(
            engine,
            strategy='litellm',
            recovery_kind='rescue',
            state=recovered_state,
            context=context,
            dispatch_result=dispatch_result,
            plan_result=plan_result,
        )
        self.assertEqual(engine.ctx.rescue_attempt_count, 2)
        self.assertEqual(engine.ctx.rescue_attempt_order, ['codex', 'litellm'])
        self.assertEqual(engine.ctx.rescue_rejected_executors, ['codex:no-plan'])
        self.assertEqual(engine.ctx.rescue_executor_selected, 'litellm')
        self.assertTrue(engine.ctx.rescue_plan_generated)
        self.assertEqual(engine.ctx.rescue_plan_source, 'litellm')
        self.assertEqual(engine.ctx.rescue_plan_id, 'plan-litellm')
        self.assertEqual(engine.ctx.rescue_plan_status, 'applied')
        self.assertEqual(engine.ctx.rescue_mutation_scope, ['update_openclaw_config'])
        self.assertEqual(engine.ctx.rescue_tier, 'litellm')

    def test_run_rescue_phase_records_failure_learning_when_plan_is_rolled_back(self) -> None:
        from openclaw_watchdog.engine import RunOutcome

        engine = self._engine()
        state = self._failed_state()
        context = RescueContext(incident_id='incident-1', health_level='failed', available_executors=('rule-agent',))
        plan = RescuePlan(
            plan_id='plan-rule-agent',
            diagnosis='rule fallback',
            actions=[RescueAction(kind='restart_service', params={})],
            validations=['minimal_usable_ready'],
        )
        dispatch_result = DispatchResult(final_executor='rule-agent', plan=plan)
        rolled_back_result = RescueResult(status='rolled-back', executor='rule-agent', plan_id='plan-rule-agent', rollback_performed=True)
        failure_outcome = RunOutcome(exit_code=1, state='failed', summary='rolled back')

        with patch('openclaw_watchdog.rescue_context_builder.build_rescue_context', return_value=context):
            with patch('openclaw_watchdog.rescue_runtime.dispatch_rescue', return_value=dispatch_result):
                with patch('openclaw_watchdog.rescue_runtime.execute_rescue_plan', return_value=rolled_back_result):
                    with patch(
                        'openclaw_watchdog.rescue_learning_service.record_learning_from_failure',
                        return_value={
                            'case_ingest_result': 'recorded:rollback-case.json',
                            'candidate_rule_status': 'negative-evidence-recorded',
                        },
                    ) as learning_mock:
                        with patch(
                            'openclaw_watchdog.flows.recovery_finalize_runtime.finalize_failure',
                            return_value=failure_outcome,
                        ) as finalize_failure_mock:
                            from openclaw_watchdog.flows import rescue_phase_runtime

                            result = rescue_phase_runtime.run_rescue_phase(engine, engine.ctx, state)

        self.assertEqual(result, failure_outcome)
        self.assertEqual(engine.ctx.rescue_plan_status, 'rolled-back')
        self.assertEqual(engine.ctx.case_ingest_result, 'recorded:rollback-case.json')
        self.assertEqual(engine.ctx.candidate_rule_status, 'negative-evidence-recorded')
        self.assertEqual(engine.ctx.rescue_learning_summary, 'recorded:rollback-case.json / negative-evidence-recorded')
        learning_mock.assert_called_once()
        self.assertEqual(learning_mock.call_args.kwargs['recovery_kind'], 'rescue')
        self.assertEqual(getattr(learning_mock.call_args.kwargs['plan_result'], 'status', ''), 'rolled-back')
        finalize_failure_mock.assert_called_once_with(
            engine,
            summary='rescue plan failed validation and was rolled back',
        )

    def test_run_rescue_phase_records_positive_learning_on_successful_rescue(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._engine()
        state = self._failed_state()
        context = RescueContext(incident_id='incident-1', health_level='failed', available_executors=('rule-agent',))
        plan = RescuePlan(
            plan_id='plan-rule-agent',
            diagnosis='rule fallback',
            actions=[RescueAction(kind='restart_service', params={})],
            validations=['minimal_usable_ready'],
        )
        dispatch_result = DispatchResult(final_executor='rule-agent', plan=plan)
        plan_result = RescueResult(status='applied', executor='rule-agent', plan_id='plan-rule-agent')
        recovered_state = self._degraded_state()

        with patch('openclaw_watchdog.rescue_context_builder.build_rescue_context', return_value=context):
            with patch('openclaw_watchdog.rescue_runtime.dispatch_rescue', return_value=dispatch_result):
                with patch('openclaw_watchdog.rescue_runtime.execute_rescue_plan', return_value=plan_result):
                    with patch('openclaw_watchdog.health.live_probe', return_value={'minimal_usable_ready': True}):
                        with patch.object(recovery_probe_runtime, 'phase_state_from_probe', return_value=recovered_state):
                            with patch(
                                'openclaw_watchdog.rescue_learning_service.record_learning_from_recovery',
                                return_value={
                                    'case_ingest_result': 'recorded:case.json',
                                    'candidate_rule_status': 'candidate-recorded',
                                },
                            ) as learning_mock:
                                with patch('openclaw_watchdog.state_transition.set_state') as set_state_mock:
                                    with patch('openclaw_watchdog.last_good_runtime.backup_last_good') as backup_mock:
                                        from openclaw_watchdog.flows import rescue_phase_runtime

                                        outcome = rescue_phase_runtime.run_rescue_phase(engine, engine.ctx, state)

        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.state, 'recovered')
        self.assertEqual(outcome.summary, 'minimal conversation remains available')
        learning_mock.assert_called_once()
        self.assertEqual(learning_mock.call_args.kwargs['strategy'], 'rule-agent')
        self.assertEqual(learning_mock.call_args.kwargs['recovery_kind'], 'rescue')
        self.assertEqual(engine.ctx.case_ingest_result, 'recorded:case.json')
        self.assertEqual(engine.ctx.candidate_rule_status, 'candidate-recorded')
        self.assertEqual(engine.ctx.rescue_learning_summary, 'recorded:case.json / candidate-recorded')
        engine.finalize_recovery_tracking.assert_called_once_with(strategy='rule-agent', restored_conversation=False)
        set_state_mock.assert_called_once_with(
            engine,
            'recovered',
            'minimal conversation remains available',
            health_level_override='degraded',
        )
        backup_mock.assert_not_called()

    def test_run_rescue_phase_records_failure_learning_when_rescue_is_exhausted(self) -> None:
        from openclaw_watchdog.engine import RunOutcome

        engine = self._engine()
        state = self._failed_state()
        context = RescueContext(incident_id='incident-1', health_level='failed', available_executors=('rule-agent',))
        dispatch_result = DispatchResult(
            executor_order=['rule-agent'],
            final_executor='rule-agent',
            attempts=[RescueAttempt(executor='rule-agent', status='no-plan')],
            plan=None,
        )
        failure_outcome = RunOutcome(exit_code=1, state='failed', summary='exhausted')

        with patch('openclaw_watchdog.rescue_context_builder.build_rescue_context', return_value=context):
            with patch('openclaw_watchdog.rescue_runtime.dispatch_rescue', return_value=dispatch_result):
                with patch(
                    'openclaw_watchdog.rescue_learning_service.record_learning_from_failure',
                    return_value={
                        'case_ingest_result': 'recorded:failure-case.json',
                        'candidate_rule_status': 'negative-evidence-recorded',
                    },
                ) as learning_mock:
                    with patch(
                        'openclaw_watchdog.flows.recovery_finalize_runtime.finalize_failure',
                        return_value=failure_outcome,
                    ) as finalize_failure_mock:
                        from openclaw_watchdog.flows import rescue_phase_runtime

                        result = rescue_phase_runtime.run_rescue_phase(engine, engine.ctx, state)

        self.assertEqual(result, failure_outcome)
        self.assertFalse(engine.ctx.rescue_plan_generated)
        self.assertEqual(engine.ctx.rescue_attempt_count, 1)
        self.assertEqual(engine.ctx.rescue_rejected_executors, ['rule-agent:no-plan'])
        self.assertEqual(engine.ctx.case_ingest_result, 'recorded:failure-case.json')
        self.assertEqual(engine.ctx.candidate_rule_status, 'negative-evidence-recorded')
        learning_mock.assert_called_once()
        self.assertIsNone(learning_mock.call_args.kwargs['plan_result'])
        finalize_failure_mock.assert_called_once_with(
            engine,
            summary='rescue flow exhausted without restoring minimal usability',
        )


if __name__ == '__main__':
    unittest.main()
