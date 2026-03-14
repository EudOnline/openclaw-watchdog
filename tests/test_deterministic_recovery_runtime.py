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

    def _build_engine(self, *, doctor_enabled: bool = True):
        engine = SimpleNamespace(
            config=SimpleNamespace(watchdog_enable_doctor_repair=doctor_enabled),
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

    def test_survival_branch_runs_before_doctor_and_can_end_recovery(self) -> None:
        from openclaw_watchdog.engine import RunOutcome
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine()
        engine.enter_survival_mode.return_value = {'applied': True}
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
                                'openclaw_watchdog.flows.recovery_finalize_runtime.maybe_finalize_recovery',
                                side_effect=[None, None, outcome],
                            ) as finalize_mock:
                                with patch('openclaw_watchdog.repair_action_runtime.run_doctor_repair') as doctor_mock:
                                    from openclaw_watchdog.flows import deterministic_recovery_runtime

                                    result, final_state = deterministic_recovery_runtime.run_deterministic_recovery(engine, ctx, initial_state)

        self.assertEqual(result, outcome)
        self.assertEqual(final_state, survival_state)
        engine.enter_survival_mode.assert_called_once_with(reason='rescue-flow')
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

    def test_doctor_runs_when_enabled_after_all_other_steps_fail(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine(doctor_enabled=True)
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
