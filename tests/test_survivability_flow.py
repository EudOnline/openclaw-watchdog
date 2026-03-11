from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from watchdog_v2.flows import survivability_run
from watchdog_v2.run_context import RunContext


class FlowEngineDouble:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            watchdog_enable_service_level_probe=False,
            watchdog_service_level_failure_threshold=2,
            watchdog_maintenance_file=Path('state/maintenance.flag'),
        )
        self.ctx = RunContext.initial(stable_required_runs=2)
        self.log_records = []
        self.state_records = []
        self.run_state_writes = []
        self.sync_calls = []
        self.recovery_calls = []
        self.backed_up = False
        self.ctx.survival_mode_active = False

    def write_run_state(self, payload: dict[str, object]) -> None:
        self.run_state_writes.append(payload)

    def log(self, level: str, message: str) -> None:
        self.log_records.append((level, message))

    def reset_recovery_tracking(self) -> None:
        self.ctx.recovery_steps = []
        self.ctx.last_recovery_strategy = 'none'
        self.ctx.last_recovery_action_count = 0
        self.ctx.last_recovery_restored_conversation = False

    def last_good_status(self) -> dict[str, object]:
        return {
            'last_good_validated_at': '2026-03-11T09:50:00+08:00',
            'last_good_generation_id': 'gen-2',
            'last_good_generation_count': 2,
        }

    def live_probe(self, *, include_doctor: bool, apply_grace: bool) -> dict[str, object]:
        return {
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
            'service_probe_summary': 'ok',
            'conversation_probe_summary': 'ready',
            'service_probe_checked_at': '2026-03-11T10:00:00+08:00',
            'doctor_rc': 0,
        }

    def sync_survival_mode(self, *, probe: dict[str, object], config_invalid: bool) -> None:
        self.sync_calls.append((probe['conversation_status'], config_invalid))

    def read_run_state(self) -> dict[str, object]:
        return {}

    def _service_probe_failures_for(self, probe: dict[str, object], previous_failures: int) -> int:
        return 0

    def _write_probe_run_state(self, probe: dict[str, object], *, config_invalid: bool, service_probe_failures: int) -> str:
        self.run_state_writes.append({'probe_summary': probe.get('service_probe_summary', ''), 'config_invalid': config_invalid, 'service_probe_failures': service_probe_failures})
        return 'healthy'

    def finalize_recovery_tracking(self, *, strategy: str, restored_conversation: bool) -> None:
        self.recovery_calls.append((strategy, restored_conversation))
        self.ctx.last_recovery_strategy = strategy
        self.ctx.last_recovery_restored_conversation = restored_conversation

    def backup_last_good(self, validation: dict[str, object] | None = None) -> None:
        self.backed_up = True

    def set_state(self, state: str, summary: str) -> None:
        self.state_records.append((state, summary))


class SurvivabilityFlowTest(unittest.TestCase):
    def test_conversation_ready_probe_returns_healthy(self) -> None:
        engine = FlowEngineDouble()

        outcome = survivability_run.run(engine, engine.ctx)

        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.state, 'healthy')
        self.assertEqual(outcome.summary, 'conversation ready and gateway listener healthy')
        self.assertEqual(engine.sync_calls, [('ready', False)])
        self.assertIn(('steady-state', True), engine.recovery_calls)
        self.assertTrue(engine.backed_up)
        self.assertIn(('healthy', 'conversation ready and gateway listener healthy'), engine.state_records)
        self.assertEqual(engine.ctx.last_recovery_strategy, 'steady-state')
        self.assertGreaterEqual(len(engine.run_state_writes), 3)


if __name__ == '__main__':
    unittest.main()
