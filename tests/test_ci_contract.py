from __future__ import annotations

from pathlib import Path
import unittest


class CiContractTest(unittest.TestCase):
    def test_ci_workflow_installs_and_runs_ruff_and_mypy(self) -> None:
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

        self.assertIn('python -m pip install ruff mypy', workflow_text)
        self.assertIn('python -m ruff check', workflow_text)
        self.assertIn('python -m mypy', workflow_text)

    def test_ci_workflow_installs_package_and_runs_console_script_smoke(self) -> None:
        workflow_text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')

        self.assertIn('python -m pip install .', workflow_text)
        self.assertIn('openclaw-watchdog --help', workflow_text)

    def test_pyproject_declares_quality_tool_configuration(self) -> None:
        pyproject_text = Path('pyproject.toml').read_text(encoding='utf-8')

        self.assertIn('[tool.ruff]', pyproject_text)
        self.assertIn('[tool.mypy]', pyproject_text)


if __name__ == '__main__':
    unittest.main()
