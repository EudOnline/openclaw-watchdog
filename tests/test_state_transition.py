from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from openclaw_watchdog.engine import WatchdogEngine
from openclaw_watchdog.run_context import RunContext


class StateTransitionEngineDouble:
    def __init__(self, temp_dir: str) -> None:
        root = Path(temp_dir)
        self.config = SimpleNamespace(
            watchdog_state_dir=root / 'state',
            watchdog_maintenance_file=root / 'state' / 'maintenance.flag',
            watchdog_last_rollback_summary_file=root / 'state' / 'rollback-summary.txt',
            watchdog_log_file=root / 'state' / 'watchdog.log',
            watchdog_guard_manifest_file=root / 'state' / 'guard.json',
            watchdog_notify_on_degraded=True,
            watchdog_notify_on_recovery=True,
            watchdog_notify_on_failure=True,
            watchdog_survival_stable_ready_runs=2,
        )
        self.config.watchdog_state_dir.mkdir(parents=True, exist_ok=True)
        self.config.watchdog_log_file.write_text('', encoding='utf-8')
        self.last_status_file = root / 'state' / 'last-status'
        self.incident_backup_marker = root / 'state' / 'incident-backup-done'
        self.current_incident_marker = root / 'state' / 'current-incident-id'
        self.ctx = RunContext.initial(stable_required_runs=2)
        self.ctx.run_ts = '2026-03-12 18:20:00 CST'
        self.ctx.pre_repair_backup_result = 'created:backup-1'
        self.ctx.last_recovery_strategy = 'rollback'
        self.ctx.last_recovery_action_count = 2
        self.ctx.last_recovery_restored_conversation = True
        self.ctx.rescue_attempt_count = 1
        self.ctx.rescue_executor_selected = 'rule-agent'
        self.ctx.rescue_plan_generated = True
        self.ctx.rescue_plan_source = 'rule-agent'
        self.ctx.rescue_plan_id = 'plan-1'
        self.ctx.rescue_plan_status = 'applied'
        self.ctx.rescue_tier = 'rule-agent'
        self.ctx.case_ingest_result = 'recorded:case-1.json'
        self.ctx.candidate_rule_status = 'none'
        self.ctx.rescue_attempt_order = ['rule-agent']
        self.ctx.rescue_rejected_executors = ['codex:unavailable']
        self.ctx.rescue_learning_summary = 'recorded:case-1.json / none'
        self.ctx.rescue_mutation_scope = ['restart_service']
        self.ctx.last_good_validated_at = '2026-03-12T18:10:00+08:00'
        self.ctx.last_good_generation_id = 'gen-1'
        self.ctx.last_good_generation_count = 1
        self.ctx.rollback_candidate_used = ''
        self.ctx.rollback_reason = ''
        self.ctx.config_drift_detected = False
        self.ctx.drift_scope = []
        self.ctx.drift_since_last_good = ''
        self.ctx.drift_summary = ''
        self.ctx.latest_probe = {
            'conversation_ready': True,
            'minimal_usable_ready': True,
            'conversation_status': 'ready',
            'conversation_probe_summary': 'ready',
        }
        self.attach_calls = 0
        self.reset_failure_count_calls = 0
        self.updated_incident_states: list[tuple[str, str, bool]] = []
        self.refreshed_indexes: list[tuple[str | None, str | None]] = []
        self.reset_incident_state_calls = 0
        self.run_state_writes: list[dict[str, object]] = []
        self.event_writes: list[tuple[str, str]] = []
        self.notifications: list[str] = []

    def attach_current_incident_if_any(self) -> bool:
        self.attach_calls += 1
        return True

    def current_mode(self, *, maintenance: bool, degraded: bool = False, survival: bool = False) -> str:
        if maintenance:
            return 'maintenance'
        if survival:
            return 'survival'
        if degraded:
            return 'degraded'
        return 'normal'

    def recovery_path_text(self) -> str:
        return 'restart:applied -> rollback:applied'

    def reset_failure_count(self) -> None:
        self.reset_failure_count_calls += 1

    def update_incident_state(self, state: str, summary: str, *, resolved: bool = False) -> None:
        self.updated_incident_states.append((state, summary, resolved))

    def refresh_current_incident_index(self, *, summary: str | None = None, health_level: str | None = None) -> None:
        self.refreshed_indexes.append((summary, health_level))

    def reset_incident_state(self) -> None:
        self.reset_incident_state_calls += 1

    def write_run_state(self, updates: dict[str, object]) -> dict[str, object]:
        self.run_state_writes.append(dict(updates))
        return updates

    def append_rollback_summary(self, text: str) -> str:
        if self.ctx.rollback_summary:
            return f'{text}\n\n回退摘要：\n{self.ctx.rollback_summary}'
        return text

    def notify(self, message: str) -> None:
        self.notifications.append(message)


