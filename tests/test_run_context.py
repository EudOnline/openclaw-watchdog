from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from watchdog_v2.engine import WatchdogEngine
from watchdog_v2.run_context import RunContext
from watchdog_v2 import survival as survival_ops


class RunContextTest(unittest.TestCase):
    def test_initial_context_captures_runtime_defaults(self) -> None:
        ctx = RunContext.initial(stable_required_runs=3)

        self.assertNotEqual(ctx.run_ts, '')
        self.assertEqual(ctx.survival_mode_stable_required_runs, 3)
        self.assertEqual(ctx.pre_repair_backup_result, 'not-run')
        self.assertIsNotNone(ctx.last_run_started_at)
        self.assertIsNotNone(ctx.last_run_finished_at)

    def test_engine_runtime_state_lives_only_under_ctx(self) -> None:
        engine = WatchdogEngine.__new__(WatchdogEngine)
        object.__setattr__(engine, 'ctx', RunContext.initial(stable_required_runs=2))

        engine.ctx.last_recovery_strategy = 'restart'
        engine.ctx.rollback_candidate_used = 'gen-2'
        engine.ctx.incident_id = 'incident-7'

        self.assertEqual(engine.ctx.last_recovery_strategy, 'restart')
        self.assertEqual(engine.ctx.rollback_candidate_used, 'gen-2')
        self.assertEqual(engine.ctx.incident_id, 'incident-7')
        with self.assertRaises(AttributeError):
            _ = engine.last_recovery_strategy
        with self.assertRaises(AttributeError):
            _ = engine.rollback_candidate_used
        with self.assertRaises(AttributeError):
            _ = engine.incident_id


    def test_run_state_service_round_trips_learning_and_attempt_fields(self) -> None:
        from watchdog_v2 import run_state_service

        with tempfile.TemporaryDirectory() as temp_dir:
            run_state_file = Path(temp_dir) / 'run-state.json'
            guard_manifest_file = Path(temp_dir) / 'guard.json'

            written = run_state_service.write_run_state(
                run_state_file,
                {
                    'rescue_attempt_order': ['codex', 'litellm'],
                    'rescue_learning_summary': 'recorded:case-1.json / pending-review',
                    'candidate_rule_status': 'pending-review',
                },
                stable_required_runs=2,
                guard_manifest_file=guard_manifest_file,
            )
            reread = run_state_service.read_run_state(
                run_state_file,
                stable_required_runs=2,
                guard_manifest_file=guard_manifest_file,
            )

        self.assertEqual(written['rescue_attempt_order'], ['codex', 'litellm'])
        self.assertEqual(reread['rescue_learning_summary'], 'recorded:case-1.json / pending-review')
        self.assertEqual(reread['guard_manifest_file'], str(guard_manifest_file))
        self.assertEqual(reread['survival_mode_stable_required_runs'], 2)

    def test_survival_state_applies_into_ctx(self) -> None:
        engine = SimpleNamespace(
            config=SimpleNamespace(
                watchdog_survival_stable_ready_runs=2,
                watchdog_survival_config_file=Path('state/survival.json'),
            ),
            ctx=RunContext.initial(stable_required_runs=2),
        )

        survival_ops._apply_state_to_engine(
            engine,
            {
                'active': True,
                'reason': 'config-invalid',
                'entered_at': '2026-03-11T10:00:00+08:00',
                'summary': 'minimal channels enabled',
                'actions': ['disabled optional channel feishu'],
                'disabled_features': ['channel:feishu'],
                'config_path': 'state/survival.json',
                'sticky': True,
                'sticky_reason': 'waiting for stable full-ready window 0/2',
                'exit_ready': False,
                'exit_policy': 'manual-clear-or-reconfig',
                'exit_blockers': ['minimal conversation not yet usable'],
                'stable_ready_runs': 0,
                'stable_required_runs': 2,
                'manual_clear_required': False,
                'config_changed_away': False,
                'last_exit_at': '',
                'last_exit_reason': '',
                'last_exit_kind': '',
                'last_exit_summary': '',
            },
        )

        self.assertTrue(engine.ctx.survival_mode_active)
        self.assertEqual(engine.ctx.survival_mode_reason, 'config-invalid')
        self.assertEqual(engine.ctx.survival_mode_actions, ['disabled optional channel feishu'])
        self.assertEqual(engine.ctx.survival_mode_exit_blockers, ['minimal conversation not yet usable'])
        self.assertEqual(survival_ops.run_state_fields(engine)['survival_mode_reason'], 'config-invalid')


if __name__ == '__main__':
    unittest.main()
