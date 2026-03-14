from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from openclaw_watchdog.rescue_dispatch import DispatchResult
from openclaw_watchdog.rescue_models import RescueAction, RescueContext, RescuePlan, RescueResult
from openclaw_watchdog.run_context import RunContext


class FlowEngineDouble:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            watchdog_enable_doctor_repair=False,
            watchdog_enable_survival_mode=False,
            watchdog_maintenance_file=Path('state/maintenance.flag'),
            watchdog_survival_stable_ready_runs=2,
        )
        self.ctx = RunContext.initial(stable_required_runs=2)
        self.calls: list[str] = []
        self.state_records: list[tuple[str, str]] = []
        self._probes = [
            {
                'doctor_output': '',
                'config_invalid': False,
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
                'service_probe_summary': 'down',
                'conversation_probe_summary': 'down',
                'service_probe_checked_at': '2026-03-11T10:00:00+08:00',
                'doctor_rc': 0,
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': True,
                'service_layer_healthy': True,
                'conversation_ready': False,
                'minimal_usable_ready': True,
                'conversation_status': 'minimal',
                'service_active': True,
                'service_main_pid': '123',
                'listener_pids': ['456'],
            },
        ]
        self.last_executor = ''

    def log(self, level: str, message: str) -> None:
        pass

    def reset_recovery_tracking(self) -> None:
        self.ctx.recovery_steps = []
        self.ctx.last_recovery_strategy = 'none'
        self.ctx.last_recovery_action_count = 0
        self.ctx.last_recovery_restored_conversation = False

    def refresh_drift_context(self) -> dict[str, object]:
        return {'detected': False, 'scope': [], 'since_last_good': '', 'summary': ''}

    def sync_survival_mode(self, *, probe: dict[str, object], config_invalid: bool) -> None:
        self.calls.append('sync')

    def _service_probe_failures_for(self, probe: dict[str, object], previous_failures: int) -> int:
        return 0

    def _write_probe_run_state(self, probe: dict[str, object], *, config_invalid: bool, service_probe_failures: int) -> str:
        return 'failed'

    def record_recovery_step(self, step: str, outcome: str, detail: str = '') -> None:
        self.calls.append(step)

    def restart_service(self) -> bool:
        return True

    def restore_last_good(self, *, reason: str = '') -> bool:
        return True

    def enter_survival_mode(self, *, reason: str) -> dict[str, object]:
        return {'applied': True}

    def run_doctor_repair(self) -> None:
        self.calls.append('doctor-repair')

    def build_rescue_context(self, probe: dict[str, object]) -> RescueContext:
        return RescueContext(incident_id='incident-1', health_level='failed', available_executors=('litellm', 'rule-agent'))

    def dispatch_rescue(self, context: RescueContext) -> DispatchResult:
        return DispatchResult(
            executor_order=['litellm', 'rule-agent'],
            final_executor='litellm',
            plan=RescuePlan(
                plan_id='plan-litellm',
                diagnosis='litellm fallback',
                actions=[RescueAction(kind='restart_service', params={})],
                validations=['minimal_usable_ready'],
            ),
        )

    def execute_rescue_plan(self, plan: RescuePlan, *, executor: str) -> RescueResult:
        self.last_executor = executor
        return RescueResult(status='applied', executor=executor, plan_id=plan.plan_id)

    def finalize_recovery_tracking(self, *, strategy: str, restored_conversation: bool) -> None:
        self.ctx.last_recovery_strategy = strategy
        self.ctx.last_recovery_restored_conversation = restored_conversation

    def read_run_state(self) -> dict[str, object]:
        return getattr(self, '_run_state', {})

    def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
        state = dict(getattr(self, '_run_state', {}))
        state.update(updates)
        self._run_state = state
        return state

    def now_iso(self) -> str:
        return '2026-03-11T10:00:00+08:00'

    def current_mode(self, *, maintenance: bool, degraded: bool = False, survival: bool = False) -> str:
        if maintenance:
            return 'maintenance'
        if survival:
            return 'survival'
        if degraded:
            return 'degraded'
        return 'normal'




class DeterministicLearningEngineDouble(FlowEngineDouble):
    def __init__(self) -> None:
        super().__init__()
        self._probes = [
            {
                'doctor_output': '',
                'config_invalid': False,
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
                'service_probe_summary': 'down',
                'conversation_probe_summary': 'down',
                'service_probe_checked_at': '2026-03-11T10:00:00+08:00',
                'doctor_rc': 0,
            },
            {
                'process_layer_healthy': True,
                'service_layer_healthy': True,
                'conversation_ready': False,
                'minimal_usable_ready': True,
                'conversation_status': 'minimal',
                'service_active': True,
                'service_main_pid': '123',
                'listener_pids': ['456'],
            },
        ]
        self.learning_calls = []

    def record_learning_from_recovery(self, **payload):
        self.learning_calls.append(payload)
        return {'case_ingest_result': 'recorded:restart-case.json', 'candidate_rule_status': 'none'}




