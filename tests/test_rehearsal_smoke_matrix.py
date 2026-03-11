from __future__ import annotations

from pathlib import Path
import unittest


CRITICAL_SCENARIOS = [
    'bootstrap-missing-openclaw',
    'watchdog-conversation-probe-ready',
    'watchdog-failed-fallback',
    'watchdog-incident-queue',
]


class RehearsalSmokeMatrixTest(unittest.TestCase):
    def test_ci_workflow_runs_critical_rehearsal_scenarios(self) -> None:
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

        for scenario in CRITICAL_SCENARIOS:
            self.assertIn(f'bash rehearsal/scripts/run-scenario.sh {scenario}', workflow_text)

    def test_critical_scenarios_have_expected_artifacts(self) -> None:
        scenario_dir = Path('rehearsal/scenarios')

        for scenario in CRITICAL_SCENARIOS:
            expected_txt = scenario_dir / f'{scenario}.expected.txt'
            expected_assertions = scenario_dir / f'{scenario}.assertions.json'
            self.assertTrue(expected_txt.exists() or expected_assertions.exists(), scenario)


if __name__ == '__main__':
    unittest.main()
