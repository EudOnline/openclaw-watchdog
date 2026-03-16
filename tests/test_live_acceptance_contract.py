from __future__ import annotations

from pathlib import Path
import unittest


class LiveAcceptanceContractTest(unittest.TestCase):
    def test_live_acceptance_script_supports_env_and_macos_launchd_evidence(self) -> None:
        script = Path('scripts/openclaw-watchdog-live-acceptance.sh').read_text(encoding='utf-8')

        self.assertIn('--env', script)
        self.assertIn('launchctl print', script)
        self.assertIn('watchdog-launchd.txt', script)
        self.assertIn('gateway-launchd.txt', script)


if __name__ == '__main__':
    unittest.main()
