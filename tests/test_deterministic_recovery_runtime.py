from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch


class DeterministicRecoveryRuntimeTests(unittest.TestCase):
    def _initial_state(self):
        from openclaw_watchdog.flows.recovery_probe_runtime import RecoveryPhaseState

        return RecoveryPhaseState(
            probe={'conversation_status': 'down'},
            config_invalid=False,
            health_level='failed',
        )

    def _phase_state(self, *, health_level: str, minimal_usable_ready: bool = False, conversation_ready: bool = False):
        from openclaw_watchdog.flows.recovery_probe_runtime import RecoveryPhaseState

        return RecoveryPhaseState(
            probe={
                'conversation_status': 'ready' if conversation_ready else 'minimal' if minimal_usable_ready else 'down',
                'minimal_usable_ready': minimal_usable_ready,
                'conversation_ready': conversation_ready,
            },
            config_invalid=False,
            health_level=health_level,
        )

    def _build_engine(self, *, doctor_enabled: bool = True, model_failover_enabled: bool = False):
        engine = SimpleNamespace(
            config=SimpleNamespace(
                watchdog_enable_doctor_repair=doctor_enabled,
                watchdog_enable_survival_mode=False,
                watchdog_enable_model_http_error_failover=model_failover_enabled,
            ),
            record_recovery_step=Mock(),
            enter_survival_mode=Mock(return_value={'applied': False}),
        )
        return engine

    def test_restart_reprobes_and_returns_early_when_usability_is_restored(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine()
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        restart_state = self._phase_state(health_level='degraded', minimal_usable_ready=True)
        outcome = RunOutcome(exit_code=0, state='recovered', summary='restart restored minimal usability')

        with patch('openclaw_watchdog.health.live_probe', return_value={'minimal_usable_ready': True}) as live_probe_mock:
            with patch.object(recovery_probe_runtime, 'phase_state_from_probe', return_value=restart_state) as phase_state_mock:
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup') as pre_backup_mock:
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', return_value=True) as restart_mock:
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good') as rollback_mock:
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                return_value=outcome,
                            ) as finalize_mock:
                                from openclaw_watchdog.flows import deterministic_recovery_runtime

                                result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(result, outcome)
        self.assertEqual(final_state, restart_state)
        pre_backup_mock.assert_called_once_with(engine)
        restart_mock.assert_called_once_with(engine)
        rollback_mock.assert_not_called()
        live_probe_mock.assert_called_once_with(engine, include_doctor=False, apply_grace=True)
        phase_state_mock.assert_called_once_with(
            engine,
            {'minimal_usable_ready': True},
            config_invalid=False,
        )
        finalize_mock.assert_called_once_with(
            engine,
            strategy='restart',
            recovery_kind='deterministic',
            state=restart_state,
        )
        engine.record_recovery_step.assert_called_once_with('restart', 'applied', '')

    def test_rollback_restarts_service_after_restore_and_can_finish_recovery(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine()
        ctx = SimpleNamespace(config_drift_detected=True)
        initial_state = self._initial_state()
        restart_state = self._phase_state(health_level='failed')
        rollback_state = self._phase_state(health_level='degraded', minimal_usable_ready=True)
        outcome = RunOutcome(exit_code=0, state='recovered', summary='rollback restored minimal usability')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}]) as live_probe_mock:
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[restart_state, rollback_state],
            ) as phase_state_mock:
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', return_value=True) as restart_mock:
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=True) as rollback_mock:
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                side_effect=[None, outcome],
                            ) as finalize_mock:
                                from openclaw_watchdog.flows import deterministic_recovery_runtime

                                result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(result, outcome)
        self.assertEqual(final_state, rollback_state)
        self.assertEqual(live_probe_mock.call_count, 2)
        self.assertEqual(phase_state_mock.call_count, 2)
        rollback_mock.assert_called_once_with(engine, reason='drift-auto-rollback')
        self.assertEqual(restart_mock.call_count, 2)
        self.assertEqual(
            finalize_mock.call_args_list,
            [
                call(engine, strategy='restart', recovery_kind='deterministic', state=restart_state),
                call(engine, strategy='rollback', recovery_kind='deterministic', state=rollback_state),
            ],
        )
        self.assertEqual(
            engine.record_recovery_step.call_args_list,
            [
                call('restart', 'applied', ''),
                call('rollback', 'applied', ''),
            ],
        )

    def test_successful_rollback_reprobe_clears_stale_config_invalid_flag(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine()
        ctx = SimpleNamespace(config_drift_detected=True)
        initial_state = self._initial_state()
        initial_state.config_invalid = True
        restart_state = self._phase_state(health_level='failed')
        restart_state.config_invalid = True
        rollback_state = self._phase_state(health_level='healthy', conversation_ready=True, minimal_usable_ready=True)

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}]):
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[restart_state, rollback_state],
            ) as phase_state_mock:
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', return_value=True):
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=True):
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                side_effect=[None, object()],
                            ):
                                from openclaw_watchdog.flows import deterministic_recovery_runtime

                                deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(
            phase_state_mock.call_args_list,
            [
                call(engine, {}, config_invalid=True),
                call(engine, {}, config_invalid=False),
            ],
        )

    def test_model_failover_runs_between_restart_and_rollback_and_can_finish_recovery(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine(model_failover_enabled=True)
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        restart_state = self._phase_state(health_level='failed')
        model_failover_state = self._phase_state(health_level='degraded', minimal_usable_ready=True)
        outcome = RunOutcome(exit_code=0, state='recovered', summary='model failover restored minimal usability')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}]) as live_probe_mock:
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[restart_state, model_failover_state],
            ) as phase_state_mock:
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', side_effect=[False, True]) as restart_mock:
                        with patch('openclaw_watchdog.flows.deterministic_recovery_runtime.model_failover_runtime.apply_model_http_error_failover', return_value={'applied': True, 'status': 'applied', 'summary': 'switched primary model'}) as failover_mock:
                            with patch('openclaw_watchdog.rollback_runtime.restore_last_good') as rollback_mock:
                                with patch(
                                    'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                    side_effect=[None, outcome],
                                ) as finalize_mock:
                                    from openclaw_watchdog.flows import deterministic_recovery_runtime

                                    result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(result, outcome)
        self.assertEqual(final_state, model_failover_state)
        self.assertEqual(live_probe_mock.call_count, 2)
        self.assertEqual(phase_state_mock.call_count, 2)
        self.assertEqual(restart_mock.call_count, 2)
        failover_mock.assert_called_once_with(engine)
        rollback_mock.assert_not_called()
        self.assertEqual(
            finalize_mock.call_args_list,
            [
                call(engine, strategy='restart', recovery_kind='deterministic', state=restart_state),
                call(engine, strategy='model-failover', recovery_kind='deterministic', state=model_failover_state),
            ],
        )
        self.assertEqual(
            engine.record_recovery_step.call_args_list,
            [
                call('restart', 'failed', ''),
                call('model-failover', 'applied', 'switched primary model'),
            ],
        )

    def test_survival_branch_runs_before_doctor_and_can_end_recovery(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine()
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        restart_state = self._phase_state(health_level='failed')
        rollback_state = self._phase_state(health_level='failed')
        survival_state = self._phase_state(health_level='degraded', minimal_usable_ready=True)
        outcome = RunOutcome(exit_code=0, state='recovered', summary='survival restored minimal usability')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}, {}]):
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[restart_state, rollback_state, survival_state],
            ):
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', return_value=False):
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=False):
                            with patch(
                                'openclaw_watchdog.flows.deterministic_recovery_runtime.survival_transition_runtime.enter_survival_mode',
                                return_value={'applied': True},
                            ) as survival_mock:
                                with patch(
                                    'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                    side_effect=[None, None, outcome],
                                ) as finalize_mock:
                                    with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair') as doctor_mock:
                                        from openclaw_watchdog.flows import deterministic_recovery_runtime

                                        result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(result, outcome)
        self.assertEqual(final_state, survival_state)
        engine.enter_survival_mode.assert_not_called()
        survival_mock.assert_called_once_with(engine, reason='rescue-flow')
        doctor_mock.assert_not_called()
        self.assertEqual(
            engine.record_recovery_step.call_args_list,
            [
                call('restart', 'failed', ''),
                call('rollback', 'failed', ''),
                call('survival', 'applied', ''),
            ],
        )
        self.assertEqual(finalize_mock.call_count, 3)

    def test_survival_recovery_restarts_service_before_reprobe(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine()
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        restart_state = self._phase_state(health_level='failed')
        rollback_state = self._phase_state(health_level='failed')
        survival_state = self._phase_state(health_level='degraded', minimal_usable_ready=True)
        outcome = RunOutcome(exit_code=0, state='recovered', summary='survival restored minimal usability')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}, {}]):
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[restart_state, rollback_state, survival_state],
            ):
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', side_effect=[False, True]) as restart_mock:
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=False):
                            with patch(
                                'openclaw_watchdog.flows.deterministic_recovery_runtime.survival_transition_runtime.enter_survival_mode',
                                return_value={'applied': True},
                            ):
                                with patch(
                                    'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                    side_effect=[None, None, outcome],
                                ):
                                    with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair') as doctor_mock:
                                        from openclaw_watchdog.flows import deterministic_recovery_runtime

                                        result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(result, outcome)
        self.assertEqual(final_state, survival_state)
        self.assertEqual(restart_mock.call_count, 2)
        doctor_mock.assert_not_called()

    def test_survival_branch_uses_transition_owner_when_engine_wrapper_is_absent(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = SimpleNamespace(
            config=SimpleNamespace(watchdog_enable_doctor_repair=False),
            record_recovery_step=Mock(),
        )
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        restart_state = self._phase_state(health_level='failed')
        rollback_state = self._phase_state(health_level='failed')
        survival_state = self._phase_state(health_level='degraded', minimal_usable_ready=True)
        outcome = RunOutcome(exit_code=0, state='recovered', summary='survival restored minimal usability')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}, {}]):
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[restart_state, rollback_state, survival_state],
            ):
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', return_value=False):
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=False):
                            with patch(
                                'openclaw_watchdog.flows.deterministic_recovery_runtime.survival_transition_runtime.enter_survival_mode',
                                return_value={'applied': True},
                            ) as survival_mock:
                                with patch(
                                    'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                    side_effect=[None, None, outcome],
                                ):
                                    from openclaw_watchdog.flows import deterministic_recovery_runtime

                                    result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(result, outcome)
        self.assertEqual(final_state, survival_state)
        survival_mock.assert_called_once_with(engine, reason='rescue-flow')
        self.assertEqual(
            engine.record_recovery_step.call_args_list,
            [
                call('restart', 'failed', ''),
                call('rollback', 'failed', ''),
                call('survival', 'applied', ''),
            ],
        )

    def test_doctor_runs_when_enabled_after_all_other_steps_fail(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine(doctor_enabled=True)
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        failed_state = self._phase_state(health_level='failed')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}, {}, {}]):
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[failed_state, failed_state, failed_state, failed_state],
            ):
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', return_value=False):
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=False):
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                side_effect=[None, None, None, None],
                            ):
                                with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair') as doctor_mock:
                                    from openclaw_watchdog.flows import deterministic_recovery_runtime

                                    result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertIsNone(result)
        self.assertEqual(final_state, failed_state)
        doctor_mock.assert_called_once_with(engine)
        self.assertEqual(
            engine.record_recovery_step.call_args_list,
            [
                call('restart', 'failed', ''),
                call('rollback', 'failed', ''),
                call('survival', 'failed', ''),
                call('doctor', 'applied', ''),
            ],
        )

    def test_doctor_failure_does_not_restart_service_or_reprobe(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine(doctor_enabled=True)
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        failed_state = self._phase_state(health_level='failed')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}, {}]) as live_probe_mock:
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[failed_state, failed_state, failed_state],
            ) as phase_state_mock:
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', return_value=False) as restart_mock:
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=False):
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                side_effect=[None, None, None],
                            ) as finalize_mock:
                                with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair', return_value=False) as doctor_mock:
                                    from openclaw_watchdog.flows import deterministic_recovery_runtime

                                    result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertIsNone(result)
        self.assertEqual(final_state, failed_state)
        doctor_mock.assert_called_once_with(engine)
        self.assertEqual(restart_mock.call_count, 1)
        self.assertEqual(live_probe_mock.call_count, 3)
        self.assertEqual(phase_state_mock.call_count, 3)
        self.assertEqual(finalize_mock.call_count, 3)
        self.assertEqual(
            engine.record_recovery_step.call_args_list,
            [
                call('restart', 'failed', ''),
                call('rollback', 'failed', ''),
                call('survival', 'failed', ''),
                call('doctor', 'failed', ''),
            ],
        )

    def test_doctor_reprobes_and_can_finish_recovery_when_repair_restores_conversation(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine(doctor_enabled=True)
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        failed_state = self._phase_state(health_level='failed')
        recovered_state = self._phase_state(health_level='healthy', conversation_ready=True, minimal_usable_ready=True)
        outcome = RunOutcome(exit_code=0, state='recovered', summary='doctor restored conversation')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}, {}, {}]) as live_probe_mock:
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[failed_state, failed_state, failed_state, recovered_state],
            ) as phase_state_mock:
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', side_effect=[False, True]) as restart_mock:
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=False):
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                side_effect=[None, None, None, outcome],
                            ) as finalize_mock:
                                with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair') as doctor_mock:
                                    from openclaw_watchdog.flows import deterministic_recovery_runtime

                                    result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(result, outcome)
        self.assertEqual(final_state, recovered_state)
        doctor_mock.assert_called_once_with(engine)
        self.assertEqual(restart_mock.call_count, 2)
        self.assertEqual(live_probe_mock.call_count, 4)
        self.assertEqual(phase_state_mock.call_count, 4)
        self.assertEqual(finalize_mock.call_count, 4)
        self.assertEqual(
            engine.record_recovery_step.call_args_list,
            [
                call('restart', 'failed', ''),
                call('rollback', 'failed', ''),
                call('survival', 'failed', ''),
                call('doctor', 'applied', ''),
            ],
        )

    def test_doctor_reprobe_clears_stale_config_invalid_flag_after_repair(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine(doctor_enabled=True)
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        initial_state.config_invalid = True
        failed_state = self._phase_state(health_level='failed')
        failed_state.config_invalid = True
        recovered_state = self._phase_state(health_level='healthy', conversation_ready=True, minimal_usable_ready=True)

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}, {}, {}]):
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[failed_state, failed_state, failed_state, recovered_state],
            ) as phase_state_mock:
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', side_effect=[False, True]):
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=False):
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                side_effect=[None, None, None, object()],
                            ):
                                with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair'):
                                    from openclaw_watchdog.flows import deterministic_recovery_runtime

                                    deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(
            phase_state_mock.call_args_list,
            [
                call(engine, {}, config_invalid=True),
                call(engine, {}, config_invalid=True),
                call(engine, {}, config_invalid=True),
                call(engine, {}, config_invalid=False),
            ],
        )

    def test_doctor_is_skipped_when_disabled(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine(doctor_enabled=False)
        ctx = SimpleNamespace(config_drift_detected=False)
        initial_state = self._initial_state()
        failed_state = self._phase_state(health_level='failed')

        with patch('openclaw_watchdog.health.live_probe', side_effect=[{}, {}, {}]):
            with patch.object(
                recovery_probe_runtime,
                'phase_state_from_probe',
                side_effect=[failed_state, failed_state, failed_state],
            ):
                with patch('openclaw_watchdog.repair_action_runtime.run_pre_repair_backup'):
                    with patch('openclaw_watchdog.repair_action_runtime.restart_service', return_value=False):
                        with patch('openclaw_watchdog.rollback_runtime.restore_last_good', return_value=False):
                            with patch(
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                side_effect=[None, None, None],
                            ):
                                with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair') as doctor_mock:
                                    from openclaw_watchdog.flows import deterministic_recovery_runtime

                                    result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertIsNone(result)
        self.assertEqual(final_state, failed_state)
        doctor_mock.assert_not_called()
        self.assertEqual(
            engine.record_recovery_step.call_args_list,
            [
                call('restart', 'failed', ''),
                call('rollback', 'failed', ''),
                call('survival', 'failed', ''),
                call('doctor', 'skipped', ''),
            ],
        )


if __name__ == '__main__':
    unittest.main()
