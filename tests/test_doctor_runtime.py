import unittest
from types import SimpleNamespace
from unittest.mock import patch


class DoctorRuntimeTests(unittest.TestCase):
    def test_doctor_runtime_delegates_to_openclaw_runtime_owner(self) -> None:
        from openclaw_watchdog import doctor_runtime

        owner = SimpleNamespace(
            run_doctor=unittest.mock.Mock(return_value=(0, 'delegated')),
            config_invalid=unittest.mock.Mock(return_value=True),
        )
        engine = object()

        with patch.object(doctor_runtime, 'openclaw_doctor_runtime', owner, create=True):
            self.assertEqual(doctor_runtime.run_doctor(engine), (0, 'delegated'))
            self.assertTrue(doctor_runtime.config_invalid(engine, 'warning'))

        owner.run_doctor.assert_called_once_with(engine)
        owner.config_invalid.assert_called_once_with(engine, 'warning')

    def test_run_doctor_uses_non_interactive_openclaw_doctor(self) -> None:
        from openclaw_watchdog import doctor_runtime

        calls: list[dict[str, object]] = []

        def run_command(args, *, timeout=None, cwd=None, merge_stderr=False, input_text=None):
            calls.append(
                {
                    'args': args,
                    'timeout': timeout,
                    'cwd': cwd,
                    'merge_stderr': merge_stderr,
                    'input_text': input_text,
                }
            )
            return SimpleNamespace(returncode=7, output='doctor output')

        engine = SimpleNamespace(
            config=SimpleNamespace(watchdog_doctor_timeout_seconds=23),
            run_command=run_command,
        )

        self.assertEqual(doctor_runtime.run_doctor(engine), (7, 'doctor output'))
        self.assertEqual(
            calls,
            [
                {
                    'args': ['openclaw', 'doctor', '--non-interactive'],
                    'timeout': 23,
                    'cwd': None,
                    'merge_stderr': True,
                    'input_text': None,
                }
            ],
        )

    def test_config_invalid_detects_invalid_marker(self) -> None:
        from openclaw_watchdog import doctor_runtime

        engine = object()

        self.assertTrue(doctor_runtime.config_invalid(engine, 'warning: Config invalid: missing token'))
        self.assertFalse(doctor_runtime.config_invalid(engine, 'doctor completed normally'))


if __name__ == '__main__':
    unittest.main()
