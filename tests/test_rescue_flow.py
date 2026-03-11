from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from watchdog_v2.rescue_dispatch import DispatchResult
from watchdog_v2.rescue_models import RescueAction, RescueContext, RescuePlan, RescueResult
from watchdog_v2.run_context import RunContext


class FlowEngineDouble:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            watchdog_enable_doctor_repair=True,
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

    def live_probe(self, *, include_doctor: bool, apply_grace: bool) -> dict[str, object]:
        return dict(self._probes.pop(0))

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

    def set_state(self, state: str, summary: str, health_level_override: str | None = None) -> None:
        self.state_records.append((state, summary))




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


class RescueFlowTests(unittest.TestCase):
    def test_deterministic_recovery_records_learning(self) -> None:
        from watchdog_v2.flows import rescue_run

        engine = DeterministicLearningEngineDouble()
        outcome = rescue_run.run(engine, engine.ctx)

        self.assertEqual(outcome.state, 'recovered')
        self.assertEqual(engine.ctx.last_recovery_strategy, 'restart')
        self.assertEqual(engine.learning_calls[0]['strategy'], 'restart')
        self.assertEqual(engine.learning_calls[0]['recovery_kind'], 'deterministic')

    def test_deterministic_repair_runs_before_agent_dispatch(self) -> None:
        from watchdog_v2.flows import rescue_run

        engine = FlowEngineDouble()
        outcome = rescue_run.run(engine, engine.ctx)

        self.assertEqual(engine.calls[:4], ['sync', 'restart', 'rollback', 'survival'])
        self.assertEqual(outcome.state, 'recovered')
        self.assertEqual(engine.last_executor, 'litellm')
        self.assertEqual(engine.ctx.last_recovery_strategy, 'litellm')


if __name__ == '__main__':
    unittest.main()
