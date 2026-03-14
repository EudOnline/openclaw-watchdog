from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class RecoveryFinalizeRuntimeTests(unittest.TestCase):
    def _build_engine(self):
        return SimpleNamespace(
            ctx=SimpleNamespace(
                case_ingest_result='not-run',
                candidate_rule_status='none',
                rescue_learning_summary='',
            ),
        )

    def test_refresh_last_good_if_ready_only_runs_when_conversation_is_ready(self) -> None:
        from openclaw_watchdog.flows import recovery_finalize_runtime

        engine = self._build_engine()

        with patch(
            'openclaw_watchdog.flows.recovery_finalize_runtime.last_good_runtime.backup_last_good'
        ) as backup_mock:
            recovery_finalize_runtime.refresh_last_good_if_ready(engine, {'conversation_ready': False})
            recovery_finalize_runtime.refresh_last_good_if_ready(engine, {'conversation_ready': True})

        backup_mock.assert_called_once_with(engine, validation={'conversation_ready': True})

    def test_maybe_finalize_recovery_returns_none_for_failed_state(self) -> None:
        from openclaw_watchdog.flows import recovery_finalize_runtime
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine()
        state = recovery_probe_runtime.RecoveryPhaseState(
            probe={'conversation_ready': False},
            config_invalid=False,
            health_level='failed',
        )

        with patch(
            'openclaw_watchdog.flows.recovery_finalize_runtime.record_learning_from_recovery'
        ) as learning_mock:
            outcome = recovery_finalize_runtime.maybe_finalize_recovery(
                engine,
                strategy='restart',
                recovery_kind='deterministic',
                state=state,
            )

        self.assertIsNone(outcome)
        learning_mock.assert_not_called()

    def test_maybe_finalize_recovery_records_learning_and_returns_recovered_outcome(self) -> None:
        from openclaw_watchdog.flows import recovery_finalize_runtime
        from openclaw_watchdog.flows import recovery_probe_runtime

        engine = self._build_engine()
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
            'openclaw_watchdog.flows.recovery_finalize_runtime.record_learning_from_recovery',
            return_value={
                'case_ingest_result': 'recorded:case.json',
                'candidate_rule_status': 'candidate-recorded',
            },
        ) as learning_mock:
            with patch(
                'openclaw_watchdog.flows.recovery_finalize_runtime.state_transition.set_state'
            ) as set_state_mock:
                with patch(
                    'openclaw_watchdog.flows.recovery_finalize_runtime.recovery_tracking.finalize'
                ) as finalize_mock:
                    outcome = recovery_finalize_runtime.maybe_finalize_recovery(
                        engine,
                        strategy='restart',
                        recovery_kind='deterministic',
                        state=state,
                    )

        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.state, 'recovered')
        self.assertEqual(outcome.summary, 'minimal conversation remains available')
        self.assertEqual(engine.ctx.case_ingest_result, 'recorded:case.json')
        self.assertEqual(engine.ctx.candidate_rule_status, 'candidate-recorded')
        self.assertEqual(engine.ctx.rescue_learning_summary, 'recorded:case.json / candidate-recorded')
        learning_mock.assert_called_once()
        finalize_mock.assert_called_once_with(engine.ctx, strategy='restart', restored_conversation=False)
        set_state_mock.assert_called_once_with(
            engine,
            'recovered',
            'minimal conversation remains available',
            health_level_override='degraded',
        )

    def test_finalize_failure_sets_failed_state_and_summary(self) -> None:
        from openclaw_watchdog.flows import recovery_finalize_runtime

        engine = self._build_engine()

        with patch(
            'openclaw_watchdog.flows.recovery_finalize_runtime.state_transition.set_state'
        ) as set_state_mock:
            with patch(
                'openclaw_watchdog.flows.recovery_finalize_runtime.recovery_tracking.finalize'
            ) as finalize_mock:
                outcome = recovery_finalize_runtime.finalize_failure(engine, summary='rescue exhausted')

        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(outcome.state, 'failed')
        self.assertEqual(outcome.summary, 'rescue exhausted')
        finalize_mock.assert_called_once_with(engine.ctx, strategy='failed', restored_conversation=False)
        set_state_mock.assert_called_once_with(
            engine,
            'failed',
            'rescue exhausted',
            health_level_override='failed',
        )


if __name__ == '__main__':
    unittest.main()
