from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from watchdog_v2.flows import legacy_run
from watchdog_v2.run_context import RUN_CONTEXT_FIELDS, RunContext


class FlowEngineDouble:
    def __init__(self) -> None:
        object.__setattr__(
            self,
            'config',
            SimpleNamespace(
                watchdog_enable_service_level_probe=False,
                watchdog_service_level_failure_threshold=2,
                watchdog_maintenance_file=Path('state/maintenance.flag'),
            ),
        )
        object.__setattr__(self, 'ctx', RunContext.initial(stable_required_runs=2))
        object.__setattr__(self, 'log_records', [])
        object.__setattr__(self, 'state_records', [])
        object.__setattr__(self, 'run_state_writes', [])
        object.__setattr__(self, 'backed_up', False)

    def __getattr__(self, name: str):
        if name in RUN_CONTEXT_FIELDS:
            return getattr(self.ctx, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name != 'ctx' and name in RUN_CONTEXT_FIELDS:
            setattr(self.ctx, name, value)
            return
        object.__setattr__(self, name, value)

    def write_run_state(self, payload: dict[str, object]) -> None:
        self.run_state_writes.append(payload)

    def log(self, level: str, message: str) -> None:
        self.log_records.append((level, message))

    def live_probe(self, *, include_doctor: bool, apply_grace: bool) -> dict[str, object]:
        return {
            'doctor_output': '',
            'config_invalid': False,
            'process_layer_healthy': True,
            'service_layer_healthy': True,
            'service_active': True,
            'service_main_pid': '123',
            'listener_pids': ['456'],
            'service_probe_summary': 'ok',
            'service_probe_checked_at': '2026-03-11T10:00:00+08:00',
            'service_probe_rc': 0,
            'doctor_rc': 0,
        }

    def read_run_state(self) -> dict[str, object]:
        return {}

    def current_mode(self, *, maintenance: bool, degraded: bool = False, survival: bool = False) -> str:
        return 'degraded' if degraded else 'normal'

    def codex_cooldown_remaining(self) -> int:
        return 0

    def backup_last_good(self, validation: dict[str, object] | None = None) -> None:
        self.backed_up = True

    def set_state(self, state: str, summary: str) -> None:
        self.state_records.append((state, summary))

    def now_iso(self) -> str:
        return '2026-03-11T10:00:00+08:00'


class LegacyFlowTest(unittest.TestCase):
    def test_healthy_probe_short_circuits_without_remediation(self) -> None:
        engine = FlowEngineDouble()

        outcome = legacy_run.run(engine, engine.ctx)

        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.state, 'healthy')
        self.assertEqual(outcome.summary, 'service active and listener matches service process tree')
        self.assertTrue(engine.backed_up)
        self.assertIn(('healthy', 'service active and listener matches service process tree'), engine.state_records)
        self.assertGreaterEqual(len(engine.run_state_writes), 3)


if __name__ == '__main__':
    unittest.main()
