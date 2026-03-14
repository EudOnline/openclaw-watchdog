import tempfile
import unittest
from pathlib import Path

from openclaw_watchdog.runtime import run_capture_to_file, run_command


class RuntimeHelpersTest(unittest.TestCase):
    def test_run_command_missing_binary_returns_127(self) -> None:
        result = run_command(['definitely-not-a-real-binary-openclaw'])
        self.assertEqual(result.returncode, 127)
        self.assertTrue(result.stderr)

    def test_run_capture_to_file_writes_combined_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / 'capture.txt'
            run_capture_to_file(['sh', '-c', 'printf "hello"; printf " world" >&2'], destination)
            self.assertIn('hello', destination.read_text(encoding='utf-8'))
            self.assertIn('world', destination.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
