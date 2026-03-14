from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class RecoveryProbeRuntimeTests(unittest.TestCase):
    def test_probe_state_classifies_failed_healthy_and_degraded(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        self.assertEqual(
            recovery_probe_runtime.probe_state(
                {
                    'process_layer_healthy': True,
                    'conversation_ready': True,
                    'minimal_usable_ready': True,
                },
                config_invalid=True,
            ),
            'failed',
        )
        self.assertEqual(
            recovery_probe_runtime.probe_state(
                {
                    'process_layer_healthy': True,
                    'conversation_ready': True,
                    'minimal_usable_ready': True,
                },
                config_invalid=False,
            ),
            'healthy',
        )
        self.assertEqual(
            recovery_probe_runtime.probe_state(
                {
                    'process_layer_healthy': True,
                    'conversation_ready': False,
                    'minimal_usable_ready': True,
                },
                config_invalid=False,
            ),
            'degraded',
        )

    def test_summary_from_probe_prefers_probe_summaries_before_status(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        summary = recovery_probe_runtime.summary_from_probe(
            {
                'conversation_status': 'down',
                'service_probe_summary': 'service summary',
                'conversation_probe_summary': 'conversation summary',
            },
            fallback='fallback summary',
        )
        self.assertEqual(summary, 'conversation summary')

        service_summary = recovery_probe_runtime.summary_from_probe(
            {
                'conversation_status': 'down',
                'service_probe_summary': 'service summary',
                'conversation_probe_summary': '',
            },
            fallback='fallback summary',
        )
        self.assertEqual(service_summary, 'service summary')

        fallback = recovery_probe_runtime.summary_from_probe({}, fallback='fallback summary')
        self.assertEqual(fallback, 'fallback summary')

    def test_baseline_probe_and_sync_writes_run_state_and_syncs_survival_mode(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        probe = {
            'config_invalid': False,
            'process_layer_healthy': False,
            'conversation_ready': False,
            'minimal_usable_ready': False,
            'conversation_status': 'down',
        }
        engine = SimpleNamespace(
            config=SimpleNamespace(),
            ctx=SimpleNamespace(),
            sync_survival_mode=Mock(),
            read_run_state=Mock(return_value={'service_probe_failures': 1}),
        )

        with patch('openclaw_watchdog.flows.recovery_probe_runtime.health_ops.live_probe', return_value=probe) as live_probe_mock:
            with patch(
                'openclaw_watchdog.flows.recovery_probe_runtime.probe_run_state.service_probe_failures_for',
                return_value=2,
            ) as failures_mock:
                with patch(
                    'openclaw_watchdog.flows.recovery_probe_runtime.probe_run_state.write_probe_run_state',
                    return_value='failed',
                ) as write_mock:
                    state = recovery_probe_runtime.baseline_probe_and_sync(engine)

        self.assertEqual(state.probe, probe)
        self.assertFalse(state.config_invalid)
        self.assertEqual(state.health_level, 'failed')
        live_probe_mock.assert_called_once_with(engine, include_doctor=True, apply_grace=True)
        engine.sync_survival_mode.assert_called_once_with(probe=probe, config_invalid=False)
        failures_mock.assert_called_once_with(engine.config, probe, 1)
        write_mock.assert_called_once_with(
            engine,
            probe,
            config_invalid=False,
            service_probe_failures=2,
        )

    def test_finish_initial_state_returns_healthy_outcome_and_refreshes_last_good(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = SimpleNamespace(
            finalize_recovery_tracking=Mock(),
        )
        state = recovery_probe_runtime.RecoveryPhaseState(
            probe={
                'conversation_ready': True,
                'conversation_probe_summary': 'conversation is ready',
            },
            config_invalid=False,
            health_level='healthy',
        )

        with patch(
            'openclaw_watchdog.flows.recovery_finalize_runtime.refresh_last_good_if_ready'
        ) as refresh_mock:
            with patch(
                'openclaw_watchdog.flows.recovery_probe_runtime.state_transition.set_state'
            ) as set_state_mock:
                outcome = recovery_probe_runtime.finish_initial_state(engine, state)

        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.state, 'healthy')
        self.assertEqual(outcome.summary, 'conversation is ready')
        refresh_mock.assert_called_once_with(engine, state.probe)
        engine.finalize_recovery_tracking.assert_called_once_with(strategy='none', restored_conversation=True)
        set_state_mock.assert_called_once_with(
            engine,
            'healthy',
            'conversation is ready',
            health_level_override='healthy',
        )

    def test_finish_initial_state_returns_degraded_without_refresh(self) -> None:
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = SimpleNamespace(
            finalize_recovery_tracking=Mock(),
        )
        state = recovery_probe_runtime.RecoveryPhaseState(
            probe={
                'conversation_ready': False,
                'minimal_usable_ready': True,
                'conversation_probe_summary': 'minimal conversation remains available',
            },
            config_invalid=False,
            health_level='degraded',
        )

        with patch(
            'openclaw_watchdog.flows.recovery_finalize_runtime.refresh_last_good_if_ready'
        ) as refresh_mock:
            with patch(
                'openclaw_watchdog.flows.recovery_probe_runtime.state_transition.set_state'
            ) as set_state_mock:
                outcome = recovery_probe_runtime.finish_initial_state(engine, state)

        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.state, 'degraded')
        self.assertEqual(outcome.summary, 'minimal conversation remains available')
        refresh_mock.assert_not_called()
        engine.finalize_recovery_tracking.assert_called_once_with(strategy='none', restored_conversation=False)
        set_state_mock.assert_called_once_with(
            engine,
            'degraded',
            'minimal conversation remains available',
            health_level_override='degraded',
        )


if __name__ == '__main__':
    unittest.main()
