import os
import tempfile
import unittest
from pathlib import Path

from watchdog_v2.config import Config


class ConfigDefaultsTest(unittest.TestCase):
    def test_safe_defaults_without_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_home:
            expected_home = Path(temp_home)
            old_home = os.environ.get('HOME')
            os.environ['HOME'] = temp_home
            try:
                config = Config.load(Path(temp_home) / 'missing.env')
            finally:
                if old_home is None:
                    os.environ.pop('HOME', None)
                else:
                    os.environ['HOME'] = old_home

        self.assertFalse(config.watchdog_enable_pre_repair_backup)
        self.assertFalse(config.watchdog_enable_codex_autorun)
        self.assertEqual(config.watchdog_backup_script, Path('./tools/openclaw-backup.js').expanduser())
        self.assertEqual(config.watchdog_backup_env_file, Path('./config/openclaw-backup.env').expanduser())
        self.assertEqual(config.watchdog_restart_wait_seconds, 12)
        self.assertEqual(config.watchdog_service_level_timeout_seconds, 12)
        self.assertEqual(config.watchdog_service_level_retry_grace_seconds, 8)
        self.assertEqual(config.watchdog_codex_workdir, expected_home)
        self.assertEqual(config.watchdog_opencode_fallback_workdir, expected_home)
        self.assertEqual(config.openclaw_config, expected_home / '.openclaw/openclaw.json')
        self.assertEqual(config.watchdog_state_dir, expected_home / '.openclaw-backup/watchdog')


if __name__ == '__main__':
    unittest.main()
