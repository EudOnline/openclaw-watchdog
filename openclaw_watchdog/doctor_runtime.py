from __future__ import annotations

from openclaw_watchdog.openclaw_runtime import doctor_runtime as openclaw_doctor_runtime


def run_doctor(engine) -> tuple[int, str]:
    return openclaw_doctor_runtime.run_doctor(engine)


def config_invalid(engine, doctor_output: str) -> bool:
    return openclaw_doctor_runtime.config_invalid(engine, doctor_output)
