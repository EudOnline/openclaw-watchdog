from __future__ import annotations

from pathlib import Path
import unittest


CRITICAL_SCENARIOS = [
    'bootstrap-missing-openclaw',
    'watchdog-rescue-chain-codex',
    'watchdog-rescue-chain-claude-code',
    'watchdog-rescue-chain-gemini-cli',
    'watchdog-rescue-chain-opencode',
    'watchdog-rescue-chain-litellm',
    'watchdog-rescue-chain-rule-agent',
    'watchdog-candidate-rule-auto-promotion',
    'watchdog-candidate-rule-review-pending',
    'watchdog-conversation-probe-ready',
    'watchdog-rollback-priority-before-doctor',
    'watchdog-survival-mode-recovery',
    'watchdog-config-drift-guard',
]

EXTENDED_SCENARIOS = [
    'bootstrap-openclaw-missing-plugin',
    'watchdog-recovery',
    'watchdog-failed-fallback',
    'watchdog-active-no-listener-grace',
    'watchdog-service-layer-degraded',
    'watchdog-service-layer-threshold-recovery',
    'watchdog-service-layer-transient-retry',
    'watchdog-conversation-probe-ready',
    'watchdog-conversation-probe-minimal',
    'watchdog-conversation-probe-down',
    'watchdog-restart-priority-recovery',
    'watchdog-rollback-priority-before-doctor',
    'watchdog-doctor-deferred-until-survival-fails',
    'watchdog-survival-mode-recovery',
    'watchdog-survival-mode-sticky-until-stable',
    'watchdog-survival-mode-exit',
    'watchdog-config-drift-guard',
    'watchdog-env-drift-rollback',
    'watchdog-plugin-drift-rollback',
    'watchdog-recovery-notify-normal',
    'watchdog-last-good-generation-selection',
    'watchdog-config-invalid-rollback',
    'watchdog-incidents-open',
    'watchdog-incidents-resolved',
    'watchdog-metrics-healthy',
    'watchdog-metrics-open-incident',
    'watchdog-metrics-resolved',
    'watchdog-metrics-operator-context',
    'watchdog-model-http-error-failover',
    'watchdog-report-operator-attention',
    'watchdog-report-operator-attention-cleared',
    'watchdog-incident-attention-filter',
    'watchdog-incident-queue',
    'watchdog-incident-operator-open',
    'watchdog-incident-operator-resolved',
    'watchdog-incident-operator-reset',
    'watchdog-incident-timeline-open',
    'watchdog-incident-timeline-resolved',
    'watchdog-incident-notes-query',
]


class RehearsalSmokeMatrixTest(unittest.TestCase):
    def test_ci_workflow_uses_openclaw_watchdog_module_surface(self) -> None:
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

        self.assertIn('python -m openclaw_watchdog --help', workflow_text)
        self.assertIn('python -m py_compile openclaw_watchdog/*.py', workflow_text)
        self.assertNotIn('watchdog_v2', workflow_text)

    def test_ci_workflow_runs_critical_rehearsal_scenarios(self) -> None:
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

        self.assertIn('bash rehearsal/scripts/run-scenario.sh critical', workflow_text)

    def test_critical_tier_includes_core_survivability_scenarios(self) -> None:
        scenarios_readme = Path('rehearsal/scenarios/README.md').read_text(encoding='utf-8')
        run_script = Path('rehearsal/scripts/run-scenario.sh').read_text(encoding='utf-8')

        for scenario in (
            'watchdog-conversation-probe-ready',
            'watchdog-rollback-priority-before-doctor',
            'watchdog-survival-mode-recovery',
            'watchdog-config-drift-guard',
        ):
            self.assertIn(scenario, CRITICAL_SCENARIOS)
            self.assertIn(f'  {scenario}', run_script)
            critical_section = scenarios_readme.split('## Extended tier', 1)[0]
            self.assertIn(f'- `{scenario}`', critical_section)

    def test_ci_runs_only_critical_release_gate_scenarios(self) -> None:
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

        self.assertNotIn('bash rehearsal/scripts/run-scenario.sh extended', workflow_text)
        for scenario in EXTENDED_SCENARIOS:
            self.assertNotIn(f'bash rehearsal/scripts/run-scenario.sh {scenario}', workflow_text)

    def test_extended_scenarios_are_documented_but_not_required_in_ci(self) -> None:
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
        scenarios_readme = Path('rehearsal/scenarios/README.md').read_text(encoding='utf-8')
        run_script = Path('rehearsal/scripts/run-scenario.sh').read_text(encoding='utf-8')

        self.assertIn('critical)', run_script)
        self.assertIn('extended)', run_script)
        for scenario in CRITICAL_SCENARIOS + EXTENDED_SCENARIOS:
            self.assertIn(f'- `{scenario}`', scenarios_readme)
        for scenario in EXTENDED_SCENARIOS:
            self.assertNotIn(f'bash rehearsal/scripts/run-scenario.sh {scenario}', workflow_text)

    def test_critical_scenarios_have_expected_artifacts(self) -> None:
        scenario_dir = Path('rehearsal/scenarios')

        for scenario in CRITICAL_SCENARIOS:
            expected_txt = scenario_dir / f'{scenario}.expected.txt'
            expected_assertions = scenario_dir / f'{scenario}.assertions.json'
            self.assertTrue(expected_txt.exists() or expected_assertions.exists(), scenario)


if __name__ == '__main__':
    unittest.main()
