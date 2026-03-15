from __future__ import annotations

from openclaw_watchdog.openclaw_runtime.capabilities import DoctorCapabilities


def run_doctor(engine) -> tuple[int, str]:
    result = engine.run_command(
        ['openclaw', 'doctor', '--non-interactive'],
        timeout=engine.config.watchdog_doctor_timeout_seconds,
        merge_stderr=True,
    )
    return result.returncode, result.output


def config_invalid(engine, doctor_output: str) -> bool:
    return 'config invalid' in doctor_output.lower()


def detect_doctor_capabilities(help_text: str) -> DoctorCapabilities:
    text = help_text.lower()
    supports_repair = '--repair' in text
    supports_non_interactive = '--non-interactive' in text
    supports_yes = '--yes' in text
    return DoctorCapabilities(
        supports_repair=supports_repair,
        supports_non_interactive=supports_non_interactive,
        supports_yes=supports_yes,
        supports_non_interactive_yes=supports_non_interactive and supports_yes,
    )
