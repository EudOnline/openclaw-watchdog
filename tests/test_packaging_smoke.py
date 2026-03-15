from __future__ import annotations

from pathlib import Path
import unittest


class PackagingSmokeTest(unittest.TestCase):
    def test_pyproject_declares_console_script(self) -> None:
        pyproject_text = Path('pyproject.toml').read_text(encoding='utf-8')

        self.assertIn('openclaw-watchdog = "openclaw_watchdog.cli:main"', pyproject_text)


if __name__ == '__main__':
    unittest.main()