class StateTransitionTests(unittest.TestCase):
    def test_watchdog_engine_no_longer_exposes_set_state_wrapper(self) -> None:
        self.assertFalse(hasattr(WatchdogEngine, 'set_state'))

    def test_state_transition_reads_survival_fields_from_state_runtime_owner(self) -> None:
        from openclaw_watchdog import state_transition

        with TemporaryDirectory() as temp_dir:
            engine = StateTransitionEngineDouble(temp_dir)
            engine.last_status_file.write_text('healthy', encoding='utf-8')
            engine.ctx.incident_id = 'incident-3'
            engine.ctx.incident_dir = Path(temp_dir) / 'incident-3'
            write_event_mock = Mock(side_effect=lambda probe_engine, status, summary: probe_engine.event_writes.append((status, summary)))
            report_mock = Mock(return_value={'message_text': 'operator summary'})

            with patch('openclaw_watchdog.state_transition.last_good_runtime.guard_status', return_value={'guard_manifest_file': 'guard.json', 'guard_last_operation': 'validate', 'guard_last_phase': 'after', 'guard_last_time': '2026-03-12T18:19:00+08:00', 'guard_last_summary': 'ok'}):
                with patch(
                    'openclaw_watchdog.state_transition.survival_state_runtime.run_state_fields',
                    return_value={'survival_mode_reason': 'owner-state'},
                ) as survival_fields_mock:
                    with patch('openclaw_watchdog.state_transition.incident_service_ops.update_incident_state'):
                        with patch('openclaw_watchdog.state_transition.incident_service_ops.refresh_current_incident_index'):
                            with patch.object(state_transition, 'event_runtime', SimpleNamespace(write_event=write_event_mock), create=True):
                                with patch.object(state_transition, 'reporting_ops', SimpleNamespace(report_payload=report_mock), create=True):
                                    state_transition.set_state(engine, 'failed', 'still down', health_level_override='failed')

        survival_fields_mock.assert_called_once_with(engine)
        self.assertEqual(engine.run_state_writes[-1]['survival_mode_reason'], 'owner-state')

    def test_healthy_transition_resolves_incident_and_clears_context(self) -> None:
        from openclaw_watchdog import state_transition

        with TemporaryDirectory() as temp_dir:
            engine = StateTransitionEngineDouble(temp_dir)
            engine.last_status_file.write_text('failed', encoding='utf-8')
            engine.ctx.incident_id = 'incident-1'
            engine.ctx.incident_dir = Path(temp_dir) / 'incident-1'
            engine.incident_backup_marker.write_text('1', encoding='utf-8')
            write_event_mock = Mock(side_effect=lambda probe_engine, status, summary: probe_engine.event_writes.append((status, summary)))
            report_mock = Mock(return_value={'message_text': 'operator summary'})

            with patch('openclaw_watchdog.state_transition.last_good_runtime.guard_status', return_value={'guard_manifest_file': 'guard.json', 'guard_last_operation': 'validate', 'guard_last_phase': 'after', 'guard_last_time': '2026-03-12T18:19:00+08:00', 'guard_last_summary': 'ok'}):
                with patch('openclaw_watchdog.state_transition.incident_service_ops.attach_current_incident_if_any', return_value=True) as attach_mock:
                    with patch('openclaw_watchdog.state_transition.incident_service_ops.update_incident_state') as update_mock:
                        with patch('openclaw_watchdog.state_transition.incident_service_ops.refresh_current_incident_index') as refresh_mock:
                            with patch('openclaw_watchdog.state_transition.incident_service_ops.reset_incident_state') as reset_mock:
                                with patch.object(state_transition, 'event_runtime', SimpleNamespace(write_event=write_event_mock), create=True):
                                    with patch.object(state_transition, 'reporting_ops', SimpleNamespace(report_payload=report_mock), create=True):
                                        state_transition.set_state(engine, 'healthy', 'all good', health_level_override='healthy')

        attach_mock.assert_called_once_with(engine)
        self.assertEqual(engine.reset_failure_count_calls, 1)
        update_mock.assert_called_once_with(engine, 'resolved', 'all good', resolved=True)
        refresh_mock.assert_called_once_with(engine, summary='all good', health_level='healthy')
        reset_mock.assert_called_once_with(engine)
        write_event_mock.assert_called_once_with(engine, 'healthy', 'all good')
        report_mock.assert_called_once_with(engine, incident_limit=5)
        self.assertFalse(engine.incident_backup_marker.exists())
        self.assertEqual(engine.event_writes, [('healthy', 'all good')])
        self.assertEqual(engine.notifications, [])
        self.assertEqual(engine.run_state_writes[-1]['current_incident_id'], '')
        self.assertEqual(engine.run_state_writes[-1]['current_incident_state'], '')
        self.assertEqual(engine.run_state_writes[-1]['last_success_at'], engine.ctx.run_ts)

    def test_failed_transition_notifies_only_on_state_edge(self) -> None:
        from openclaw_watchdog import state_transition

        with TemporaryDirectory() as temp_dir:
            engine = StateTransitionEngineDouble(temp_dir)
            engine.last_status_file.write_text('healthy', encoding='utf-8')
            engine.ctx.incident_id = 'incident-2'
            engine.ctx.incident_dir = Path(temp_dir) / 'incident-2'
            write_event_mock = Mock(side_effect=lambda probe_engine, status, summary: probe_engine.event_writes.append((status, summary)))
            report_mock = Mock(return_value={'message_text': 'operator summary'})

            with patch('openclaw_watchdog.state_transition.last_good_runtime.guard_status', return_value={'guard_manifest_file': 'guard.json', 'guard_last_operation': 'validate', 'guard_last_phase': 'after', 'guard_last_time': '2026-03-12T18:19:00+08:00', 'guard_last_summary': 'ok'}):
                with patch('openclaw_watchdog.state_transition.incident_service_ops.update_incident_state') as update_mock:
                    with patch('openclaw_watchdog.state_transition.incident_service_ops.refresh_current_incident_index') as refresh_mock:
                        with patch.object(state_transition, 'event_runtime', SimpleNamespace(write_event=write_event_mock), create=True):
                            with patch.object(state_transition, 'reporting_ops', SimpleNamespace(report_payload=report_mock), create=True):
                                state_transition.set_state(engine, 'failed', 'still down', health_level_override='failed')

            update_mock.assert_called_once_with(engine, 'open', 'still down')
            refresh_mock.assert_called_once_with(engine, summary='still down', health_level='failed')
            write_event_mock.assert_called_once_with(engine, 'failed', 'still down')
            report_mock.assert_called_once_with(engine, incident_limit=5)
            self.assertEqual(engine.run_state_writes[-1]['current_incident_id'], 'incident-2')
            self.assertEqual(engine.run_state_writes[-1]['current_incident_state'], 'open')
            self.assertEqual(engine.run_state_writes[-1]['last_failed_at'], engine.ctx.run_ts)
            self.assertEqual(len(engine.notifications), 1)
            self.assertIn('❌ OpenClaw watchdog 状态变化', engine.notifications[0])
            self.assertIn('operator summary', engine.notifications[0])

            engine.notifications.clear()
            with patch('openclaw_watchdog.state_transition.last_good_runtime.guard_status', return_value={'guard_manifest_file': 'guard.json', 'guard_last_operation': 'validate', 'guard_last_phase': 'after', 'guard_last_time': '2026-03-12T18:19:00+08:00', 'guard_last_summary': 'ok'}):
                with patch('openclaw_watchdog.state_transition.incident_service_ops.update_incident_state'):
                    with patch('openclaw_watchdog.state_transition.incident_service_ops.refresh_current_incident_index'):
                        with patch.object(state_transition, 'event_runtime', SimpleNamespace(write_event=write_event_mock), create=True):
                            with patch.object(state_transition, 'reporting_ops', SimpleNamespace(report_payload=report_mock), create=True):
                                state_transition.set_state(engine, 'failed', 'still down', health_level_override='failed')

        self.assertEqual(engine.notifications, [])


if __name__ == '__main__':
    unittest.main()
