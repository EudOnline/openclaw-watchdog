import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class RuntimeWrapperTest(unittest.TestCase):
    def test_requires_supported_python_without_traceback(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        wrapper = repo_root / 'scripts' / 'openclaw-watchdog'

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_python3 = Path(temp_dir) / 'python3'
            fake_python3.write_text(
                '#!/usr/bin/env bash\n'
                'if [ "${1:-}" = "-c" ]; then\n'
                '  exit 1\n'
                'fi\n'
                'echo "fake python3 should not execute watchdog" >&2\n'
                'exit 99\n',
                encoding='utf-8',
            )
            fake_python3.chmod(fake_python3.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env['PATH'] = f"{temp_dir}:/usr/bin:/bin"

            result = subprocess.run(
                [str(wrapper), '--help'],
                cwd=repo_root,
                capture_output=True,
                text=True,
                env=env,
            )

        combined = (result.stdout or '') + (result.stderr or '')

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', combined)
        self.assertIn('Python 3.11+', combined)


if __name__ == '__main__':
    unittest.main()
