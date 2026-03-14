from __future__ import annotations


def run_doctor(engine) -> tuple[int, str]:
    result = engine.run_command(
        ['openclaw', 'doctor', '--non-interactive'],
        timeout=engine.config.watchdog_doctor_timeout_seconds,
        merge_stderr=True,
    )
    return result.returncode, result.output


def config_invalid(engine, doctor_output: str) -> bool:
    return 'Config invalid' in doctor_output
