from __future__ import annotations

from pathlib import Path

from openclaw_watchdog.openclaw_runtime import config_runtime
from openclaw_watchdog.openclaw_runtime import doctor_runtime
from openclaw_watchdog.openclaw_runtime import status_runtime
from openclaw_watchdog.openclaw_runtime.capabilities import DoctorCapabilities
from openclaw_watchdog.openclaw_runtime.contracts import GatewayContract


class OpenClawRuntimeAdapter:
    def read_status(self, engine) -> dict[str, object] | None:
        return status_runtime.read_status(engine)

    def read_health(self, engine) -> dict[str, object] | None:
        return status_runtime.read_health(engine)

    def run_doctor(self, engine) -> tuple[int, str]:
        return doctor_runtime.run_doctor(engine)

    def config_invalid(self, engine, doctor_output: str) -> bool:
        return doctor_runtime.config_invalid(engine, doctor_output)

    def detect_gateway_contract(self, engine, status_payload: dict[str, object] | None) -> GatewayContract:
        return status_runtime.detect_gateway_contract(engine, status_payload)

    def detect_doctor_capabilities(self, help_text: str) -> DoctorCapabilities:
        return doctor_runtime.detect_doctor_capabilities(help_text)

    def load_json_object(self, path: Path, *, label: str, allow_jsonc: bool) -> dict[str, object]:
        return config_runtime.load_json_object(path, label=label, allow_jsonc=allow_jsonc)

    def read_logging_file_from_config(self, config_path: Path) -> Path | None:
        return config_runtime.read_logging_file_from_config(config_path)


_DEFAULT_ADAPTER = OpenClawRuntimeAdapter()


def default_adapter() -> OpenClawRuntimeAdapter:
    return _DEFAULT_ADAPTER