class ValidationRollbackFlowEngineDouble(FlowEngineDouble):
    def __init__(self) -> None:
        super().__init__()
        self._probes = [
            {
                'doctor_output': '',
                'config_invalid': False,
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
                'service_probe_summary': 'down',
                'conversation_probe_summary': 'down',
                'service_probe_checked_at': '2026-03-11T10:00:00+08:00',
                'doctor_rc': 0,
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': True,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': True,
                'conversation_status': 'minimal',
                'service_active': True,
                'service_main_pid': '123',
                'listener_pids': ['456'],
            },
        ]

    def execute_rescue_plan(self, plan: RescuePlan, *, executor: str) -> RescueResult:
        self.last_executor = executor
        return RescueResult(status='rolled-back', executor=executor, plan_id=plan.plan_id, rollback_performed=True)


class ExhaustedAfterAppliedPlanFlowEngineDouble(FlowEngineDouble):
    def __init__(self) -> None:
        super().__init__()
        self._probes = [
            {
                'doctor_output': '',
                'config_invalid': False,
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
                'service_probe_summary': 'down',
                'conversation_probe_summary': 'down',
                'service_probe_checked_at': '2026-03-11T10:00:00+08:00',
                'doctor_rc': 0,
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
        ]


class DriftAwareFlowEngineDouble(FlowEngineDouble):
    def refresh_drift_context(self) -> dict[str, object]:
        self.ctx.config_drift_detected = True
        self.ctx.drift_scope = ['openclaw_config']
        self.ctx.drift_since_last_good = 'generation=gen-1 validated_at=2026-03-11T10:00:00+08:00'
        self.ctx.drift_summary = 'protected paths changed since last-good: openclaw_config'
        return {
            'detected': True,
            'scope': list(self.ctx.drift_scope),
            'since_last_good': self.ctx.drift_since_last_good,
            'summary': self.ctx.drift_summary,
        }


class RollbackRestartAfterRestoreEngineDouble(FlowEngineDouble):
    def __init__(self) -> None:
        super().__init__()
        self._probes = [
            {
                'doctor_output': '',
                'config_invalid': False,
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
                'service_probe_summary': 'down',
                'conversation_probe_summary': 'down',
                'service_probe_checked_at': '2026-03-11T10:00:00+08:00',
                'doctor_rc': 0,
            },
            {
                'process_layer_healthy': False,
                'service_layer_healthy': False,
                'conversation_ready': False,
                'minimal_usable_ready': False,
                'conversation_status': 'down',
                'service_active': False,
                'service_main_pid': '0',
                'listener_pids': [],
            },
            {
                'process_layer_healthy': True,
                'service_layer_healthy': True,
                'conversation_ready': False,
                'minimal_usable_ready': True,
                'conversation_status': 'minimal',
                'service_active': True,
                'service_main_pid': '123',
                'listener_pids': ['456'],
            },
        ]

    def refresh_drift_context(self) -> dict[str, object]:
        self.ctx.config_drift_detected = True
        self.ctx.drift_scope = ['openclaw_config']
        self.ctx.drift_since_last_good = 'generation=gen-1'
        self.ctx.drift_summary = 'protected paths changed since last-good: openclaw_config'
        return {
            'detected': True,
            'scope': ['openclaw_config'],
            'since_last_good': 'generation=gen-1',
            'summary': self.ctx.drift_summary,
        }


class HealthyBaselineBackupEngineDouble(FlowEngineDouble):
    def __init__(self) -> None:
        super().__init__()
        self.backup_calls: list[dict[str, object]] = []
        self._probes = [
            {
                'doctor_output': '',
                'config_invalid': False,
                'process_layer_healthy': True,
                'service_layer_healthy': True,
                'conversation_ready': True,
                'minimal_usable_ready': True,
                'conversation_status': 'ready',
                'service_active': True,
                'service_main_pid': '123',
                'listener_pids': ['456'],
                'service_probe_summary': 'gateway.reachable=true',
                'conversation_probe_summary': 'ready',
                'service_probe_checked_at': '2026-03-11T10:00:00+08:00',
                'doctor_rc': 0,
                'health_level': 'healthy',
            },
        ]

    def backup_last_good(self, *, validation: dict[str, object] | None = None) -> None:
        self.backup_calls.append(dict(validation or {}))


class RecoveryTrackingHelpersTest(unittest.TestCase):
    def test_recovery_tracking_helper_keeps_action_count_and_path_order(self) -> None:
        from openclaw_watchdog import recovery_tracking

        ctx = RunContext.initial(stable_required_runs=2)
        recovery_tracking.reset(ctx, stable_required_runs=2)
        recovery_tracking.record_step(ctx, 'restart', 'applied')
        recovery_tracking.record_step(ctx, 'doctor', 'skipped')
        recovery_tracking.record_step(ctx, 'rollback', 'failed', 'missing-last-good')
        recovery_tracking.finalize(ctx, strategy='litellm', restored_conversation=False)

        self.assertEqual(ctx.last_recovery_action_count, 2)
        self.assertEqual(recovery_tracking.path_text(ctx), 'restart:applied -> doctor:skipped -> rollback:failed(missing-last-good)')
        self.assertEqual(ctx.last_recovery_strategy, 'litellm')
        self.assertFalse(ctx.last_recovery_restored_conversation)

class RescueFlowTests(unittest.TestCase):
    def _run_flow(self, engine):
        from openclaw_watchdog.flows import rescue_run

        def _next_probe(probe_engine, *, include_doctor: bool, apply_grace: bool) -> dict[str, object]:
            probes = getattr(probe_engine, '_probes', [])
            if probes:
                return dict(probes.pop(0))
            return {}

        set_state_mock = Mock(
            side_effect=lambda probe_engine, state, summary, health_level_override=None: probe_engine.state_records.append((state, summary))
        )
        backup_last_good_mock = Mock(
            side_effect=lambda probe_engine, validation=None: getattr(probe_engine, 'backup_last_good', lambda **kwargs: None)(validation=validation)
        )
        restore_last_good_mock = Mock(
            side_effect=lambda probe_engine, reason='': getattr(probe_engine, 'restore_last_good', lambda **kwargs: False)(reason=reason)
        )
        pre_repair_backup_mock = Mock(
            side_effect=lambda probe_engine: getattr(probe_engine, 'run_pre_repair_backup', lambda: None)()
        )
        restart_service_mock = Mock(
            side_effect=lambda probe_engine: getattr(probe_engine, 'restart_service', lambda: False)()
        )
        doctor_repair_mock = Mock(
            side_effect=lambda probe_engine: getattr(probe_engine, 'run_doctor_repair', lambda: None)()
        )
        sync_survival_mock = Mock(
            side_effect=lambda probe_engine, *, probe, config_invalid: (
                getattr(probe_engine, 'sync_survival_mode', lambda **kwargs: None)(probe=probe, config_invalid=config_invalid)
            )
        )
        enter_survival_mock = Mock(
            side_effect=lambda probe_engine, *, reason: (
                getattr(probe_engine, 'enter_survival_mode', lambda **kwargs: {'applied': False})(reason=reason)
            )
        )
        with patch('openclaw_watchdog.health.live_probe', side_effect=_next_probe):
            with patch('openclaw_watchdog.state_transition.set_state', set_state_mock):
                with patch('openclaw_watchdog.last_good_runtime.backup_last_good', backup_last_good_mock):
                    with patch('openclaw_watchdog.rollback_runtime.restore_last_good', restore_last_good_mock):
                        with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup', pre_repair_backup_mock):
                            with patch('openclaw_watchdog.repair_action_runtime.restart_service', restart_service_mock):
                                with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair', doctor_repair_mock):
                                    with patch('openclaw_watchdog.flows.recovery_probe_runtime.survival_transition_runtime.sync_survival_mode', sync_survival_mock):
                                        with patch('openclaw_watchdog.flows.deterministic_recovery_runtime.survival_transition_runtime.enter_survival_mode', enter_survival_mock):
                                            outcome = rescue_run.run(engine, engine.ctx)
        self.assertTrue(set_state_mock.called)
        return outcome

    def test_rescue_run_uses_direct_module_owners_when_engine_wrappers_are_absent(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        class WrapperlessFlowEngineDouble:
            def __init__(self) -> None:
                self.config = SimpleNamespace(
                    watchdog_enable_doctor_repair=False,
                    watchdog_maintenance_file=Path('state/maintenance.flag'),
                    watchdog_rescue_knowledge_root=Path('knowledge'),
                    watchdog_survival_stable_ready_runs=2,
                )
                self.ctx = RunContext.initial(stable_required_runs=2)
                self.state_records: list[tuple[str, str]] = []
                self._run_state: dict[str, object] = {}
                self._probes = [
                    {
                        'config_invalid': False,
                        'process_layer_healthy': False,
                        'service_layer_healthy': False,
                        'conversation_ready': False,
                        'minimal_usable_ready': False,
                        'conversation_status': 'down',
                        'service_active': False,
                        'service_main_pid': '0',
                        'listener_pids': [],
                    },
                    {
                        'process_layer_healthy': False,
                        'service_layer_healthy': False,
                        'conversation_ready': False,
                        'minimal_usable_ready': False,
                        'conversation_status': 'down',
                        'service_active': False,
                        'service_main_pid': '0',
                        'listener_pids': [],
                    },
                    {
                        'process_layer_healthy': False,
                        'service_layer_healthy': False,
                        'conversation_ready': False,
                        'minimal_usable_ready': False,
                        'conversation_status': 'down',
                        'service_active': False,
                        'service_main_pid': '0',
                        'listener_pids': [],
                    },
                    {
                        'process_layer_healthy': False,
                        'service_layer_healthy': False,
                        'conversation_ready': False,
                        'minimal_usable_ready': False,
                        'conversation_status': 'down',
                        'service_active': False,
                        'service_main_pid': '0',
                        'listener_pids': [],
                    },
                    {
                        'process_layer_healthy': True,
                        'service_layer_healthy': True,
                        'conversation_ready': False,
                        'minimal_usable_ready': True,
                        'conversation_status': 'minimal',
                        'service_active': True,
                        'service_main_pid': '123',
                        'listener_pids': ['456'],
                    },
                ]

            def log(self, level: str, message: str) -> None:
                return None

            def sync_survival_mode(self, *, probe: dict[str, object], config_invalid: bool) -> None:
                return None

            def record_recovery_step(self, step: str, outcome: str, detail: str = '') -> None:
                return None

            def enter_survival_mode(self, *, reason: str) -> dict[str, object]:
                return {'applied': False}

            def read_run_state(self) -> dict[str, object]:
                return dict(self._run_state)

            def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
                self._run_state.update(updates)
                return dict(self._run_state)

            def now_iso(self) -> str:
                return '2026-03-11T10:00:00+08:00'

            def current_mode(self, *, maintenance: bool, degraded: bool = False, survival: bool = False) -> str:
                if maintenance:
                    return 'maintenance'
                if survival:
                    return 'survival'
                if degraded:
                    return 'degraded'
                return 'normal'

        engine = WrapperlessFlowEngineDouble()
        context = RescueContext(incident_id='incident-2', health_level='failed', available_executors=('rule-agent',))
        plan = RescuePlan(
            plan_id='plan-rule',
            diagnosis='rule fallback',
            actions=[RescueAction(kind='restart_service', params={})],
            validations=['minimal_usable_ready'],
        )
        dispatch_result = DispatchResult(final_executor='rule-agent', plan=plan)
        pre_backup_mock = Mock()
        restart_mock = Mock(return_value=False)
        restore_mock = Mock(return_value=False)
        doctor_mock = Mock()
        reset_tracking_mock = Mock(side_effect=lambda ctx, *, stable_required_runs: setattr(ctx, 'recovery_steps', []))
        apply_drift_mock = Mock(
            side_effect=lambda current_engine: {
                'detected': False,
                'scope': [],
                'since_last_good': '',
                'summary': '',
            }
        )
        finalize_tracking_mock = Mock(
            side_effect=lambda ctx, *, strategy, restored_conversation: (
                setattr(ctx, 'last_recovery_strategy', strategy),
                setattr(ctx, 'last_recovery_restored_conversation', restored_conversation),
            )
        )

        with patch('openclaw_watchdog.probe_run_state.service_probe_failures_for', return_value=0) as failures_mock:
            with patch('openclaw_watchdog.probe_run_state.write_probe_run_state', return_value='failed') as write_mock:
                with patch('openclaw_watchdog.rescue_context_builder.build_rescue_context', return_value=context) as context_mock:
                    with patch('openclaw_watchdog.rescue_runtime.dispatch_rescue', return_value=dispatch_result) as dispatch_mock:
                        with patch(
                            'openclaw_watchdog.rescue_runtime.execute_rescue_plan',
                            return_value=RescueResult(status='applied', executor='rule-agent', plan_id='plan-rule'),
                        ) as execute_mock:
                            with patch(
                                'openclaw_watchdog.rescue_learning_service.record_learning_from_recovery',
                                return_value={'case_ingest_result': 'recorded:case.json', 'candidate_rule_status': 'candidate-recorded'},
                            ) as learning_mock:
                                with patch(
                                    'openclaw_watchdog.health.live_probe',
                                    side_effect=lambda probe_engine, *, include_doctor, apply_grace: dict(probe_engine._probes.pop(0)),
                                ):
                                    set_state_mock = Mock(
                                        side_effect=lambda probe_engine, state, summary, health_level_override=None: probe_engine.state_records.append((state, summary))
                                    )
                                    with patch('openclaw_watchdog.state_transition.set_state', set_state_mock):
                                        with patch('openclaw_watchdog.flows.rescue_run.recovery_tracking.reset', reset_tracking_mock):
                                            with patch('openclaw_watchdog.flows.rescue_run.last_good_runtime.apply_drift_context', apply_drift_mock):
                                                with patch('openclaw_watchdog.flows.recovery_probe_runtime.recovery_tracking.finalize', finalize_tracking_mock):
                                                    with patch('openclaw_watchdog.flows.recovery_finalize_runtime.recovery_tracking.finalize', finalize_tracking_mock):
                                                        with patch(
                                                            'openclaw_watchdog.flows.recovery_probe_runtime.survival_transition_runtime.sync_survival_mode'
                                                        ) as sync_mock:
                                                            with patch(
                                                                'openclaw_watchdog.flows.deterministic_recovery_runtime.survival_transition_runtime.enter_survival_mode',
                                                                return_value={'applied': False},
                                                            ) as survival_mock:
                                                                with patch('openclaw_watchdog.rollback_runtime.restore_last_good', restore_mock):
                                                                    with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup', pre_backup_mock):
                                                                        with patch('openclaw_watchdog.repair_action_runtime.restart_service', restart_mock):
                                                                            with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair', doctor_mock):
                                                                                outcome = rescue_run.run(engine, engine.ctx)

        self.assertEqual(outcome.state, 'recovered')
        context_mock.assert_called_once()
        dispatch_mock.assert_called_once_with(engine, context)
        execute_mock.assert_called_once_with(engine, plan, executor='rule-agent')
        sync_mock.assert_called_once()
        survival_mock.assert_called_once_with(engine, reason='rescue-flow')
        self.assertTrue(failures_mock.called)
        self.assertTrue(write_mock.called)
        learning_mock.assert_called_once()
        pre_backup_mock.assert_called_once_with(engine)
        self.assertEqual(restart_mock.call_count, 1)
        restore_mock.assert_called_once_with(engine, reason='rescue-flow')
        doctor_mock.assert_not_called()
        reset_tracking_mock.assert_called_once_with(engine.ctx, stable_required_runs=2)
        self.assertTrue(apply_drift_mock.called)
        self.assertTrue(finalize_tracking_mock.called)
        self.assertTrue(set_state_mock.called)

    def test_run_delegates_deterministic_path_to_recovery_phase_helpers(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import rescue_run

        self.assertTrue(hasattr(rescue_run, 'recovery_phases'))

        class MinimalEngine:
            def __init__(self) -> None:
                self.config = SimpleNamespace()
                self.ctx = RunContext.initial(stable_required_runs=2)
                self.run_state_writes: list[dict[str, object]] = []

            def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
                self.run_state_writes.append(dict(updates))
                return updates

            def log(self, level: str, message: str) -> None:
                return None

            def reset_recovery_tracking(self) -> None:
                return None

            def refresh_drift_context(self) -> dict[str, object]:
                return {}

        engine = MinimalEngine()
        baseline_state = SimpleNamespace(probe={'conversation_status': 'down'}, config_invalid=False, health_level='failed')
        deterministic_outcome = RunOutcome(exit_code=0, state='recovered', summary='restart restored minimal usability')

        with patch('openclaw_watchdog.flows.rescue_run.recovery_phases.baseline_probe_and_sync', return_value=baseline_state) as baseline_mock:
            with patch('openclaw_watchdog.flows.rescue_run.recovery_phases.finish_initial_state', return_value=None) as initial_mock:
                with patch('openclaw_watchdog.flows.rescue_run.recovery_phases.run_deterministic_recovery', return_value=(deterministic_outcome, baseline_state)) as deterministic_mock:
                    with patch('openclaw_watchdog.flows.rescue_run.recovery_phases.run_rescue_phase') as rescue_mock:
                        outcome = rescue_run.run(engine, engine.ctx)

        self.assertEqual(outcome, deterministic_outcome)
        baseline_mock.assert_called_once_with(engine)
        initial_mock.assert_called_once_with(engine, baseline_state)
        deterministic_mock.assert_called_once_with(engine, engine.ctx, baseline_state)
        rescue_mock.assert_not_called()

    def test_run_delegates_rescue_path_to_recovery_phase_helpers(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import rescue_run

        self.assertTrue(hasattr(rescue_run, 'recovery_phases'))

        class MinimalEngine:
            def __init__(self) -> None:
                self.config = SimpleNamespace()
                self.ctx = RunContext.initial(stable_required_runs=2)
                self.run_state_writes: list[dict[str, object]] = []

            def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
                self.run_state_writes.append(dict(updates))
                return updates

            def log(self, level: str, message: str) -> None:
                return None

            def reset_recovery_tracking(self) -> None:
                return None

            def refresh_drift_context(self) -> dict[str, object]:
                return {}

        engine = MinimalEngine()
        baseline_state = SimpleNamespace(probe={'conversation_status': 'down'}, config_invalid=False, health_level='failed')
        rescue_outcome = RunOutcome(exit_code=0, state='recovered', summary='rule-agent restored minimal usability')

        with patch('openclaw_watchdog.flows.rescue_run.recovery_phases.baseline_probe_and_sync', return_value=baseline_state) as baseline_mock:
            with patch('openclaw_watchdog.flows.rescue_run.recovery_phases.finish_initial_state', return_value=None) as initial_mock:
                with patch('openclaw_watchdog.flows.rescue_run.recovery_phases.run_deterministic_recovery', return_value=(None, baseline_state)) as deterministic_mock:
                    with patch('openclaw_watchdog.flows.rescue_run.recovery_phases.run_rescue_phase', return_value=rescue_outcome) as rescue_mock:
                        outcome = rescue_run.run(engine, engine.ctx)

        self.assertEqual(outcome, rescue_outcome)
        baseline_mock.assert_called_once_with(engine)
        initial_mock.assert_called_once_with(engine, baseline_state)
        deterministic_mock.assert_called_once_with(engine, engine.ctx, baseline_state)
        rescue_mock.assert_called_once_with(engine, engine.ctx, baseline_state)

    def test_run_uses_last_good_runtime_when_refresh_wrapper_is_absent(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        class IncompleteEngine:
            def __init__(self) -> None:
                self.config = SimpleNamespace(watchdog_survival_stable_ready_runs=2)
                self.ctx = RunContext.initial(stable_required_runs=2)
                self.run_state_writes: list[dict[str, object]] = []

            def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
                self.run_state_writes.append(dict(updates))
                return dict(updates)

            def log(self, level: str, message: str) -> None:
                return None

        engine = IncompleteEngine()
        baseline_state = SimpleNamespace(probe={'conversation_status': 'down'}, config_invalid=False, health_level='failed')

        with patch('openclaw_watchdog.flows.rescue_run.recovery_tracking.reset') as reset_mock:
            with patch(
                'openclaw_watchdog.flows.rescue_run.last_good_runtime.apply_drift_context',
                return_value={},
            ) as drift_mock:
                with patch(
                    'openclaw_watchdog.flows.rescue_run.recovery_phases.baseline_probe_and_sync',
                    return_value=baseline_state,
                ) as baseline_mock:
                    with patch(
                        'openclaw_watchdog.flows.rescue_run.recovery_phases.finish_initial_state',
                        return_value=SimpleNamespace(exit_code=0, state='healthy', summary='ready'),
                    ):
                        outcome = rescue_run.run(engine, engine.ctx)

        self.assertEqual(outcome.state, 'healthy')
        reset_mock.assert_called_once_with(engine.ctx, stable_required_runs=2)
        drift_mock.assert_called_once_with(engine)
        baseline_mock.assert_called_once_with(engine)

    def test_run_calls_phase_helpers_in_order_before_rescue(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import rescue_run

        call_order: list[str] = []

        class MinimalEngine:
            def __init__(self) -> None:
                self.config = SimpleNamespace()
                self.ctx = RunContext.initial(stable_required_runs=2)
                self.run_state_writes: list[dict[str, object]] = []

            def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
                self.run_state_writes.append(dict(updates))
                return updates

            def log(self, level: str, message: str) -> None:
                return None

            def reset_recovery_tracking(self) -> None:
                return None

            def refresh_drift_context(self) -> dict[str, object]:
                return {}

        engine = MinimalEngine()
        baseline_state = SimpleNamespace(probe={'conversation_status': 'down'}, config_invalid=False, health_level='failed')
        rescue_outcome = RunOutcome(exit_code=0, state='recovered', summary='rule-agent restored minimal usability')

        with patch(
            'openclaw_watchdog.flows.rescue_run.recovery_phases.baseline_probe_and_sync',
            side_effect=lambda current_engine: call_order.append('baseline') or baseline_state,
        ):
            with patch(
                'openclaw_watchdog.flows.rescue_run.recovery_phases.finish_initial_state',
                side_effect=lambda current_engine, current_state: call_order.append('initial') or None,
            ):
                with patch(
                    'openclaw_watchdog.flows.rescue_run.recovery_phases.run_deterministic_recovery',
                    side_effect=lambda current_engine, current_ctx, current_state: call_order.append('deterministic') or (None, baseline_state),
                ):
                    with patch(
                        'openclaw_watchdog.flows.rescue_run.recovery_phases.run_rescue_phase',
                        side_effect=lambda current_engine, current_ctx, current_state: call_order.append('rescue') or rescue_outcome,
                    ):
                        outcome = rescue_run.run(engine, engine.ctx)

        self.assertEqual(outcome, rescue_outcome)
        self.assertEqual(call_order, ['baseline', 'initial', 'deterministic', 'rescue'])

    def test_refreshes_drift_context_before_recovery_attempts(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        engine = DriftAwareFlowEngineDouble()
        outcome = self._run_flow(engine)

        self.assertEqual(outcome.state, 'recovered')
        self.assertTrue(engine.ctx.config_drift_detected)
        self.assertEqual(engine.ctx.drift_scope, ['openclaw_config'])
        self.assertIn('generation=gen-1', engine.ctx.drift_since_last_good)

    def test_healthy_window_refreshes_last_good_baseline(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        engine = HealthyBaselineBackupEngineDouble()
        outcome = self._run_flow(engine)

        self.assertEqual(outcome.state, 'healthy')
        self.assertEqual(len(engine.backup_calls), 1)
        self.assertTrue(engine.backup_calls[0]['conversation_ready'])

    def test_drift_recovery_is_attributed_to_rollback_after_restore_restart(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        engine = RollbackRestartAfterRestoreEngineDouble()
        engine.config.watchdog_enable_drift_auto_rollback = True
        outcome = self._run_flow(engine)

        self.assertEqual(outcome.state, 'recovered')
        self.assertEqual(engine.calls[:3], ['sync', 'restart', 'rollback'])
        self.assertEqual(engine.ctx.last_recovery_strategy, 'rollback')

    def test_deterministic_recovery_records_learning(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        engine = DeterministicLearningEngineDouble()
        outcome = self._run_flow(engine)

        self.assertEqual(outcome.state, 'recovered')
        self.assertEqual(engine.ctx.last_recovery_strategy, 'restart')
        self.assertEqual(engine.learning_calls[0]['strategy'], 'restart')
        self.assertEqual(engine.learning_calls[0]['recovery_kind'], 'deterministic')

    def test_failed_validation_marks_rescue_result_as_rolled_back(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        engine = ValidationRollbackFlowEngineDouble()
        engine.config.watchdog_rescue_knowledge_root = Path('tmp/knowledge')
        with patch(
            'openclaw_watchdog.rescue_learning_service.record_learning_from_failure',
            return_value={'case_ingest_result': 'recorded:rollback-case.json', 'candidate_rule_status': 'negative-evidence-recorded'},
        ) as learning_mock:
            outcome = self._run_flow(engine)

        self.assertEqual(engine.ctx.rescue_plan_status, 'rolled-back')
        self.assertEqual(outcome.state, 'failed')
        self.assertEqual(engine.ctx.last_recovery_strategy, 'failed')
        self.assertGreaterEqual(learning_mock.call_count, 1)
        self.assertTrue(
            any(
                call.kwargs.get('recovery_kind') == 'rescue'
                and getattr(call.kwargs.get('plan_result'), 'status', '') == 'rolled-back'
                for call in learning_mock.call_args_list
            )
        )

    def test_applied_rescue_plan_keeps_plan_result_when_flow_still_exhausts(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        engine = ExhaustedAfterAppliedPlanFlowEngineDouble()
        engine.config.watchdog_rescue_knowledge_root = Path('tmp/knowledge')
        with patch(
            'openclaw_watchdog.rescue_learning_service.record_learning_from_failure',
            return_value={'case_ingest_result': 'recorded:applied-failure-case.json', 'candidate_rule_status': 'negative-evidence-recorded'},
        ) as learning_mock:
            outcome = self._run_flow(engine)

        self.assertEqual(outcome.state, 'failed')
        self.assertEqual(engine.ctx.rescue_plan_status, 'applied')
        self.assertGreaterEqual(learning_mock.call_count, 1)
        self.assertTrue(
            any(
                call.kwargs.get('recovery_kind') == 'rescue'
                and getattr(call.kwargs.get('plan_result'), 'status', '') == 'applied'
                and getattr(call.kwargs.get('plan_result'), 'plan_id', '') == 'plan-litellm'
                for call in learning_mock.call_args_list
            )
        )

    def test_deterministic_repair_runs_before_agent_dispatch(self) -> None:
        from openclaw_watchdog.flows import rescue_run

        engine = FlowEngineDouble()
        outcome = self._run_flow(engine)

        self.assertEqual(engine.calls[:4], ['sync', 'restart', 'rollback', 'survival'])
        self.assertEqual(outcome.state, 'recovered')
        self.assertEqual(engine.last_executor, 'litellm')
        self.assertEqual(engine.ctx.last_recovery_strategy, 'litellm')


class WatchdogEngineRescueContextSeamsTest(unittest.TestCase):
    def _build_engine(self, temp_dir: str):
        from openclaw_watchdog.engine import WatchdogEngine

        engine = WatchdogEngine.__new__(WatchdogEngine)
        object.__setattr__(
            engine,
            'config',
            SimpleNamespace(
                watchdog_rescue_knowledge_root=Path(temp_dir) / 'knowledge',
                watchdog_incidents_dir=Path(temp_dir) / 'incidents',
                watchdog_rescue_editable_paths=(str(Path(temp_dir) / 'openclaw.json'),),
                watchdog_rescue_editable_keys=('channels.qqbot.enabled',),
                watchdog_litellm_enabled=False,
                watchdog_litellm_model='',
                watchdog_survival_stable_ready_runs=2,
                watchdog_guard_manifest_file=Path(temp_dir) / 'guard.json',
            ),
        )
        object.__setattr__(engine, 'ctx', RunContext.initial(stable_required_runs=2))
        object.__setattr__(engine, 'run_state_file', Path(temp_dir) / 'run-state.json')
        object.__setattr__(engine, 'current_incident_marker', Path(temp_dir) / 'current-incident-id')
        return engine

    def test_build_rescue_context_keeps_normalized_signature_recent_cases_and_editable_bounds(self) -> None:
        import json
        import tempfile

        from openclaw_watchdog.learning import LearningStore
        from openclaw_watchdog import rescue_context_builder

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self._build_engine(temp_dir)
            store = LearningStore(root=engine.config.watchdog_rescue_knowledge_root)
            store.record_successful_case(
                {
                    'case_id': 'case-a',
                    'failure_signature': 'yaml-parse-error',
                    'config_invalid': True,
                    'status': 'recovered',
                    'executor': 'codex',
                    'strategy': 'codex',
                }
            )
            store.record_case(
                {
                    'case_id': 'case-b',
                    'failure_signature': 'provider-auth-exploded',
                    'config_invalid': True,
                    'status': 'failed',
                    'executor': 'rule-agent',
                    'strategy': 'rule-agent',
                }
            )
            (store.rules_dir / 'config-invalid-auto.json').write_text(
                json.dumps(
                    {
                        'rule_id': 'config-invalid-auto',
                        'match': {'normalized_failure_signature': 'config-invalid'},
                        'diagnosis': 'restore last known good config',
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ) + '\n',
                encoding='utf-8',
            )

            with patch(
                'openclaw_watchdog.executor_registry.executor_available',
                side_effect=lambda config, name, which=None: name == 'rule-agent',
            ):
                context = rescue_context_builder.build_rescue_context(
                    engine,
                    {
                        'config_invalid': True,
                        'process_layer_healthy': True,
                        'service_layer_healthy': True,
                        'minimal_usable_ready': False,
                        'conversation_ready': False,
                        'conversation_status': 'down',
                        'service_active': True,
                    }
                )

        self.assertEqual(context.metadata['failure_signature'], 'config-invalid')
        self.assertEqual(context.metadata['normalized_failure_signature'], 'config-invalid')
        self.assertEqual([case['case_id'] for case in context.metadata['recent_cases']], ['case-a', 'case-b'])
        self.assertEqual(context.metadata['known_rules'][0]['rule_id'], 'config-invalid-auto')
        self.assertEqual(context.available_executors, ('rule-agent',))
        self.assertEqual(context.editable_paths, (str(Path(temp_dir) / 'openclaw.json'),))
        self.assertEqual(context.editable_keys, ('channels.qqbot.enabled',))
        self.assertTrue(context.incident_id)

    def test_build_rescue_context_ignores_legacy_executor_priority_override(self) -> None:
        import tempfile

        from openclaw_watchdog import rescue_context_builder

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self._build_engine(temp_dir)
            engine.config.watchdog_rescue_executor_priority = ('rule-agent', 'opencode', 'codex')

            with patch(
                'openclaw_watchdog.executor_registry.executor_available',
                side_effect=lambda config, name, which=None: name in {'codex', 'opencode', 'rule-agent'},
            ):
                context = rescue_context_builder.build_rescue_context(
                    engine,
                    {
                        'config_invalid': False,
                        'process_layer_healthy': False,
                        'service_layer_healthy': False,
                        'minimal_usable_ready': False,
                        'conversation_ready': False,
                        'conversation_status': 'down',
                        'service_active': False,
                    },
                )

        self.assertEqual(context.available_executors, ('codex', 'opencode', 'rule-agent'))

    def test_build_rescue_context_seeds_current_incident_context_for_new_rescue_flow(self) -> None:
        import tempfile

        from openclaw_watchdog import rescue_context_builder

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self._build_engine(temp_dir)

            with patch(
                'openclaw_watchdog.executor_registry.executor_available',
                side_effect=lambda config, name, which=None: name == 'rule-agent',
            ):
                context = rescue_context_builder.build_rescue_context(
                    engine,
                    {
                        'config_invalid': False,
                        'process_layer_healthy': False,
                        'service_layer_healthy': False,
                        'minimal_usable_ready': False,
                        'conversation_ready': False,
                        'conversation_status': 'down',
                        'service_active': False,
                    },
                )

            self.assertEqual(engine.ctx.incident_id, context.incident_id)
            self.assertEqual(engine.ctx.incident_dir, Path(temp_dir) / 'incidents' / context.incident_id)
            self.assertEqual(engine.current_incident_marker.read_text(encoding='utf-8').strip(), context.incident_id)


if __name__ == '__main__':
    unittest.main()
